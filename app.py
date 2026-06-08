"""
General Relativity Simulation Backend
Simulates Schwarzschild metric, geodesic paths, gravitational lensing,
and time dilation using Python + Flask.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import numpy as np
import math

app = Flask(__name__)
CORS(app)

# ── Constants ──────────────────────────────────────────────────────────────────
G  = 6.674e-11   # Gravitational constant (m³ kg⁻¹ s⁻²)
c  = 3e8         # Speed of light (m/s)
M_SUN = 1.989e30 # Solar mass (kg)


# ── Schwarzschild metric helpers ───────────────────────────────────────────────

def schwarzschild_radius(M_kg):
    """rs = 2GM/c²"""
    return 2 * G * M_kg / c**2


def time_dilation_factor(r, rs):
    """
    Gravitational time dilation factor: sqrt(1 - rs/r)
    Returns how much slower time runs at radius r compared to infinity.
    r must be > rs.
    """
    if r <= rs:
        return 0.0
    return math.sqrt(max(0.0, 1.0 - rs / r))


def geodesic_rk4(r0, phi0, dr_dtau0, dphi_dtau0, rs, steps=800, dtau=0.5):
    """
    Integrate Schwarzschild geodesic equations using RK4.

    Equations of motion (equatorial plane, massive particle):
        d²r/dτ²   = r(dphi/dτ)² (1 - rs/r) - (rs/2)(1 - rs/r)/r²  * (dr/dτ)² / (1-rs/r)
                    + rs/(2r²) (1-rs/r) (dt/dτ)² ... simplified effective potential form:

    We use the effective potential approach:
        (dr/dτ)² = E² - (1 - rs/r)(1 + L²/r²)
    with conserved energy E and angular momentum L.
    """
    path = []
    r, phi = float(r0), float(phi0)
    u_r, u_phi = float(dr_dtau0), float(dphi_dtau0)

    # Conserved angular momentum L = r² dphi/dτ
    L = r0**2 * dphi_dtau0
    # Conserved energy (for timelike geodesic, rest mass = 1)
    f0 = 1.0 - rs / r0
    E2 = f0 * (1 + L**2 / r0**2) + u_r**2  # E² from initial conditions

    def derivatives(r, phi, u_r):
        if r <= rs * 1.001:
            return 0, 0, 0
        f = 1.0 - rs / r
        # du_r/dτ from geodesic equation (effective potential derivative)
        # V_eff = (1 - rs/r)(1 + L²/r²)
        dV_dr = (rs / r**2) * (1 + L**2 / r**2) + (1 - rs / r) * (-2 * L**2 / r**3)
        d2r = -0.5 * dV_dr
        dphi = L / r**2
        dr = u_r
        return dr, dphi, d2r

    for _ in range(steps):
        if r <= rs * 1.01:
            path.append({'r': float(rs), 'phi': float(phi), 'captured': True})
            break

        path.append({'r': float(r), 'phi': float(phi), 'captured': False})

        # RK4
        dr1, dp1, du1 = derivatives(r, phi, u_r)
        dr2, dp2, du2 = derivatives(r + 0.5*dtau*dr1, phi + 0.5*dtau*dp1, u_r + 0.5*dtau*du1)
        dr3, dp3, du3 = derivatives(r + 0.5*dtau*dr2, phi + 0.5*dtau*dp2, u_r + 0.5*dtau*du2)
        dr4, dp4, du4 = derivatives(r + dtau*dr3, phi + dtau*dp3, u_r + dtau*du3)

        r   += dtau * (dr1 + 2*dr2 + 2*dr3 + dr4) / 6
        phi += dtau * (dp1 + 2*dp2 + 2*dp3 + dp4) / 6
        u_r += dtau * (du1 + 2*du2 + 2*du3 + du4) / 6

        if r > r0 * 5:
            break

    return path


def light_deflection_angle(b, rs):
    """
    Approximate light deflection angle: δ ≈ 2rs/b (weak field, b >> rs)
    Returns angle in radians.
    """
    if b <= 0:
        return math.pi
    if b < rs * 1.5:  # Inside photon sphere
        return math.pi
    return 2.0 * rs / b


def geodesic_light_rk4(b, rs, steps=1200, dlambda=0.3):
    """
    Integrate null geodesic (light ray) in Schwarzschild spacetime.
    Uses impact parameter b.
    Start from large r on one side, shoot toward mass.
    """
    path = []
    # Start far away, r_start = 50 * rs or 20*b whichever is larger
    r_start = max(50 * rs, 20 * abs(b))
    phi_start = 0.0
    # u_r initial (moving inward)
    u_r = -1.0
    # L = b (impact parameter for light)
    L = float(b)
    r = float(r_start)
    phi = float(phi_start)

    # For null geodesic: (dr/dlambda)² = 1/b² - (1-rs/r)/r²
    # Effective potential: V = (1-rs/r)/r²,  E=1/b

    def deriv_light(r, phi, u_r):
        if r <= rs * 1.001:
            return 0, 0, 0
        # dphi/dlambda = L/r² (with L=b, affine parameterized with E=1)
        dphi = L / r**2
        # d²r/dlambda² = -(1/2) dV/dr where V = (1-rs/r)/r²
        # dV/dr = rs/(r³) - 2/r³ * (1 - rs/r)  = (rs - 2)/r³ + 2rs/r⁴... let me redo:
        # V(r) = (1-rs/r)/r² = 1/r² - rs/r³
        # dV/dr = -2/r³ + 3rs/r⁴
        dV_dr = -2.0 / r**3 + 3.0 * rs / r**4
        d2r = -0.5 * dV_dr * L**2  # scaled
        dr = u_r
        return dr, dphi, d2r

    for _ in range(steps):
        if r <= rs * 1.01:
            path.append({'r': float(rs), 'phi': float(phi), 'captured': True})
            break

        path.append({'r': float(r), 'phi': float(phi), 'captured': False})

        dr1, dp1, du1 = deriv_light(r, phi, u_r)
        dr2, dp2, du2 = deriv_light(r + 0.5*dlambda*dr1, phi + 0.5*dlambda*dp1, u_r + 0.5*dlambda*du1)
        dr3, dp3, du3 = deriv_light(r + 0.5*dlambda*dr2, phi + 0.5*dlambda*dp2, u_r + 0.5*dlambda*du2)
        dr4, dp4, du4 = deriv_light(r + dlambda*dr3, phi + dlambda*dp3, u_r + dlambda*du3)

        r   += dlambda * (dr1 + 2*dr2 + 2*dr3 + dr4) / 6
        phi += dlambda * (dp1 + 2*dp2 + 2*dp3 + dp4) / 6
        u_r += dlambda * (du1 + 2*du2 + 2*du3 + du4) / 6

        if r > r_start * 1.1 and u_r > 0:
            # Ray escaping — continue a bit more then stop
            for _ in range(60):
                path.append({'r': float(r), 'phi': float(phi), 'captured': False})
                dr1, dp1, du1 = deriv_light(r, phi, u_r)
                r   += dlambda * dr1
                phi += dlambda * dp1
                u_r += dlambda * du1
                if r > r_start * 3:
                    break
            break

    return path


def spacetime_curvature_grid(rs, grid_size=20, r_max=15):
    """
    Compute a 2D curvature grid showing the embedding diagram (Flamm's paraboloid)
    z = 2*sqrt(rs*(r-rs)) for r > rs
    Returns grid points with z-displacement for visualization.
    """
    points = []
    for ix in range(grid_size):
        for iy in range(grid_size):
            x = (ix / (grid_size - 1) - 0.5) * 2 * r_max
            y = (iy / (grid_size - 1) - 0.5) * 2 * r_max
            r = math.sqrt(x**2 + y**2)
            if r <= rs:
                z = -5.0  # inside event horizon
            else:
                z = -2.0 * math.sqrt(rs * (r - rs))  # Flamm's paraboloid (dip)
            points.append({'x': x, 'y': y, 'r': r, 'z': z})
    return points


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.route('/api/info', methods=['GET'])
def info():
    return jsonify({
        'name': 'General Relativity Simulator',
        'version': '1.0',
        'endpoints': [
            '/api/schwarzschild',
            '/api/geodesic',
            '/api/light_ray',
            '/api/time_dilation',
            '/api/spacetime_grid',
            '/api/multi_geodesics',
        ]
    })


@app.route('/api/schwarzschild', methods=['GET'])
def schwarzschild():
    """Return Schwarzschild radius for a given mass (in solar masses)."""
    mass_solar = float(request.args.get('mass', 1.0))
    M = mass_solar * M_SUN
    rs = schwarzschild_radius(M)
    rs_km = rs / 1000
    return jsonify({
        'mass_solar': mass_solar,
        'mass_kg': M,
        'schwarzschild_radius_m': rs,
        'schwarzschild_radius_km': rs_km,
        'description': (
            f'A {mass_solar} solar-mass object has a Schwarzschild radius of '
            f'{rs_km:.3f} km. If compressed below this radius, it becomes a black hole.'
        )
    })


@app.route('/api/geodesic', methods=['POST'])
def geodesic():
    """
    Compute a massive-particle geodesic in Schwarzschild spacetime.
    Body JSON:
        r0       – initial radius (in units of rs)
        phi0     – initial angle (radians)
        dr_dtau  – initial radial velocity
        dphi_dtau– initial angular velocity
        rs       – Schwarzschild radius (dimensionless units, typically 1.0)
        steps    – integration steps (default 800)
    """
    data = request.get_json(force=True)
    rs_val   = float(data.get('rs', 1.0))
    r0       = float(data.get('r0', 6.0))          # ISCO ≈ 3rs
    phi0     = float(data.get('phi0', 0.0))
    dr_dtau  = float(data.get('dr_dtau', 0.0))
    dphi_dtau= float(data.get('dphi_dtau', 0.12))
    steps    = int(data.get('steps', 800))
    dtau     = float(data.get('dtau', 0.5))

    path = geodesic_rk4(r0, phi0, dr_dtau, dphi_dtau, rs_val, steps, dtau)

    # Convert polar → Cartesian
    cartesian = [
        {
            'x': p['r'] * math.cos(p['phi']),
            'y': p['r'] * math.sin(p['phi']),
            'r': p['r'],
            'phi': p['phi'],
            'captured': p['captured']
        }
        for p in path
    ]

    return jsonify({
        'path': cartesian,
        'rs': rs_val,
        'r0': r0,
        'steps_computed': len(cartesian),
        'captured': cartesian[-1]['captured'] if cartesian else False
    })


@app.route('/api/light_ray', methods=['POST'])
def light_ray():
    """
    Compute a null geodesic (light ray) deflected by Schwarzschild mass.
    Body JSON:
        b   – impact parameter (in units of rs)
        rs  – Schwarzschild radius (default 1.0)
        steps / dlambda – integration params
    """
    data = request.get_json(force=True)
    rs_val  = float(data.get('rs', 1.0))
    b       = float(data.get('b', 5.0))
    steps   = int(data.get('steps', 1200))
    dlambda = float(data.get('dlambda', 0.3))

    path = geodesic_light_rk4(b, rs_val, steps, dlambda)
    cartesian = [
        {
            'x': p['r'] * math.cos(p['phi']),
            'y': p['r'] * math.sin(p['phi']),
            'r': p['r'],
            'phi': p['phi'],
            'captured': p['captured']
        }
        for p in path
    ]

    deflection_approx = math.degrees(light_deflection_angle(b, rs_val))
    return jsonify({
        'path': cartesian,
        'impact_parameter': b,
        'rs': rs_val,
        'deflection_angle_deg': deflection_approx,
        'captured': cartesian[-1]['captured'] if cartesian else False
    })


@app.route('/api/time_dilation', methods=['GET'])
def time_dilation():
    """
    Return time dilation factors across a range of radii.
    Query: rs (default 1.0), r_min_factor (default 1.01), r_max_factor (default 20), points (default 200)
    """
    rs_val       = float(request.args.get('rs', 1.0))
    r_min_factor = float(request.args.get('r_min', 1.01))
    r_max_factor = float(request.args.get('r_max', 20.0))
    n_points     = int(request.args.get('points', 200))

    r_min = rs_val * r_min_factor
    r_max = rs_val * r_max_factor
    radii = np.linspace(r_min, r_max, n_points).tolist()

    data_points = []
    for r in radii:
        td = time_dilation_factor(r, rs_val)
        data_points.append({
            'r': r,
            'r_over_rs': r / rs_val,
            'dilation_factor': td,
            'time_ratio_percent': td * 100,
            'slower_by_percent': (1 - td) * 100
        })

    return jsonify({
        'rs': rs_val,
        'data': data_points,
        'description': 'dilation_factor=1 means same rate as infinity; 0 means time stops (event horizon)'
    })


@app.route('/api/spacetime_grid', methods=['GET'])
def spacetime_grid():
    """
    Return Flamm's paraboloid embedding grid for spacetime curvature visualization.
    Query: rs, grid_size, r_max
    """
    rs_val    = float(request.args.get('rs', 1.0))
    grid_size = int(request.args.get('grid_size', 22))
    r_max     = float(request.args.get('r_max', 14.0))

    grid = spacetime_curvature_grid(rs_val, grid_size, r_max)
    return jsonify({
        'rs': rs_val,
        'grid_size': grid_size,
        'r_max': r_max,
        'points': grid
    })


@app.route('/api/multi_geodesics', methods=['POST'])
def multi_geodesics():
    """
    Compute multiple geodesics at once (for orbit family visualization).
    Body JSON:
        rs       – Schwarzschild radius
        configs  – list of {r0, dphi_dtau, dr_dtau, color} dicts
        steps, dtau
    """
    data    = request.get_json(force=True)
    rs_val  = float(data.get('rs', 1.0))
    configs = data.get('configs', [])
    steps   = int(data.get('steps', 700))
    dtau    = float(data.get('dtau', 0.5))

    results = []
    for cfg in configs:
        r0        = float(cfg.get('r0', 6.0))
        dphi_dtau = float(cfg.get('dphi_dtau', 0.12))
        dr_dtau   = float(cfg.get('dr_dtau', 0.0))
        color     = cfg.get('color', '#ffffff')

        path = geodesic_rk4(r0, 0.0, dr_dtau, dphi_dtau, rs_val, steps, dtau)
        cartesian = [
            {
                'x': p['r'] * math.cos(p['phi']),
                'y': p['r'] * math.sin(p['phi']),
                'captured': p['captured']
            }
            for p in path
        ]
        results.append({'path': cartesian, 'color': color, 'r0': r0, 'captured': cartesian[-1]['captured'] if cartesian else False})

    return jsonify({'geodesics': results, 'rs': rs_val})


@app.route('/api/gravitational_waves', methods=['GET'])
def gravitational_waves():
    """
    Return a simulated gravitational wave strain h(t) for a binary inspiral.
    Very simplified chirp waveform.
    Query: m1, m2 (solar masses), duration (s), sample_rate
    """
    m1 = float(request.args.get('m1', 30.0))
    m2 = float(request.args.get('m2', 30.0))
    duration = float(request.args.get('duration', 2.0))
    sample_rate = int(request.args.get('sample_rate', 2048))

    M_total = (m1 + m2) * M_SUN
    M_chirp = ((m1 * m2)**0.6 / (m1 + m2)**0.2) * M_SUN  # Chirp mass

    t_arr = np.linspace(0, duration, int(duration * sample_rate))
    t_coal = duration  # coalescence at end

    strain = []
    for t in t_arr:
        tau = t_coal - t
        if tau <= 0:
            tau = 1e-10
        # GW frequency: f_gw = (1/pi) * (5/(256*tau))^(3/8) * (G*M_chirp/c^3)^(-5/8)
        # Simplified dimensionless chirp
        f_gw = 50.0 * (1.0 + (t / t_coal) ** 2) * min(1, tau**-0.375)
        # Amplitude grows as coalescence approaches
        A = 1e-21 * (1 + (t / t_coal) ** 3)
        h = float(A * np.cos(2 * np.pi * f_gw * t))
        strain.append({'t': float(t), 'h': h, 'f': float(f_gw)})

    return jsonify({
        'm1_solar': m1,
        'm2_solar': m2,
        'chirp_mass_solar': float(M_chirp / M_SUN),
        'data': strain[:2048]  # cap output size
    })


if __name__ == '__main__':
    print("=" * 60)
    print("  General Relativity Simulator  –  Backend API")
    print("=" * 60)
    print(f"  Speed of light     c = {c:.2e} m/s")
    print(f"  Grav. constant     G = {G:.3e} m^3/(kg*s^2)")
    print(f"  Solar mass     M_sun = {M_SUN:.3e} kg")
    rs_sun = schwarzschild_radius(M_SUN)
    print(f"  Sun's Schwarzschild radius = {rs_sun/1000:.2f} km")
    rs_bh = schwarzschild_radius(10 * M_SUN)
    print(f"  10M_sun black hole rs = {rs_bh/1000:.2f} km")
    print("=" * 60)
    print("  Running on http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000, host='0.0.0.0')
