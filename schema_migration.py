"""
schema_migration.py – Database migration utilities.

Features:
  - Version-based schema migrations (simple, no Alembic required for SQLite)
  - SQLite → PostgreSQL data migration
  - DB health check and status report

Usage:
  python schema_migration.py status          # check DB status & migrations
  python schema_migration.py migrate         # apply pending migrations
  python schema_migration.py to-postgres     # copy data SQLite → PostgreSQL
  python schema_migration.py reset           # DROP all tables and re-create (DESTRUCTIVE!)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import inspect, text

from database import DATABASE_URL, engine, get_db_info, get_db_session, init_db

# ── Migration Registry ────────────────────────────────────────────────────────────
# Each migration is a tuple: (version, description, up_sql_list)
# Keep this append-only. Never modify existing migrations.

MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "Initial schema – create all tables via SQLAlchemy metadata", []),  # handled by init_db()
    (2, "Add index on simulation_runs.sim_type (covered by model but explicit here)", [
        # SQLite and PostgreSQL compatible
        "CREATE INDEX IF NOT EXISTS ix_sim_runs_sim_type_v2 ON simulation_runs (sim_type, created_at DESC)",
    ]),
    (3, "Add total_runs column default update trigger comment", [
        # Documentation migration – no DDL needed
    ]),
]

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    description TEXT,
    applied_at  TEXT NOT NULL
)
"""


# ── Migration Engine ──────────────────────────────────────────────────────────────

def _ensure_migrations_table():
    """Create schema_migrations tracking table if not exists."""
    with engine.connect() as conn:
        conn.execute(text(SCHEMA_VERSION_TABLE))
        conn.commit()


def get_applied_versions() -> list[int]:
    """Return list of applied migration versions."""
    _ensure_migrations_table()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version FROM schema_migrations ORDER BY version")).fetchall()
    return [r[0] for r in rows]


def apply_migrations(dry_run: bool = False) -> list[int]:
    """
    Apply all pending migrations.

    Returns: list of version numbers that were applied.
    """
    _ensure_migrations_table()
    applied = get_applied_versions()
    pending = [(v, desc, sqls) for v, desc, sqls in MIGRATIONS if v not in applied]

    if not pending:
        print("[Migration] All migrations already applied. ✓")
        return []

    applied_now = []
    with engine.connect() as conn:
        for version, desc, sql_statements in pending:
            print(f"[Migration] Applying v{version}: {desc}")
            if not dry_run:
                for sql in sql_statements:
                    if sql.strip():
                        conn.execute(text(sql))
                conn.execute(
                    text("INSERT INTO schema_migrations (version, description, applied_at) VALUES (:v, :d, :t)"),
                    {"v": version, "d": desc, "t": datetime.now(timezone.utc).isoformat()}
                )
                conn.commit()
                applied_now.append(version)
            else:
                print(f"  [dry-run] Would apply {len(sql_statements)} SQL statements.")
                applied_now.append(version)

    return applied_now


# ── SQLite → PostgreSQL Migration ─────────────────────────────────────────────────

