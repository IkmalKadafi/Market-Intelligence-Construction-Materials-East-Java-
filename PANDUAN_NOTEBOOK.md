# 📒 Panduan Lengkap — Market Intelligence Scraper (AAC / Bata Ringan)

## Struktur File

```
Market-Intelligence-Construction-Materials-East-Java-/
├── market_intel_scraper.py     ← Script utama (GUNAKAN INI)
├── tokopedia_scraper.py        ← Versi lama (deprecated)
├── data_scraping.ipynb         ← Notebook (paste kode dari script utama)
└── PANDUAN_NOTEBOOK.md         ← File ini
```

---

## Platform yang Di-Scrape

| Platform | Status | Keterangan |
|---|---|---|
| ✅ Tokopedia | Aktif | Harga distributor independen, filter Jatim |
| ✅ Shopee | Aktif | Volume retail kecil, JS-heavy |
| ✅ Depo Bangunan | Aktif | Harga acuan retail resmi Jatim |

---

## Schema Kolom Output

| Kolom | Tipe | Deskripsi | Tujuan Analisis |
|---|---|---|---|
| `scraped_at` | Datetime | Waktu data diambil | Lacak fluktuasi harga mingguan/bulanan |
| `platform` | String | Tokopedia / Shopee / DepoBangunan | Segmentasi per channel |
| `search_keyword` | String | Kata kunci pencarian | Relevansi produk |
| `brand_label` | String | Blesscon, Citicon, dll | Segmentasi brand |
| `product_name` | String | Nama lengkap produk | Identifikasi spesifikasi (7.5cm vs 10cm) |
| `price_numeric` | Integer | Harga bersih (angka) | Rata-rata & price gap antar brand |
| `unit_type` | String | m3 / pcs / palet / rit | Normalisasi harga adil |
| `store_name` | String | Nama toko / distributor | Pemain paling agresif |
| `store_location` | String | Kota toko | Distribusi geografis |
| `is_east_java` | Boolean | Apakah lokasi di Jatim | Filter regional |
| `total_sold` | String | Jumlah terjual (raw) | Estimasi market share |
| `total_sold_numeric` | Integer | Jumlah terjual (angka) | Kalkulasi market share |
| `rating_product` | Float | Skor bintang | Persepsi kepuasan konsumen |
| `product_url` | String | Link produk | Validasi data |

---

## Daftar Keyword (18 Total)

### Grup: Brand Awareness (8 keyword)
| Keyword | Brand Label |
|---|---|
| Bata Ringan Blesscon | Blesscon |
| Bata Ringan Citicon | Citicon |
| Bata Ringan Grand Elephant | Grand Elephant |
| Bata Ringan Falcon | Falcon |
| Bata Ringan Hebel | Hebel |
| Bata Ringan Prime Mortar | Prime Mortar |
| Bata Ringan Focon | Focon |
| Bata Ringan Great Wall | Great Wall |

### Grup: Spesifikasi & Regional (7 keyword)
| Keyword | Brand Label |
|---|---|
| Bata Ringan Surabaya Murah | General |
| Bata Ringan Sidoarjo Grosir | General |
| Bata Ringan Gresik m3 | General |
| Bata Ringan 7.5cm | General |
| Bata Ringan 10cm | General |
| Hebel Surabaya satu rit | Hebel |
| Bata Ringan per kubik | General |

### Grup: Cross-Selling Accessories (3 keyword)
| Keyword | Brand Label |
|---|---|
| Semen Mortar Perekat Bata Ringan | Mortar/Accessories |
| Mortar Instan Surabaya | Mortar/Accessories |
| Thinbed Bata Ringan | Mortar/Accessories |

---

## Cara Pakai di Jupyter Notebook / Google Colab

### Opsi 1 — Jalankan langsung sebagai script
```bash
python market_intel_scraper.py
```

### Opsi 2 — Paste ke `data_scraping.ipynb`
Salin isi `market_intel_scraper.py` ke dalam cell-cell notebook sesuai komentar `# CELL 1`, `# CELL 2`, dst.

Di **Google Colab**, tambahkan cell pertama:
```python
!apt-get update -q && apt-get install -y -q chromium-browser chromium-chromedriver
!pip install selenium webdriver-manager beautifulsoup4 pandas lxml -q
```

Lalu saat memanggil `main()`, gunakan:
```python
df_result = main(is_colab=True)   # ← ganti ke True di Colab!
```

---

## Konfigurasi Lanjutan

Edit bagian konstanta di awal file untuk menyesuaikan:

```python
# Enable/disable platform
PLATFORMS_ENABLED = {
    "Tokopedia":    True,
    "Shopee":       False,   # ← nonaktifkan jika terlalu lambat
    "DepoBangunan": True,
}

# Sesuaikan kecepatan scraping
SCROLL_COUNT = 4        # lebih banyak = lebih lambat tapi lebih lengkap
DELAY_MIN    = 3.5      # jeda minimum antar request (detik)
DELAY_MAX    = 8.0      # jeda maksimum antar request (detik)
```

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| `0 produk` di Tokopedia | Selector berubah — cek DevTools, update CSS di `scrape_tokopedia()` |
| `0 produk` di Shopee | Shopee anti-bot aktif → coba tambah `WAIT_TIMEOUT` ke 30 |
| `ChromeDriver error` | `pip install --upgrade webdriver-manager` |
| Terblokir / CAPTCHA | Tambah `DELAY_MIN/MAX`, ganti User-Agent di `create_driver()` |
| Colab tidak menemukan Chrome | Pastikan `is_colab=True` dan sudah install `chromium-browser` |

---

## Contoh Analisis Lanjutan dari Output

```python
import pandas as pd

df = pd.read_csv("raw_market_data_lightweight_concrete.csv")

# 1. Rata-rata harga per brand per platform
df.groupby(["brand_label","platform"])["price_numeric"].mean()

# 2. Market share estimasi per brand (berdasarkan total sold)
df.groupby("brand_label")["total_sold_numeric"].sum().sort_values(ascending=False)

# 3. Filter hanya produk dari Jawa Timur
df_jatim = df[df["is_east_java"] == True]

# 4. Price benchmark per unit type
df.groupby(["brand_label","unit_type"])["price_numeric"].agg(["min","mean","max"])
```
