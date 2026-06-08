# 🌌 Mô Phỏng Thuyết Tương Đối Rộng

> **General Relativity Interactive Simulator**  
> Mô phỏng tương tác các hiện tượng vật lý của Thuyết Tương Đối Rộng (GTR) bằng Python + HTML5 Canvas.

---

## 📋 Mục Lục

- [Giới Thiệu](#-giới-thiệu)
- [Các Khái Niệm Vật Lý](#-các-khái-niệm-vật-lý)
- [Tính Năng](#-tính-năng)
- [Cấu Trúc Dự Án](#-cấu-trúc-dự-án)
- [Yêu Cầu Hệ Thống](#-yêu-cầu-hệ-thống)
- [Cài Đặt & Chạy](#-cài-đặt--chạy)
- [API Backend](#-api-backend)
- [Chi Tiết Từng Module](#-chi-tiết-từng-module)
- [Data Engineering & Database](#-data-engineering--database)
- [Phương Pháp Số](#-phương-pháp-số)
- [Tài Liệu Tham Khảo](#-tài-liệu-tham-khảo)

---

## 🔭 Giới Thiệu

Dự án này là một web app mô phỏng tương tác **Thuyết Tương Đối Rộng** (General Theory of Relativity) của Albert Einstein (1915). Người dùng có thể trực tiếp thay đổi các tham số vật lý và quan sát kết quả ngay trên trình duyệt.

### Phương trình trường Einstein

```
G_μν + Λg_μν = (8πG / c⁴) · T_μν
```

Phương trình này mô tả cách **khối lượng–năng lượng** (vế phải) làm cong **không-thời gian** (vế trái). Đây là nền tảng của toàn bộ mô phỏng.

### Metric Schwarzschild

Nghiệm ngoài chân không của phương trình Einstein quanh một vật thể cầu đối xứng, không quay:

```
ds² = −(1 − rs/r)c²dt² + dr²/(1 − rs/r) + r²dΩ²
```

Trong đó:
- `rs = 2GM/c²` — bán kính Schwarzschild
- `r` — khoảng cách từ tâm khối lượng
- `dΩ²` — phần tử góc khối

---

## ⚛️ Các Khái Niệm Vật Lý

### 1. 🌀 Độ Cong Không-Thời Gian & Trắc Địa (Geodesic)

Trong Thuyết Tương Đối Rộng, vật thể không bị "kéo" bởi lực hấp dẫn mà di chuyển theo **đường ngắn nhất (geodesic)** trong không-thời gian bị cong bởi khối lượng.

Phương trình geodesic (dạng rút gọn cho mặt phẳng xích đạo):

```
d²r/dτ² = r(dφ/dτ)²(1 − rs/r) − (rs/2r²)(1/(1−rs/r))(dr/dτ)²
```

Nghiệm số dùng phương pháp **Runge-Kutta bậc 4 (RK4)**.

**Các loại quỹ đạo:**

| Điều kiện | Loại Quỹ Đạo |
|-----------|-------------|
| `r₀ > 3rs` | Quỹ đạo tuần hoàn hoặc thoát ly ổn định |
| `r₀ = 3rs` | ISCO – Innermost Stable Circular Orbit |
| `r₀ < 3rs` | Bị hút vào hố đen |

### 2. 💡 Thấu Kính Hấp Dẫn (Gravitational Lensing)

Ánh sáng bị bẻ cong khi đi qua vùng không gian cong. Einstein dự đoán góc lệch:

```
δ = 4GM / (bc²) = 2rs / b
```

Trong đó `b` là **thông số va chạm (impact parameter)** – khoảng cách vuông góc gần nhất giữa tia sáng và tâm khối lượng nếu không có lực hấp dẫn.

**Photon Sphere:** Tại `r = 1.5 rs`, photon có thể quay quanh hố đen theo quỹ đạo tròn không ổn định. Tia sáng có `b < 1.5 rs` bị hút vào hố đen.

> 📅 **Lịch sử:** Nhật thực ngày 29/5/1919 – Arthur Eddington đo độ lệch ánh sáng từ ngôi sao phía sau Mặt Trời, xác nhận dự đoán của Einstein là **1.75 arcseconds**.

### 3. ⏰ Giãn Nở Thời Gian Hấp Dẫn (Gravitational Time Dilation)

Đồng hồ gần vật thể khối lượng lớn chạy **chậm hơn** so với đồng hồ ở xa:

```
dτ/dt = √(1 − rs/r)
```

| Vị trí `r` | Tốc độ đồng hồ |
|------------|---------------|
| `r → ∞` | 100% (bình thường) |
| `r = 10 rs` | 94.87% |
| `r = 2 rs` | 70.71% |
| `r = 1.01 rs` | 9.95% |
| `r = rs` (chân trời sự kiện) | **0% — thời gian dừng** |

> 🛰️ **Ứng dụng thực tế:** Hệ thống GPS phải hiệu chỉnh **+45.9 μs/ngày** do giãn thời gian hấp dẫn (vệ tinh ở cao, trường hấp dẫn yếu hơn → đồng hồ chạy nhanh hơn).

### 4. 🕳️ Hố Đen Schwarzschild

Khi khối lượng bị nén xuống dưới bán kính Schwarzschild:

```
rs = 2GM / c²
```

| Vật Thể | Khối Lượng | Bán Kính Schwarzschild |
|---------|-----------|----------------------|
| Trái Đất | 5.97 × 10²⁴ kg | **8.87 mm** |
| Mặt Trời | 1 M☉ | **2.95 km** |
| Hố đen 10 M☉ | 10 M☉ | **29.5 km** |
| Sgr A* (trung tâm Ngân Hà) | 4.1 × 10⁶ M☉ | **12.1 triệu km** |
| M87* | 6.5 × 10⁹ M☉ | **19.2 tỷ km** |

**Nhiệt độ Hawking:**

```
T_H = ℏc³ / (8πGMk_B)
```

Hố đen càng nặng → nhiệt độ Hawking càng thấp.

### 5. 🌊 Sóng Hấp Dẫn (Gravitational Waves)

Khi hai vật thể khối lượng lớn (sao neutron, hố đen) quay quanh nhau và sáp nhập, chúng tạo ra **gợn sóng trong không-thời gian** — sóng hấp dẫn.

**Khối lượng chirp:**

```
M_chirp = (m₁ · m₂)^(3/5) / (m₁ + m₂)^(1/5)
```

> 🏆 **LIGO phát hiện GW150914** (14/9/2015): Tín hiệu từ 2 hố đen 36 M☉ + 29 M☉ sáp nhập cách Trái Đất 1.3 tỷ năm ánh sáng. Giải Nobel Vật lý 2017.

### 6. 🌐 Paraboloid Flamm (Embedding Diagram)

Hình học không gian quanh hố đen được nhúng vào không gian 3D theo công thức:

```
z = 2√(rs · (r − rs)),  r > rs
```

Đây là cách trực quan hóa phổ biến nhất để giải thích "không gian cong" — như tấm cao su bị một quả bóng chì kéo xuống.

---

## ✨ Tính Năng

### 5 Tab Mô Phỏng Tương Tác

| Tab | Tính Năng | Điều Chỉnh Được |
|-----|-----------|-----------------|
| 🌀 **Trắc Địa** | Vẽ quỹ đạo vật thể trong không gian Schwarzschild | `r₀`, `dφ/dτ`, `dr/dτ`, số bước RK4 |
| 💡 **Ánh Sáng** | Null geodesic – thấu kính hấp dẫn | Impact parameter `b`, đơn/đa tia |
| ⏰ **Giãn Thời Gian** | Đồ thị + animation đồng hồ đôi | Bán kính thăm dò, tầm nhìn |
| 🌐 **Cong Không Gian** | Lưới Flamm Paraboloid 3D giả | Độ phân giải, bán kính rs |
| 〰️ **Sóng Hấp Dẫn** | Chirp waveform + spectrogram | Khối lượng m₁, m₂ |

### Công Cụ Tính Hố Đen

- Nhập khối lượng bất kỳ (M☉) → tính `rs`, nhiệt độ Hawking
- Animation hố đen quay với vành đĩa bồi tụ
- Preset nhanh: Mặt Trời, Sgr A*, M87*

### Giao Diện

- 🌑 Dark space theme toàn phần
- ✨ Starfield animation động
- 🔮 Glassmorphism cards
- 📊 Canvas rendering real-time
- 📱 Responsive layout

---

## 📁 Cấu Trúc Dự Án

```
learn_physic/
│
├── app.py          # Python Flask backend – toàn bộ tính toán vật lý
├── database.py     # Database engine & session management (SQLite/PostgreSQL)
├── models.py       # SQLAlchemy ORM Models (SimulationRun, AnalyticsSummary, vv.)
├── etl_pipeline.py # ETL Jobs: Aggregate data, Heatmap, JSON Export
├── schema_migration.py # Migration tool chuyển đổi SQLite -> PostgreSQL
├── index.html      # Giao diện HTML chính
├── style.css       # Dark space theme, Glassmorphism CSS
├── main.js         # Canvas rendering, API calls, animations
└── README.md       # Tài liệu này
```

---

## 🖥️ Yêu Cầu Hệ Thống

| Thành Phần | Phiên Bản |
|-----------|----------|
| Python | ≥ 3.8 |
| Flask | ≥ 3.0 |
| Flask-CORS | ≥ 6.0 |
| NumPy | ≥ 1.24 |
| Trình duyệt | Chrome/Firefox/Edge hiện đại |

---

## 🚀 Cài Đặt & Chạy

### Bước 1 – Cài đặt thư viện Python

```bash
python -m pip install -r requirements.txt
```

Nếu muốn chạy bằng PostgreSQL, hãy bỏ comment thư viện `psycopg2-binary` trong file `requirements.txt`.

### Bước 2 – Khởi tạo cơ sở dữ liệu

Mặc định, ứng dụng dùng SQLite để dễ dàng chạy cục bộ.

```bash
python schema_migration.py init
```

### Bước 2 – Khởi động backend

```bash
cd learn_physic
python app.py
```

Kết quả mong đợi:

```
============================================================
  General Relativity Simulator  –  Backend API
============================================================
  Speed of light     c = 3.00e+08 m/s
  Grav. constant     G = 6.674e-11 m^3/(kg*s^2)
  Solar mass     M_sun = 1.989e+30 kg
  Sun's Schwarzschild radius = 2.95 km
  10M_sun black hole rs = 29.50 km
============================================================
  Running on http://localhost:5000
============================================================
 * Running on http://127.0.0.1:5000
```

### Bước 3 – Mở giao diện

Mở file `index.html` trực tiếp trong trình duyệt, hoặc chạy lệnh:

```bash
# Windows
start index.html

# macOS
open index.html

# Linux
xdg-open index.html
```

> ⚠️ **Quan trọng:** Backend Flask phải đang chạy trên cổng `5000` trước khi mở `index.html`.

---

## 🔌 API Backend

Base URL: `http://localhost:5000/api`

### GET `/api/info`
Thông tin về API.

```json
{
  "name": "General Relativity Simulator",
  "version": "1.0"
}
```

---

### GET `/api/schwarzschild`

Tính bán kính Schwarzschild.

**Query params:**
| Tham số | Kiểu | Mặc định | Mô tả |
|---------|------|----------|-------|
| `mass` | float | `1.0` | Khối lượng tính theo M☉ |

**Ví dụ:**
```
GET /api/schwarzschild?mass=10
```

**Response:**
```json
{
  "mass_solar": 10.0,
  "mass_kg": 1.989e+31,
  "schwarzschild_radius_m": 29530.0,
  "schwarzschild_radius_km": 29.53,
  "description": "A 10.0 solar-mass object has a Schwarzschild radius of 29.530 km..."
}
```

---

### POST `/api/geodesic`

Tích phân geodesic vật thể khối lượng trong không gian Schwarzschild.

**Request body:**
```json
{
  "rs": 1.0,
  "r0": 6.0,
  "phi0": 0.0,
  "dr_dtau": 0.0,
  "dphi_dtau": 0.12,
  "steps": 800,
  "dtau": 0.5
}
```

| Trường | Mô tả |
|--------|-------|
| `rs` | Bán kính Schwarzschild (đơn vị không thứ nguyên) |
| `r0` | Bán kính ban đầu (× rs) |
| `phi0` | Góc ban đầu (radian) |
| `dr_dtau` | Vận tốc hướng tâm ban đầu |
| `dphi_dtau` | Vận tốc góc ban đầu |
| `steps` | Số bước tích phân RK4 |
| `dtau` | Bước proper time |

**Response:**
```json
{
  "path": [
    { "x": 6.0, "y": 0.0, "r": 6.0, "phi": 0.0, "captured": false },
    ...
  ],
  "rs": 1.0,
  "r0": 6.0,
  "steps_computed": 800,
  "captured": false
}
```

---

### POST `/api/light_ray`

Tính null geodesic (tia sáng) bị bẻ cong bởi hấp dẫn.

**Request body:**
```json
{
  "rs": 1.0,
  "b": 5.0,
  "steps": 1200,
  "dlambda": 0.3
}
```

| Trường | Mô tả |
|--------|-------|
| `b` | Impact parameter (× rs). `b < 1.5` → bị hút vào hố đen |
| `dlambda` | Bước affine parameter |

**Response:**
```json
{
  "path": [ ... ],
  "impact_parameter": 5.0,
  "rs": 1.0,
  "deflection_angle_deg": 22.9183,
  "captured": false
}
```

---

### GET `/api/time_dilation`

Dữ liệu hệ số giãn thời gian theo bán kính.

**Query params:**
| Tham số | Mô tả |
|---------|-------|
| `rs` | Bán kính Schwarzschild (mặc định 1.0) |
| `r_min` | Bán kính tối thiểu (× rs), mặc định 1.01 |
| `r_max` | Bán kính tối đa (× rs), mặc định 20 |
| `points` | Số điểm dữ liệu, mặc định 200 |

**Response:**
```json
{
  "rs": 1.0,
  "data": [
    {
      "r": 1.01,
      "r_over_rs": 1.01,
      "dilation_factor": 0.0995,
      "time_ratio_percent": 9.95,
      "slower_by_percent": 90.05
    },
    ...
  ]
}
```

---

### GET `/api/spacetime_grid`

Dữ liệu lưới Flamm Paraboloid cho embedding diagram.

**Query params:**
| Tham số | Mô tả |
|---------|-------|
| `rs` | Bán kính Schwarzschild |
| `grid_size` | Kích thước lưới N×N (mặc định 22) |
| `r_max` | Tầm nhìn (mặc định 14.0) |

**Response:**
```json
{
  "rs": 1.0,
  "grid_size": 22,
  "points": [
    { "x": -14.0, "y": -14.0, "r": 19.8, "z": -0.141 },
    ...
  ]
}
```

Giá trị `z` là độ lún của Flamm Paraboloid: `z = -2√(rs·(r−rs))`

---

### POST `/api/multi_geodesics`

Tính đồng thời nhiều geodesic (họ quỹ đạo).

**Request body:**
```json
{
  "rs": 1.0,
  "configs": [
    { "r0": 5.0, "dphi_dtau": 0.15, "dr_dtau": 0.0, "color": "#f5c842" },
    { "r0": 7.0, "dphi_dtau": 0.12, "dr_dtau": 0.0, "color": "#00e5ff" }
  ],
  "steps": 700,
  "dtau": 0.5
}
```

---

### GET `/api/gravitational_waves`

Mô phỏng dạng sóng chirp của binary inspiral.

**Query params:**
| Tham số | Mô tả |
|---------|-------|
| `m1` | Khối lượng vật thể 1 (M☉) |
| `m2` | Khối lượng vật thể 2 (M☉) |
| `duration` | Thời lượng (giây) |
| `sample_rate` | Tần số lấy mẫu (Hz) |

**Response:**
```json
{
  "m1_solar": 30.0,
  "m2_solar": 30.0,
  "chirp_mass_solar": 26.13,
  "data": [
    { "t": 0.0, "h": 1.2e-21, "f": 50.0 },
    ...
  ]
}
```

---

## 🧮 Phương Pháp Số

### Runge-Kutta Bậc 4 (RK4)

Phương pháp tích phân được dùng để giải phương trình geodesic:

```python
k1 = f(y_n)
k2 = f(y_n + h/2 * k1)
k3 = f(y_n + h/2 * k2)
k4 = f(y_n + h * k3)

y_{n+1} = y_n + h/6 * (k1 + 2k2 + 2k3 + k4)
```

Sai số toàn cục: **O(h⁴)** – đủ chính xác cho mô phỏng giáo dục.

### Thế Hiệu Dụng (Effective Potential)

Geodesic Schwarzschild được viết lại qua thế hiệu dụng:

**Vật thể khối lượng (timelike):**
```
V_eff(r) = (1 − rs/r)(1 + L²/r²)
(dr/dτ)² = E² − V_eff(r)
```

**Photon (null geodesic):**
```
V_eff(r) = (1 − rs/r)/r²
(dr/dλ)² = 1/b² − V_eff(r)
```

Phương trình chuyển động:
```
d²r/dλ² = −(1/2) · dV_eff/dr · L²
```

---

## 🛠️ Kiến Trúc Kỹ Thuật

```
┌─────────────────────────────────────────────────────┐
│                   Trình Duyệt                        │
│                                                     │
│  index.html ──→ main.js ──→ HTML5 Canvas            │
│       │              │                              │
│  style.css      Fetch API calls                     │
└─────────────────────────┬───────────────────────────┘
                          │ HTTP JSON (localhost:5000)
                          ▼
┌─────────────────────────────────────────────────────┐
│              Flask Backend (app.py)                  │
│                                                     │
│  /api/geodesic      → geodesic_rk4()               │
│  /api/light_ray     → geodesic_light_rk4()         │
│  /api/time_dilation → time_dilation_factor()        │
│  /api/spacetime_grid→ spacetime_curvature_grid()    │
│  /api/grav_waves    → gravitational_waves()         │
│  /api/schwarzschild → schwarzschild_radius()        │
│                                                     │
│  Thư viện: NumPy, Flask, Flask-CORS                 │
└─────────────────────────────────────────────────────┘
```

---

## 💾 Data Engineering & Database

Dự án này tích hợp một **Data Engineering stack** hoàn chỉnh để lưu trữ lịch sử mô phỏng, phân tích, và phục vụ phân tích máy học.

### Kiến trúc Database (SQLite → PostgreSQL)
- **Local Dev**: Dùng SQLite không cần cài đặt (file `physics_sim.db`).
- **Production**: Chỉ cần thay đổi `DATABASE_URL` trong file `.env` thành PostgreSQL (`postgresql://user:pass@host/db`) và cài đặt `psycopg2`.
- Sử dụng **SQLAlchemy ORM** để quản lý model.

### ETL Pipeline (`etl_pipeline.py`)
Có một job ETL để tự động phân tích và trích xuất dữ liệu:
1. `aggregate_daily_stats()`: Tính toán thống kê sử dụng (thời gian chạy trung bình, số lần chạy, thông số phổ biến).
2. `update_parameter_heatmap()`: Cập nhật Heatmap để xem tham số nào hay được sử dụng nhất và tỷ lệ bị bắt (captured rate).
3. `cleanup_old_results()`: Dọn dẹp các JSON results cũ để tiết kiệm dung lượng.
4. `export_to_json()`: Export toàn bộ history phục vụ cho huấn luyện Machine Learning.

### Schema Migration (`schema_migration.py`)
Hỗ trợ kiểm tra tình trạng DB, cập nhật thay đổi schema và sao chép trực tiếp dữ liệu từ SQLite sang PostgreSQL khi cần thiết (`python schema_migration.py to-postgres --pg-url ...`).

---

## 📚 Tài Liệu Tham Khảo

| Nguồn | Mô Tả |
|-------|-------|
| Einstein, A. (1915) | *Die Feldgleichungen der Gravitation* – Phương trình trường gốc |
| Schwarzschild, K. (1916) | *Über das Gravitationsfeld eines Massenpunktes* – Nghiệm chính xác đầu tiên |
| Misner, Thorne, Wheeler (1973) | *Gravitation* – Sách giáo khoa chuẩn về GTR |
| Carroll, S. (2004) | *Spacetime and Geometry* – Giới thiệu GTR hiện đại |
| LIGO Collaboration (2016) | *GW150914* – Phát hiện sóng hấp dẫn đầu tiên, PRL 116, 061102 |
| EHT Collaboration (2019) | *First Image of M87\** – Ảnh đầu tiên của hố đen, ApJL 875 |
| Hawking, S. (1974) | *Black hole explosions?* – Bức xạ Hawking, Nature 248 |
| Wald, R. M. (1984) | *General Relativity* – Chicago University Press |

---

## 📝 Ghi Chú Phát Triển

- Backend dùng đơn vị **không thứ nguyên** (`rs = 1`) để dễ mô phỏng
- Mô phỏng sóng hấp dẫn là **chirp đơn giản hóa** (không phải giải đầy đủ post-Newtonian)
- Geodesic ánh sáng khởi đầu từ `r_start = max(50·rs, 20·b)` để đảm bảo điều kiện biên đúng
- Paraboloid Flamm chỉ là **embedding 2+1D** — không phải không-thời gian 4D đầy đủ

---

<div align="center">

**G_μν + Λg_μν = (8πG/c⁴) T_μν**

*"Không gian nói với vật chất cách di chuyển; vật chất nói với không gian cách cong."*  
— John Archibald Wheeler

</div>
