"""
etl_pipeline.py – ETL (Extract, Transform, Load) pipeline for the GR Simulator.

Jobs:
  1. aggregate_daily_stats()      – Compute & upsert daily AnalyticsSummary rows
  2. update_parameter_heatmap()   – Refresh ParameterHeatmap from recent runs
  3. cleanup_old_results()        – Delete result_data blobs older than retention policy
  4. export_to_json()             – Export dataset for ML / offline analysis

Run manually:
  python etl_pipeline.py                  # run all jobs
  python etl_pipeline.py --job aggregate  # specific job
  python etl_pipeline.py --dry-run        # validate without writing

Schedule with cron (Linux) or Task Scheduler (Windows):
  0 2 * * * python etl_pipeline.py        # 2 AM daily
"""

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, text

from database import get_db_session, init_db
from models import AnalyticsSummary, ParameterHeatmap, SimulationResult, SimulationRun, UserSession

# ── Config ───────────────────────────────────────────────────────────────────────
RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", 90))
EXPORT_DIR = os.getenv("ETL_EXPORT_DIR", "etl_exports")


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _today_str() -> str:
    return date.today().isoformat()

def _date_str(dt: datetime) -> str:
    return dt.date().isoformat()


# ── Job 1: Aggregate Daily Statistics ───────────────────────────────────────────

def aggregate_daily_stats(
    dry_run: bool = False,
    target_date: str | None = None,
    lookback_days: int = 7,
) -> dict:
    """
    Compute daily stats per sim_type and upsert into AnalyticsSummary.

    Args:
        dry_run: If True, compute but do not write to DB.
        target_date: Specific date (YYYY-MM-DD). If None, processes last `lookback_days`.
        lookback_days: How many past days to re-aggregate (default 7 for catch-up).

    Returns:
        Dict of {date: {sim_type: {stats}}} of what was computed.
    """
    print(f"[ETL] aggregate_daily_stats: dry_run={dry_run}, target={target_date or f'last {lookback_days} days'}")

    if target_date:
        dates = [target_date]
    else:
        today = date.today()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(lookback_days)]

    report = {}

    with get_db_session() as db:
        for day_str in dates:
            day_start = datetime.fromisoformat(f"{day_str}T00:00:00+00:00")
            day_end   = datetime.fromisoformat(f"{day_str}T23:59:59+00:00")

            # Fetch all runs for this day with their results
            runs = (
                db.query(SimulationRun)
                .filter(SimulationRun.created_at >= day_start, SimulationRun.created_at <= day_end)
                .all()
            )

            if not runs:
                continue

            # Group by sim_type
            by_type: dict[str, list[SimulationRun]] = defaultdict(list)
            for r in runs:
                by_type[r.sim_type].append(r)

            report[day_str] = {}

            for sim_type, type_runs in by_type.items():
                run_ids = [r.id for r in type_runs]
                session_ids = {r.session_id for r in type_runs if r.session_id}

                # Fetch results for these runs
                results = (
                    db.query(SimulationResult)
                    .filter(SimulationResult.run_id.in_(run_ids))
                    .all()
                )
                result_map = {res.run_id: res for res in results}

                exec_times = [
                    result_map[r.id].execution_ms
                    for r in type_runs
                    if r.id in result_map and result_map[r.id].execution_ms is not None
                ]
                captures = [
                    result_map[r.id].captured
                    for r in type_runs
                    if r.id in result_map
                ]
                path_counts = [
                    result_map[r.id].path_points_count
                    for r in type_runs
                    if r.id in result_map and result_map[r.id].path_points_count
                ]

                # Popular parameter values (find most common value per param key)
                param_counter: dict[str, Counter] = defaultdict(Counter)
                for run in type_runs:
                    for k, v in (run.parameters or {}).items():
                        param_counter[k][str(round(float(v), 2) if isinstance(v, (int, float)) else v)] += 1
                popular_params = {
                    k: counter.most_common(3)
                    for k, counter in param_counter.items()
                }

                stats = {
                    "total_runs": len(type_runs),
                    "unique_sessions": len(session_ids),
                    "avg_execution_ms": round(statistics.mean(exec_times), 2) if exec_times else None,
                    "median_execution_ms": round(statistics.median(exec_times), 2) if exec_times else None,
                    "capture_rate": round(sum(captures) / len(captures) * 100, 2) if captures else None,
                    "avg_path_points": round(statistics.mean(path_counts), 0) if path_counts else None,
                    "popular_params": popular_params,
                }
                report[day_str][sim_type] = stats

                if not dry_run:
                    # Upsert AnalyticsSummary
                    existing = (
                        db.query(AnalyticsSummary)
                        .filter_by(date=day_str, sim_type=sim_type)
                        .first()
                    )
                    if existing:
                        existing.total_runs        = stats["total_runs"]
                        existing.unique_sessions   = stats["unique_sessions"]
                        existing.avg_execution_ms  = stats["avg_execution_ms"]
                        existing.median_execution_ms = stats["median_execution_ms"]
                        existing.capture_rate      = stats["capture_rate"]
                        existing.avg_path_points   = stats["avg_path_points"]
                        existing.popular_params    = stats["popular_params"]
                        existing.updated_at        = _now_utc()
                    else:
                        db.add(AnalyticsSummary(date=day_str, sim_type=sim_type, **stats))

            print(f"  [ETL] {day_str}: {sum(len(v) for v in report.get(day_str, {}).values())} types aggregated")

    return report