def migrate_sqlite_to_postgres(
    sqlite_url: str = "sqlite:///physics_sim.db",
    pg_url: str | None = None,
    batch_size: int = 500,
    dry_run: bool = False,
) -> dict:
    """
    Copy all data from SQLite to PostgreSQL.

    Args:
        sqlite_url: Source SQLite database URL.
        pg_url: Target PostgreSQL URL. Falls back to DATABASE_URL if it's a PG url.
        batch_size: Insert batch size.
        dry_run: If True, read but do not write.

    Returns:
        Summary dict of {table_name: rows_migrated}.
    """
    if pg_url is None:
        pg_url = DATABASE_URL
    if not pg_url.startswith("postgresql"):
        raise ValueError(
            "Target DATABASE_URL must be a PostgreSQL URL.\n"
            "Set: DATABASE_URL=postgresql://user:pass@host/dbname"
        )

    from sqlalchemy import create_engine as _ce
    from sqlalchemy.orm import sessionmaker as _sm

    print(f"[Migration] SQLite → PostgreSQL")
    print(f"  Source: {sqlite_url}")
    print(f"  Target: {pg_url.split('@')[-1]}")

    # Source session
    sqlite_engine = _ce(sqlite_url, connect_args={"check_same_thread": False})
    SourceSession = _sm(bind=sqlite_engine, autoflush=False)

    # Target session
    pg_engine = _ce(pg_url, pool_pre_ping=True)

    # Ensure target schema exists
    if not dry_run:
        from models import Base
        Base.metadata.create_all(bind=pg_engine)

    TargetSession = _sm(bind=pg_engine, autoflush=False)

    tables = [
        "user_sessions",
        "simulation_runs",
        "simulation_results",
        "analytics_summary",
        "parameter_heatmap",
        "schema_migrations",
    ]

    summary = {}

    src = SourceSession()
    tgt = TargetSession()

    try:
        for table in tables:
            src_insp = inspect(sqlite_engine)
            if table not in src_insp.get_table_names():
                print(f"  [skip] {table}: not in source DB")
                continue

            rows = src.execute(text(f"SELECT * FROM {table}")).fetchall()
            count = len(rows)
            summary[table] = count

            if count == 0:
                print(f"  [empty] {table}: 0 rows")
                continue

            if dry_run:
                print(f"  [dry-run] {table}: would migrate {count} rows")
                continue

            # Get column names
            cols = src.execute(text(f"PRAGMA table_info({table})")).fetchall()
            col_names = [c[1] for c in cols] if cols else list(rows[0]._fields)

            # Batch insert
            col_str  = ", ".join(col_names)
            val_str  = ", ".join(f":{c}" for c in col_names)
            insert_sql = text(f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({val_str})")

            # For PG, use ON CONFLICT DO NOTHING
            if pg_url.startswith("postgresql"):
                insert_sql = text(
                    f"INSERT INTO {table} ({col_str}) VALUES ({val_str}) ON CONFLICT DO NOTHING"
                )

            for i in range(0, count, batch_size):
                batch = rows[i:i + batch_size]
                tgt.execute(insert_sql, [dict(zip(col_names, list(r))) for r in batch])
                tgt.commit()
                print(f"  ✓ {table}: {min(i + batch_size, count)}/{count} rows")

        print(f"\n[Migration] Complete! Summary: {summary}")
        return summary

    finally:
        src.close()
        tgt.close()


# ── Status Report ─────────────────────────────────────────────────────────────────

def print_status():
    """Print full database status report."""
    print("\n" + "=" * 60)
    print("  Database Status Report")
    print("=" * 60)

    try:
        info = get_db_info()
        print(f"  Engine:   {info['dialect']}")
        print(f"  URL:      {info['url']}")
        print(f"  Version:  {info['version']}")
    except Exception as e:
        print(f"  [ERROR] Cannot connect: {e}")
        return

    # Table counts
    insp = inspect(engine)
    existing_tables = insp.get_table_names()
    expected_tables = [
        "user_sessions", "simulation_runs", "simulation_results",
        "analytics_summary", "parameter_heatmap", "schema_migrations"
    ]

    print("\n  Tables:")
    with engine.connect() as conn:
        for t in expected_tables:
            if t in existing_tables:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                print(f"    ✓  {t:<30} {count:>8} rows")
            else:
                print(f"    ✗  {t:<30} [NOT FOUND]")

    # Migration status
    applied = get_applied_versions()
    latest  = max(v for v, _, _ in MIGRATIONS)
    print(f"\n  Schema Migrations:")
    print(f"    Applied: {applied}")
    print(f"    Latest:  v{latest}")
    if set(v for v, _, _ in MIGRATIONS) == set(applied):
        print(f"    Status:  ✓ Up to date")
    else:
        pending = [v for v, _, _ in MIGRATIONS if v not in applied]
        print(f"    Status:  ⚠ Pending migrations: {pending}")

    print("=" * 60 + "\n")


# ── Reset (DESTRUCTIVE) ────────────────────────────────────────────────────────────

def reset_database(confirm: bool = False):
    """Drop all tables and recreate. DESTRUCTIVE – data will be lost!"""
    if not confirm:
        resp = input("[DANGER] This will DELETE ALL DATA. Type 'yes' to confirm: ")
        if resp.strip().lower() != "yes":
            print("Aborted.")
            return

    from models import Base
    print("[Reset] Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("[Reset] Recreating schema...")
    init_db()
    apply_migrations()
    print("[Reset] Done. Fresh database ready.")


# ── CLI ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schema migration tool for GR Simulator")
    parser.add_argument("command", choices=["status", "migrate", "to-postgres", "reset", "init"])
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--sqlite-url", default="sqlite:///physics_sim.db")
    parser.add_argument("--pg-url",     help="PostgreSQL target URL")
    parser.add_argument("--yes",        action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()

    if args.command == "status":
        print_status()

    elif args.command == "init":
        init_db()
        apply_migrations(dry_run=args.dry_run)
        print_status()

    elif args.command == "migrate":
        applied = apply_migrations(dry_run=args.dry_run)
        if applied:
            print(f"Applied {len(applied)} migration(s): {applied}")

    elif args.command == "to-postgres":
        if not args.pg_url and not DATABASE_URL.startswith("postgresql"):
            print("ERROR: Set --pg-url or DATABASE_URL to a PostgreSQL URL first.")
            sys.exit(1)
        migrate_sqlite_to_postgres(
            sqlite_url=args.sqlite_url,
            pg_url=args.pg_url,
            dry_run=args.dry_run,
        )

    elif args.command == "reset":
        reset_database(confirm=args.yes)
