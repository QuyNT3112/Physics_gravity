/* ═══════════════════════════════════════════════════════════════════════════
   main.js – General Relativity Simulator
   Handles: API calls, Canvas rendering, all tab simulations
   ════════════════════════════════════════════════════════════════════════════ */

const API = 'http://localhost:5000/api';

// ── Utilities ─────────────────────────────────────────────────────────────────

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
}

function updateLabel(el, labelId) {
  const v = parseFloat(el.value);
  document.getElementById(labelId).textContent =
    Number.isInteger(v) ? v : v.toFixed(el.step && el.step.includes('.') ? (el.step.split('.')[1] || '0').length : 2);
}

function showLoading(msg = 'Đang tích phân geodesic...') {
  const ov = document.getElementById('loading-overlay');
  ov.querySelector('p').textContent = msg;
  ov.classList.add('visible');
}
function hideLoading() {
  document.getElementById('loading-overlay').classList.remove('visible');
}

async function apiPost(endpoint, body) {
  const res = await fetch(API + endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiGet(endpoint, params = {}) {
  const url = new URL(API + endpoint);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ── Canvas Helpers ─────────────────────────────────────────────────────────────

function clearCanvas(canvas, bgColor = '#020810') {
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  return ctx;
}

function toCanvas(x, y, cx, cy, scale) {
  return { cx: cx + x * scale, cy: cy - y * scale };
}

function drawGrid(ctx, cx, cy, scale, W, H, color = 'rgba(50,80,120,0.25)') {
  ctx.strokeStyle = color;
  ctx.lineWidth = 0.5;
  const spacing = scale;
  for (let x = cx % spacing; x < W; x += spacing) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = cy % spacing; y < H; y += spacing) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
  // Axes
  ctx.strokeStyle = 'rgba(100,150,200,0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, H); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(W, cy); ctx.stroke();
}

function drawBlackHoleIcon(ctx, cx, cy, rs, scale) {
  const pixRs = rs * scale;
  // Accretion disk glow
  const diskGrad = ctx.createRadialGradient(cx, cy, pixRs * 0.8, cx, cy, pixRs * 4);
  diskGrad.addColorStop(0,   'rgba(255,140,0,0.15)');
  diskGrad.addColorStop(0.4, 'rgba(255,60,0,0.08)');
  diskGrad.addColorStop(1,   'rgba(0,0,0,0)');
  ctx.fillStyle = diskGrad;
  ctx.beginPath();
  ctx.ellipse(cx, cy, pixRs * 4, pixRs * 1.5, 0, 0, Math.PI * 2);
  ctx.fill();

  // Event horizon glow
  const bhGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, pixRs * 2.5);
  bhGrad.addColorStop(0,   'rgba(100,0,200,0.25)');
  bhGrad.addColorStop(0.5, 'rgba(50,0,150,0.15)');
  bhGrad.addColorStop(1,   'rgba(0,0,0,0)');
  ctx.fillStyle = bhGrad;
  ctx.beginPath(); ctx.arc(cx, cy, pixRs * 2.5, 0, Math.PI * 2); ctx.fill();

  // Photon sphere ring
  ctx.strokeStyle = 'rgba(200,150,255,0.3)';
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 5]);
  ctx.beginPath(); ctx.arc(cx, cy, pixRs * 1.5 * scale, 0, Math.PI * 2); ctx.stroke();
  ctx.setLineDash([]);

  // Black hole itself
  ctx.fillStyle = '#000';
  ctx.beginPath(); ctx.arc(cx, cy, pixRs, 0, Math.PI * 2); ctx.fill();

  // Inner glow ring
  ctx.strokeStyle = 'rgba(168,85,247,0.8)';
  ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cy, pixRs, 0, Math.PI * 2); ctx.stroke();
}

// ══ STARFIELD ════════════════════════════════════════════════════════════════

(function initStarfield() {
  const canvas = document.getElementById('starfield-canvas');
  const ctx = canvas.getContext('2d');
  let stars = [];
  let W, H;

  function resize() {
    W = canvas.width = canvas.offsetWidth;
    H = canvas.height = canvas.offsetHeight;
    stars = Array.from({ length: 300 }, () => ({
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 1.5 + 0.2,
      alpha: Math.random(),
      speed: Math.random() * 0.004 + 0.001,
      phase: Math.random() * Math.PI * 2
    }));
  }

  function animate(t) {
    ctx.clearRect(0, 0, W, H);
    stars.forEach(s => {
      const a = s.alpha * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase));
      ctx.fillStyle = `rgba(200,220,255,${a})`;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    });
    requestAnimationFrame(animate);
  }

  resize();
  window.addEventListener('resize', resize);
  requestAnimationFrame(animate);
})();