# ── Job 2: Update Parameter Heatmap ─────────────────────────────────────────────

def update_parameter_heatmap(dry_run: bool = False, since_hours: int = 25) -> int:
    """
    Increment ParameterHeatmap counts from recent SimulationRun records.
    Uses a sliding window (since_hours) to avoid re-processing old data.

    Returns: Number of heatmap records updated/created.
    """
    print(f"[ETL] update_parameter_heatmap: dry_run={dry_run}, window={since_hours}h")
    cutoff = _now_utc() - timedelta(hours=since_hours)
    upserted = 0

    with get_db_session() as db:
        recent_runs = (
            db.query(SimulationRun)
            .filter(SimulationRun.created_at >= cutoff)
            .all()
        )
        run_ids = [r.id for r in recent_runs]
        results = (
            db.query(SimulationResult)
            .filter(SimulationResult.run_id.in_(run_ids))
            .all()
        ) if run_ids else []
        result_map = {res.run_id: res for res in results}

        for run in recent_runs:
            captured = result_map[run.id].captured if run.id in result_map else False
            for param_key, param_val in (run.parameters or {}).items():
                val_str = str(round(float(param_val), 3) if isinstance(param_val, (int, float)) else param_val)

                if not dry_run:
                    existing = (
                        db.query(ParameterHeatmap)
                        .filter_by(sim_type=run.sim_type, param_key=param_key, param_value=val_str)
                        .first()
                    )
                    if existing:
                        existing.usage_count  += 1
                        existing.capture_count += 1 if captured else 0
                        existing.last_used     = _now_utc()
                    else:
                        db.add(ParameterHeatmap(
                            sim_type=run.sim_type,
                            param_key=param_key,
                            param_value=val_str,
                            usage_count=1,
                            capture_count=1 if captured else 0,
                        ))
                upserted += 1

    print(f"  [ETL] Heatmap: {upserted} parameter records processed.")
    return upserted


# ── Job 3: Cleanup Old Results ───────────────────────────────────────────────────

def cleanup_old_results(dry_run: bool = False, retention_days: int = RETENTION_DAYS) -> int:
    """
    Delete full result_data blobs older than `retention_days` to save disk space.
    Keeps result_summary and statistics intact.

    Returns: Number of rows cleaned up.
    """
    print(f"[ETL] cleanup_old_results: dry_run={dry_run}, retention={retention_days} days")
    cutoff = _now_utc() - timedelta(days=retention_days)
    count = 0

    with get_db_session() as db:
        old_results = (
            db.query(SimulationResult)
            .join(SimulationRun)
            .filter(SimulationRun.created_at < cutoff)
            .filter(SimulationResult.result_data.isnot(None))
            .all()
        )
        count = len(old_results)
        if not dry_run:
            for res in old_results:
                res.result_data = None   # nullify blob, keep metadata
        print(f"  [ETL] Cleaned {count} result_data blobs older than {retention_days} days.")

    return count


# ── Job 4: Export Dataset ────────────────────────────────────────────────────────

def export_to_json(output_dir: str = EXPORT_DIR, since_days: int = 30) -> str:
    """
    Export simulation data as JSON for offline ML / analysis.
    Creates: {output_dir}/export_{date}.json

    Returns: Path to exported file.
    """
    os.makedirs(output_dir, exist_ok=True)
    cutoff = _now_utc() - timedelta(days=since_days)
    today  = _today_str()
    filepath = os.path.join(output_dir, f"export_{today}.json")

    print(f"[ETL] export_to_json: since={since_days} days → {filepath}")

    with get_db_session() as db:
        runs = (
            db.query(SimulationRun)
            .filter(SimulationRun.created_at >= cutoff)
            .all()
        )
        run_ids = [r.id for r in runs]
        results = (
            db.query(SimulationResult)
            .filter(SimulationResult.run_id.in_(run_ids))
            .all()
        ) if run_ids else []
        result_map = {res.run_id: res for res in results}

        records = []
        for run in runs:
            res = result_map.get(run.id)
            records.append({
                "run_uuid":      run.run_uuid,
                "sim_type":      run.sim_type,
                "parameters":    run.parameters,
                "created_at":    run.created_at.isoformat(),
                "execution_ms":  res.execution_ms if res else None,
                "path_points":   res.path_points_count if res else None,
                "captured":      res.captured if res else None,
                "result_summary": res.result_summary if res else None,
            })

    export_data = {
        "exported_at": _now_utc().isoformat(),
        "since_days":  since_days,
        "total_records": len(records),
        "records": records,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"  [ETL] Exported {len(records)} records → {filepath}")
    return filepath


# ── Run All Jobs ─────────────────────────────────────────────────────────────────

def run_all_jobs(dry_run: bool = False) -> dict:
    """Execute the full ETL pipeline in order."""
    print(f"\n{'='*60}")
    print(f"  ETL Pipeline – General Relativity Simulator")
    print(f"  Started: {_now_utc().isoformat()}")
    print(f"  dry_run: {dry_run}")
    print(f"{'='*60}\n")

    results = {}

    # Job 1
    results["aggregate_daily_stats"] = aggregate_daily_stats(dry_run=dry_run)

    # Job 2
    results["heatmap_records"] = update_parameter_heatmap(dry_run=dry_run)

    # Job 3
    results["cleaned_blobs"] = cleanup_old_results(dry_run=dry_run)

    # Job 4 (only in non-dry-run)
    if not dry_run:
        results["export_path"] = export_to_json()

    print(f"\n{'='*60}")
    print(f"  ETL Pipeline complete. dry_run={dry_run}")
    print(f"{'='*60}\n")
    return results


# ── CLI Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ETL pipeline for GR Simulator")
    parser.add_argument("--job", choices=["aggregate", "heatmap", "cleanup", "export", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="Compute without writing to DB")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (for aggregate job)")
    parser.add_argument("--days", type=int, default=30, help="Lookback days (for export job)")
    args = parser.parse_args()

    # Ensure DB and tables exist
    init_db()

    if args.job == "all":
        run_all_jobs(dry_run=args.dry_run)
    elif args.job == "aggregate":
        aggregate_daily_stats(dry_run=args.dry_run, target_date=args.date)
    elif args.job == "heatmap":
        update_parameter_heatmap(dry_run=args.dry_run)
    elif args.job == "cleanup":
        cleanup_old_results(dry_run=args.dry_run)
    elif args.job == "export":
        export_to_json(since_days=args.days)