// ══ TAB: GEODESIC ════════════════════════════════════════════════════════════

async function runGeodesic() {
  const r0       = parseFloat(document.getElementById('geo-r0').value);
  const dphi_dtau= parseFloat(document.getElementById('geo-dphi').value);
  const dr_dtau  = parseFloat(document.getElementById('geo-dr').value);
  const steps    = parseInt(document.getElementById('geo-steps').value);
  const rs       = 1.0;

  showLoading('Đang tích phân geodesic Schwarzschild...');
  try {
    const data = await apiPost('/geodesic', { rs, r0, phi0: 0, dr_dtau, dphi_dtau, steps, dtau: 0.5 });
    hideLoading();
    drawGeodesicPath(data, rs);
    updateGeoInfo(data, r0, dphi_dtau);
  } catch (e) {
    hideLoading();
    alert('Lỗi kết nối backend: ' + e.message);
  }
}

async function runMultiGeodesics() {
  const rs = 1.0;
  const configs = [
    { r0: 3.5,  dphi_dtau: 0.20, dr_dtau:  0.0,   color: '#ff6b35' },
    { r0: 5.0,  dphi_dtau: 0.15, dr_dtau:  0.0,   color: '#f5c842' },
    { r0: 7.0,  dphi_dtau: 0.12, dr_dtau:  0.0,   color: '#39ff14' },
    { r0: 10.0, dphi_dtau: 0.10, dr_dtau:  0.0,   color: '#00e5ff' },
    { r0: 5.0,  dphi_dtau: 0.12, dr_dtau:  0.08,  color: '#a855f7' },
    { r0: 4.0,  dphi_dtau: 0.25, dr_dtau: -0.05,  color: '#ff4488' },
  ];
  showLoading('Tích phân họ quỹ đạo...');
  try {
    const data = await apiPost('/multi_geodesics', { rs, configs, steps: 700, dtau: 0.5 });
    hideLoading();
    drawMultiGeodesics(data.geodesics, rs);
  } catch (e) {
    hideLoading();
    alert('Lỗi kết nối backend: ' + e.message);
  }
}

function drawGeodesicPath(data, rs) {
  const canvas = document.getElementById('canvas-geodesic');
  const ctx = clearCanvas(canvas);
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;

  const path = data.path;
  if (!path || path.length === 0) return;

  const maxR = Math.max(...path.map(p => Math.sqrt(p.x**2 + p.y**2))) * 1.1;
  const scale = (Math.min(W, H) / 2 - 20) / maxR;

  drawGrid(ctx, cx, cy, scale, W, H);
  drawBlackHoleIcon(ctx, cx, cy, rs, scale);

  // Draw path with color gradient
  if (path.length > 1) {
    for (let i = 1; i < path.length; i++) {
      const p0 = path[i - 1], p1 = path[i];
      const t = i / path.length;
      const hue = 180 + t * 160;
      ctx.strokeStyle = `hsla(${hue}, 90%, 65%, ${0.4 + t * 0.6})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx + p0.x * scale, cy - p0.y * scale);
      ctx.lineTo(cx + p1.x * scale, cy - p1.y * scale);
      ctx.stroke();
    }

    // Starting point
    const p0 = path[0];
    ctx.fillStyle = '#39ff14';
    ctx.shadowColor = '#39ff14';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(cx + p0.x * scale, cy - p0.y * scale, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // End point
    const pe = path[path.length - 1];
    ctx.fillStyle = data.captured ? '#ff4444' : '#00e5ff';
    ctx.shadowColor = ctx.fillStyle;
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(cx + pe.x * scale, cy - pe.y * scale, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  // Labels
  ctx.fillStyle = 'rgba(100,150,200,0.7)';
  ctx.font = '11px JetBrains Mono, monospace';
  ctx.fillText(`rs = ${rs}`, 12, 22);
  ctx.fillText(`r₀ = ${data.r0.toFixed(1)} rs`, 12, 36);
  ctx.fillText(`Pts: ${path.length}`, 12, 50);
  if (data.captured) {
    ctx.fillStyle = '#ff4444';
    ctx.font = 'bold 13px Outfit';
    ctx.fillText('⚠ BỊ HÚT VÀO HỐ ĐEN', 12, H - 16);
  }
}

function drawMultiGeodesics(geodesics, rs) {
  const canvas = document.getElementById('canvas-geodesic');
  const ctx = clearCanvas(canvas);
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;

  let maxR = 0;
  geodesics.forEach(g => {
    g.path.forEach(p => { maxR = Math.max(maxR, Math.sqrt(p.x**2 + p.y**2)); });
  });
  maxR = (maxR || 10) * 1.1;
  const scale = (Math.min(W, H) / 2 - 20) / maxR;

  drawGrid(ctx, cx, cy, scale, W, H);
  drawBlackHoleIcon(ctx, cx, cy, rs, scale);

  geodesics.forEach(g => {
    if (g.path.length < 2) return;
    ctx.strokeStyle = g.color;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = g.color;
    ctx.shadowBlur = 4;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.moveTo(cx + g.path[0].x * scale, cy - g.path[0].y * scale);
    g.path.forEach(p => ctx.lineTo(cx + p.x * scale, cy - p.y * scale));
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;
  });

  ctx.fillStyle = 'rgba(100,150,200,0.7)';
  ctx.font = '11px JetBrains Mono, monospace';
  ctx.fillText(`Họ ${geodesics.length} quỹ đạo`, 12, 22);
}

function updateGeoInfo(data, r0, dphi) {
  const div = document.getElementById('geo-info');
  const rs = 1.0;
  const isco = 3 * rs;
  let desc = '';
  if (data.captured)      desc = '🔴 Vật bị hút vào hố đen (r₀ < ISCO hoặc vận tốc quá nhỏ)';
  else if (r0 <= isco)    desc = '⚠️ Gần ISCO – quỹ đạo tròn nhỏ nhất ổn định ≈ 3rs';
  else                    desc = '✅ Quỹ đạo giải thoát hoặc tuần hoàn ổn định';
  div.innerHTML = `<p>${desc}</p><p class="hint">ISCO = ${isco.toFixed(1)} rs = bán kính quỹ đạo ổn định nhỏ nhất</p>`;
}

// ══ TAB: LIGHT RAY ════════════════════════════════════════════════════════════

async function runLightRay() {
  const rs = 1.0;
  const multi = document.getElementById('lr-multi').checked;

  showLoading('Tính null geodesic (ánh sáng)...');
  try {
    if (multi) {
      const bs = [2.0, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0];
      const results = await Promise.all(
        bs.map(b => apiPost('/light_ray', { rs, b, steps: 1000, dlambda: 0.3 }))
      );
      hideLoading();
      drawMultiLightRays(results, rs);
    } else {
      const b = parseFloat(document.getElementById('lr-b').value);
      const data = await apiPost('/light_ray', { rs, b, steps: 1000, dlambda: 0.3 });
      hideLoading();
      drawLightRay([data], rs);
      showDeflection(data.deflection_angle_deg, data.captured);
    }
  } catch (e) {
    hideLoading();
    alert('Lỗi kết nối backend: ' + e.message);
  }
}

function previewLightRay() { /* live update label only */ }

function drawLightRay(results, rs) {
  drawMultiLightRays(results, rs);
  if (results.length === 1) showDeflection(results[0].deflection_angle_deg, results[0].captured);
}

function drawMultiLightRays(results, rs) {
  const canvas = document.getElementById('canvas-lightray');
  const ctx = clearCanvas(canvas);
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;

  let maxR = 0;
  results.forEach(r => r.path.forEach(p => { maxR = Math.max(maxR, Math.sqrt(p.x**2 + p.y**2)); }));
  maxR = Math.max(maxR, 20) * 1.05;
  const scale = (Math.min(W, H) / 2 - 20) / maxR;

  drawGrid(ctx, cx, cy, scale, W, H);
  drawBlackHoleIcon(ctx, cx, cy, rs, scale);

  const colors = ['#ff6b35','#f5c842','#39ff14','#00e5ff','#a855f7','#ff4488','#00bcd4'];

  results.forEach((data, i) => {
    if (!data.path || data.path.length < 2) return;
    const color = colors[i % colors.length];
    ctx.strokeStyle = data.captured ? '#ff4444' : color;
    ctx.lineWidth = 1.8;
    ctx.shadowColor = ctx.strokeStyle;
    ctx.shadowBlur = 5;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    const p0 = data.path[0];
    ctx.moveTo(cx + p0.x * scale, cy - p0.y * scale);
    data.path.forEach(p => ctx.lineTo(cx + p.x * scale, cy - p.y * scale));
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;

    // Impact parameter label
    if (results.length > 1) {
      const pe = data.path[Math.min(5, data.path.length - 1)];
      ctx.fillStyle = color;
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(`b=${data.impact_parameter}`, cx + pe.x * scale + 4, cy - pe.y * scale);
    }
  });

  ctx.fillStyle = 'rgba(100,150,200,0.7)';
  ctx.font = '11px JetBrains Mono, monospace';
  ctx.fillText('Thấu kính hấp dẫn – Null Geodesics', 12, 22);

  // Photon sphere label
  const photonR = 1.5 * rs * scale;
  ctx.strokeStyle = 'rgba(200,150,255,0.4)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 6]);
  ctx.beginPath(); ctx.arc(cx, cy, photonR, 0, Math.PI * 2); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(200,150,255,0.7)';
  ctx.font = '9px Outfit, sans-serif';
  ctx.fillText('photon sphere', cx + photonR + 3, cy);
}

function showDeflection(deg, captured) {
  const div = document.getElementById('deflection-display');
  const val = document.getElementById('def-angle');
  div.style.display = 'block';
  if (captured) {
    val.textContent = 'Bị hút vào';
    val.style.color = '#ff4444';
  } else {
    val.textContent = deg.toFixed(4) + '°';
    val.style.color = '#a855f7';
  }
}

// ══ TAB: TIME DILATION ════════════════════════════════════════════════════════

let timeDilationData = null;

async function runTimeDilation() {
  const rs  = 1.0;
  const rmax = parseFloat(document.getElementById('td-rmax').value);
  try {
    const data = await apiGet('/time_dilation', { rs, r_min: 1.01, r_max: rmax, points: 300 });
    timeDilationData = data;
    drawTimeDilationChart(data);
    updateProbe();
  } catch (e) {
    console.error(e);
  }
}

function drawTimeDilationChart(data) {
  const canvas = document.getElementById('canvas-timedilation');
  const ctx = clearCanvas(canvas);
  const W = canvas.width, H = canvas.height;
  const pad = { top: 30, right: 20, bottom: 50, left: 60 };

  const pts = data.data;
  const xMin = pts[0].r_over_rs, xMax = pts[pts.length - 1].r_over_rs;
  const yMin = 0, yMax = 1;

  function px(rx) { return pad.left + (rx - xMin) / (xMax - xMin) * (W - pad.left - pad.right); }
  function py(y)  { return pad.top + (1 - (y - yMin) / (yMax - yMin)) * (H - pad.top - pad.bottom); }

  // Grid
  ctx.strokeStyle = 'rgba(50,80,120,0.3)';
  ctx.lineWidth = 0.5;
  for (let y = 0; y <= 1; y += 0.1) {
    ctx.beginPath(); ctx.moveTo(pad.left, py(y)); ctx.lineTo(W - pad.right, py(y)); ctx.stroke();
  }
  for (let x = 1; x <= xMax; x += 2) {
    ctx.beginPath(); ctx.moveTo(px(x), pad.top); ctx.lineTo(px(x), H - pad.bottom); ctx.stroke();
  }

  // Gradient fill
  const grad = ctx.createLinearGradient(0, pad.top, 0, H - pad.bottom);
  grad.addColorStop(0,   'rgba(0,229,255,0.25)');
  grad.addColorStop(0.7, 'rgba(0,229,255,0.05)');
  grad.addColorStop(1,   'rgba(0,229,255,0)');

  ctx.beginPath();
  ctx.moveTo(px(pts[0].r_over_rs), py(pts[0].dilation_factor));
  pts.forEach(p => ctx.lineTo(px(p.r_over_rs), py(p.dilation_factor)));
  ctx.lineTo(px(pts[pts.length - 1].r_over_rs), py(yMin));
  ctx.lineTo(px(pts[0].r_over_rs), py(yMin));
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Main curve
  ctx.strokeStyle = '#00e5ff';
  ctx.lineWidth = 2.5;
  ctx.shadowColor = '#00e5ff';
  ctx.shadowBlur = 8;
  ctx.beginPath();
  ctx.moveTo(px(pts[0].r_over_rs), py(pts[0].dilation_factor));
  pts.forEach(p => ctx.lineTo(px(p.r_over_rs), py(p.dilation_factor)));
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Asymptote at y=1
  ctx.strokeStyle = 'rgba(245,200,66,0.4)';
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 4]);
  ctx.beginPath(); ctx.moveTo(pad.left, py(1)); ctx.lineTo(W - pad.right, py(1)); ctx.stroke();
  ctx.setLineDash([]);

  // Axes labels
  ctx.fillStyle = 'rgba(140,170,200,0.8)';
  ctx.font = '11px JetBrains Mono, monospace';
  ctx.textAlign = 'right';
  for (let y = 0; y <= 1; y += 0.2) {
    ctx.fillText(y.toFixed(1), pad.left - 6, py(y) + 4);
  }
  ctx.textAlign = 'center';
  for (let x = 2; x <= xMax; x += 2) {
    ctx.fillText(x + 'rs', px(x), H - pad.bottom + 18);
  }
  ctx.fillStyle = 'rgba(200,220,255,0.6)';
  ctx.font = '11px Outfit, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Khoảng cách từ hố đen (× rs)', W / 2, H - 8);
  ctx.save();
  ctx.translate(14, H / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Tốc độ đồng hồ (dτ/dt)', 0, 0);
  ctx.restore();

  ctx.textAlign = 'left';
  ctx.fillText('dτ/dt = 1 (∞)', W - pad.right - 80, py(1) - 6);

  // Event horizon marker
  ctx.strokeStyle = 'rgba(255,68,68,0.6)';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(px(1), pad.top); ctx.lineTo(px(1), H - pad.bottom); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#ff4444';
  ctx.font = '10px Outfit';
  ctx.fillText('r=rs', px(1) + 4, pad.top + 14);
}

function updateProbe() {
  if (!timeDilationData) return;
  const probeR = parseFloat(document.getElementById('td-probe').value);
  document.getElementById('td-probe-val').textContent = probeR.toFixed(2);
  const rs = 1.0;
  const factor = Math.sqrt(Math.max(0, 1 - rs / probeR));
  document.getElementById('probe-rate').textContent = factor.toFixed(5);
  document.getElementById('probe-slow').textContent = ((1 - factor) * 100).toFixed(3) + '%';
  const yearFar = (1 / factor).toFixed(4);
  document.getElementById('probe-year').textContent = `${yearFar} năm`;
  drawClockAnimation(factor, probeR);
}

function drawClockAnimation(factor, rOverRs) {
  const canvas = document.getElementById('canvas-clocks');
  const ctx = clearCanvas(canvas, '#030a18');
  const W = canvas.width, H = canvas.height;

  // Two clocks side by side
  const now = Date.now() / 1000;

  function drawClock(x, y, r, speed, label, color) {
    // Clock face
    const grad = ctx.createRadialGradient(x, y, 0, x, y, r);
    grad.addColorStop(0, `rgba(20,40,70,0.9)`);
    grad.addColorStop(1, `rgba(5,10,25,0.9)`);
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.shadowBlur = 0;

    // Tick marks
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
      const inner = i % 3 === 0 ? r * 0.8 : r * 0.88;
      ctx.strokeStyle = color;
      ctx.lineWidth = i % 3 === 0 ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * inner, y + Math.sin(a) * inner);
      ctx.lineTo(x + Math.cos(a) * r * 0.95, y + Math.sin(a) * r * 0.95);
      ctx.stroke();
    }

    // Second hand
    const sAngle = (now * speed) * Math.PI * 2 - Math.PI / 2;
    ctx.strokeStyle = '#ff4444';
    ctx.lineWidth = 1.5;
    ctx.shadowColor = '#ff4444';
    ctx.shadowBlur = 5;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(sAngle) * r * 0.88, y + Math.sin(sAngle) * r * 0.88);
    ctx.stroke();

    // Minute hand
    const mAngle = (now * speed / 60) * Math.PI * 2 - Math.PI / 2;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowBlur = 3;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + Math.cos(mAngle) * r * 0.7, y + Math.sin(mAngle) * r * 0.7);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Center dot
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();

    // Label
    ctx.fillStyle = color;
    ctx.font = '11px Outfit, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label, x, y + r + 20);
  }

  drawClock(W * 0.28, H / 2, 60, factor, `r = ${rOverRs.toFixed(1)} rs  (tốc độ ${(factor*100).toFixed(1)}%)`, '#ff6b35');
  drawClock(W * 0.72, H / 2, 60, 1,      'r = ∞  (xa vô cùng – 100%)', '#00e5ff');

  // Connecting arrow
  ctx.fillStyle = 'rgba(200,200,255,0.5)';
  ctx.font = '13px Outfit';
  ctx.textAlign = 'center';
  ctx.fillText('⟵ Đồng hồ chậm hơn  ·  Hố đen ·  Đồng hồ nhanh hơn ⟶', W / 2, H - 12);

  // Animate
  setTimeout(() => updateProbe(), 100);
}

// ══ TAB: CURVATURE GRID ════════════════════════════════════════════════════════

async function runCurvature() {
  const rs    = parseFloat(document.getElementById('curv-rs').value);
  const size  = parseInt(document.getElementById('curv-size').value);
  const rmax  = parseFloat(document.getElementById('curv-rmax').value) * rs;
  try {
    const data = await apiGet('/spacetime_grid', { rs, grid_size: size, r_max: rmax });
    drawCurvatureGrid(data);
  } catch (e) {
    console.error(e);
  }
}

function drawCurvatureGrid(data) {
  const canvas = document.getElementById('canvas-curvature');
  const ctx = clearCanvas(canvas);
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;

  const pts = data.points;
  if (!pts || pts.length === 0) return;
  const N = data.grid_size;
  const rs = data.rs;
  const rMax = data.r_max;

  const scale = (Math.min(W, H) / 2 - 20) / rMax;
  const zRange = Math.abs(Math.min(...pts.map(p => p.z)));

  // Draw grid lines (rows)
  for (let row = 0; row < N; row++) {
    ctx.beginPath();
    for (let col = 0; col < N; col++) {
      const p = pts[row * N + col];
      const px = cx + p.x * scale;
      // Project z as vertical offset (pseudo-3D isometric-ish)
      const py = cy - p.y * scale * 0.6 + p.z * scale * 0.4;
      const rNorm = Math.min(p.r / (rMax * 0.8), 1);
      const depth = Math.min(Math.abs(p.z) / (zRange + 0.1), 1);
      ctx.strokeStyle = `hsla(${260 - depth * 120}, 80%, ${40 + rNorm * 40}%, ${0.5 + rNorm * 0.4})`;
      ctx.lineWidth = 1 + depth * 0.5;
      if (col === 0) ctx.moveTo(px, py);
      else           ctx.lineTo(px, py);
    }
    ctx.stroke();
  }

  // Draw grid lines (cols)
  for (let col = 0; col < N; col++) {
    ctx.beginPath();
    for (let row = 0; row < N; row++) {
      const p = pts[row * N + col];
      const px = cx + p.x * scale;
      const py = cy - p.y * scale * 0.6 + p.z * scale * 0.4;
      const rNorm = Math.min(p.r / (rMax * 0.8), 1);
      const depth = Math.min(Math.abs(p.z) / (zRange + 0.1), 1);
      ctx.strokeStyle = `hsla(${260 - depth * 120}, 80%, ${40 + rNorm * 40}%, ${0.5 + rNorm * 0.4})`;
      ctx.lineWidth = 1 + depth * 0.5;
      if (row === 0) ctx.moveTo(px, py);
      else           ctx.lineTo(px, py);
    }
    ctx.stroke();
  }

  // Draw event horizon
  const ehR = rs * scale;
  ctx.strokeStyle = 'rgba(168,85,247,0.8)';
  ctx.lineWidth = 2;
  ctx.shadowColor = '#a855f7';
  ctx.shadowBlur = 12;
  ctx.beginPath();
  ctx.arc(cx, cy, ehR, 0, Math.PI * 2);
  ctx.stroke();
  ctx.shadowBlur = 0;

  ctx.fillStyle = '#000';
  ctx.beginPath(); ctx.arc(cx, cy, ehR, 0, Math.PI * 2); ctx.fill();

  // Labels
  ctx.fillStyle = 'rgba(140,180,220,0.7)';
  ctx.font = '11px JetBrains Mono, monospace';
  ctx.textAlign = 'left';
  ctx.fillText(`rs = ${rs}  ·  Grid ${N}×${N}`, 12, 22);
  ctx.fillText('Flamm Paraboloid embedding', 12, 36);
}

// ══ TAB: GRAVITATIONAL WAVES ══════════════════════════════════════════════════

let waveData = null;
let waveAnim = null;
let waveOffset = 0;

async function runGravWaves() {
  const m1 = parseFloat(document.getElementById('gw-m1').value);
  const m2 = parseFloat(document.getElementById('gw-m2').value);
  showLoading('Mô phỏng sóng hấp dẫn...');
  try {
    const data = await apiGet('/gravitational_waves', { m1, m2, duration: 2, sample_rate: 2048 });
    waveData = data;
    hideLoading();
    document.getElementById('gw-stats').style.display = 'flex';
    document.getElementById('gw-chirp').textContent = data.chirp_mass_solar.toFixed(2) + ' M☉';
    drawWaveform(data.data, 0);
    drawWaveMap(data.data);
  } catch (e) {
    hideLoading();
    alert('Lỗi: ' + e.message);
  }
}

function drawWaveform(pts, offset) {
  const canvas = document.getElementById('canvas-waves');
  const ctx = clearCanvas(canvas, '#020810');
  const W = canvas.width, H = canvas.height;
  const pad = { l: 50, r: 20, t: 30, b: 40 };

  const visible = pts.slice(offset, offset + 600);
  if (visible.length < 2) return;

  const maxH = Math.max(...visible.map(p => Math.abs(p.h))) || 1e-21;
  const tMin = visible[0].t, tMax = visible[visible.length - 1].t;

  function px(t) { return pad.l + (t - tMin) / (tMax - tMin) * (W - pad.l - pad.r); }
  function py(h) { return H / 2 - (h / maxH) * (H / 2 - pad.t - 10); }

  // Grid
  ctx.strokeStyle = 'rgba(50,80,120,0.25)';
  ctx.lineWidth = 0.5;
  for (let y = -1; y <= 1; y += 0.5) {
    ctx.beginPath(); ctx.moveTo(pad.l, py(y * maxH)); ctx.lineTo(W - pad.r, py(y * maxH)); ctx.stroke();
  }

  // Centre line
  ctx.strokeStyle = 'rgba(100,150,200,0.3)';
  ctx.beginPath(); ctx.moveTo(pad.l, H / 2); ctx.lineTo(W - pad.r, H / 2); ctx.stroke();

  // Gradient fill
  const fillGrad = ctx.createLinearGradient(0, pad.t, 0, H - pad.b);
  fillGrad.addColorStop(0,   'rgba(0,229,255,0.18)');
  fillGrad.addColorStop(0.5, 'rgba(0,229,255,0.04)');
  fillGrad.addColorStop(1,   'rgba(0,229,255,0.18)');

  ctx.beginPath();
  ctx.moveTo(px(visible[0].t), H / 2);
  visible.forEach(p => ctx.lineTo(px(p.t), py(p.h)));
  ctx.lineTo(px(visible[visible.length - 1].t), H / 2);
  ctx.closePath();
  ctx.fillStyle = fillGrad;
  ctx.fill();

  // Chirp line — color encodes frequency
  for (let i = 1; i < visible.length; i++) {
    const p0 = visible[i - 1], p1 = visible[i];
    const frac = i / visible.length;
    const hue = 200 - frac * 140;
    ctx.strokeStyle = `hsl(${hue}, 90%, 65%)`;
    ctx.lineWidth = 1.8;
    ctx.shadowColor = `hsl(${hue}, 90%, 65%)`;
    ctx.shadowBlur = 4;
    ctx.beginPath();
    ctx.moveTo(px(p0.t), py(p0.h));
    ctx.lineTo(px(p1.t), py(p1.h));
    ctx.stroke();
  }
  ctx.shadowBlur = 0;

  // Axes
  ctx.fillStyle = 'rgba(140,170,200,0.7)';
  ctx.font = '10px JetBrains Mono, monospace';
  ctx.textAlign = 'center';
  ctx.fillText('Thời gian (s)', W / 2, H - 8);
  ctx.fillText(tMin.toFixed(2), pad.l, H - pad.b + 16);
  ctx.fillText(tMax.toFixed(2), W - pad.r, H - pad.b + 16);
  ctx.textAlign = 'left';
  ctx.fillText('h(t)  GW strain', pad.l, pad.t);
}

function drawWaveMap(pts) {
  const canvas = document.getElementById('canvas-wavemap');
  const ctx = clearCanvas(canvas, '#020810');
  const W = canvas.width, H = canvas.height;
  const pad = 20;

  // 2D spectrogram-like view: x=time, y=frequency bands, color=amplitude
  const N = pts.length;
  const blockW = (W - 2 * pad) / N;

  pts.forEach((p, i) => {
    const f = p.f;
    const normF = Math.min(f / 400, 1);
    const normA = Math.min(Math.abs(p.h) / 1e-20, 1);
    const hue = 260 - normF * 200;
    const alpha = 0.2 + normA * 0.8;
    ctx.fillStyle = `hsla(${hue}, 90%, 60%, ${alpha})`;
    const x = pad + i * blockW;
    const barH = (H - 2 * pad) * normF;
    ctx.fillRect(x, H - pad - barH, Math.max(blockW, 1), barH);
  });

  ctx.fillStyle = 'rgba(140,170,200,0.7)';
  ctx.font = '10px JetBrains Mono, monospace';
  ctx.textAlign = 'left';
  ctx.fillText('Chirp Spectrogram  –  x: thời gian  y: tần số GW', pad, pad + 12);
}

function animateWaves() {
  if (!waveData) { runGravWaves(); return; }
  if (waveAnim) { clearInterval(waveAnim); waveAnim = null; return; }
  waveOffset = 0;
  waveAnim = setInterval(() => {
    waveOffset += 20;
    if (waveOffset >= waveData.data.length - 600) {
      waveOffset = 0;
    }
    drawWaveform(waveData.data, waveOffset);
  }, 50);
}

// ══ BLACK HOLE CALCULATOR ═════════════════════════════════════════════════════

let bhAnimFrame = null;
let bhAngle = 0;

function setMass(m, label) {
  document.getElementById('bh-mass').value = m;
}

async function calcBlackHole() {
  const mass = parseFloat(document.getElementById('bh-mass').value);
  if (isNaN(mass) || mass <= 0) return;

  try {
    const data = await apiGet('/schwarzschild', { mass });
    document.getElementById('bh-result').style.display = 'block';

    const rs = data.schwarzschild_radius_km;
    document.getElementById('bh-rs').textContent = rs >= 1 ? rs.toFixed(3) + ' km' : (rs * 1000).toFixed(3) + ' m';

    // Hawking temperature T = ħc³/(8πGMk_B)
    const M_kg = data.mass_kg;
    const hbar = 1.055e-34, c = 3e8, G = 6.674e-11, kB = 1.38e-23;
    const T_H = (hbar * c**3) / (8 * Math.PI * G * M_kg * kB);
    document.getElementById('bh-hawking').textContent = T_H < 1e-6
      ? T_H.toExponential(3) + ' K'
      : T_H.toFixed(6) + ' K';

    // What to compress solar-like objects
    let compress;
    const rs_m = data.schwarzschild_radius_m;
    if (rs_m < 1)      compress = (rs_m * 100).toFixed(2) + ' cm';
    else if (rs_m < 1000) compress = rs_m.toFixed(2) + ' m';
    else               compress = data.schwarzschild_radius_km.toFixed(3) + ' km';
    document.getElementById('bh-compress').textContent = compress;

    document.getElementById('bh-desc').textContent = data.description;

    animateBlackHoleCanvas(data.schwarzschild_radius_m);
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

function animateBlackHoleCanvas(rs_m) {
  if (bhAnimFrame) cancelAnimationFrame(bhAnimFrame);
  const canvas = document.getElementById('canvas-blackhole');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;

  function frame() {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#020810';
    ctx.fillRect(0, 0, W, H);

    bhAngle += 0.003;

    // Outer space glow
    const spaceGrad = ctx.createRadialGradient(cx, cy, 20, cx, cy, W / 2);
    spaceGrad.addColorStop(0, 'rgba(80,0,160,0.3)');
    spaceGrad.addColorStop(0.4, 'rgba(0,20,60,0.2)');
    spaceGrad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = spaceGrad;
    ctx.fillRect(0, 0, W, H);

    // Accretion disk (rotating ellipse rings)
    for (let ring = 3; ring >= 1; ring--) {
      const rr = ring * 38;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(bhAngle * (ring % 2 === 0 ? 1 : -1));
      const diskGrad = ctx.createLinearGradient(-rr, 0, rr, 0);
      diskGrad.addColorStop(0,   `hsla(${20 + ring * 15}, 100%, 60%, 0.0)`);
      diskGrad.addColorStop(0.3, `hsla(${20 + ring * 15}, 100%, 60%, ${0.4 / ring})`);
      diskGrad.addColorStop(0.5, `hsla(${20 + ring * 15}, 100%, 70%, ${0.6 / ring})`);
      diskGrad.addColorStop(0.7, `hsla(${20 + ring * 15}, 100%, 60%, ${0.4 / ring})`);
      diskGrad.addColorStop(1,   `hsla(${20 + ring * 15}, 100%, 60%, 0.0)`);
      ctx.strokeStyle = diskGrad;
      ctx.lineWidth = 4 / ring;
      ctx.beginPath();
      ctx.ellipse(0, 0, rr, rr * 0.3, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // Event horizon
    const evGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 55);
    evGrad.addColorStop(0, '#000');
    evGrad.addColorStop(0.85, '#000');
    evGrad.addColorStop(1, 'rgba(100,0,200,0.5)');
    ctx.fillStyle = evGrad;
    ctx.beginPath(); ctx.arc(cx, cy, 55, 0, Math.PI * 2); ctx.fill();

    // Photon ring glow
    ctx.strokeStyle = `rgba(200,150,255,${0.4 + 0.2 * Math.sin(bhAngle * 3)})`;
    ctx.lineWidth = 2;
    ctx.shadowColor = '#a855f7';
    ctx.shadowBlur = 15;
    ctx.beginPath(); ctx.arc(cx, cy, 58, 0, Math.PI * 2); ctx.stroke();
    ctx.shadowBlur = 0;

    bhAnimFrame = requestAnimationFrame(frame);
  }
  frame();
}

// ══ INIT ══════════════════════════════════════════════════════════════════════

window.addEventListener('DOMContentLoaded', () => {
  runTimeDilation();
  runCurvature();

  // Auto-draw initial geodesic demo
  setTimeout(() => {
    runGeodesic();
  }, 800);

  // Black hole canvas preview
  animateBlackHoleCanvas(3000);

  // Preset light ray
  setTimeout(runLightRay, 1200);
});
