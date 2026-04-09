# 📒 Note Scraper Market Intelligence (Bahan Bangunan)

Dokumen ini menjelaskan rancangan arsitektur data, alasan bisnis, dan teknis dari script scraper market intelligence untuk material konstruksi (khususnya Bata Ringan) di wilayah Jawa Timur.

---

## 1. Scraping Data Apa?

Sistem ini melakukan **Web Scraping Market Intelligence** khusus untuk industri produk bahan bangunan beton ringan (*Autoclaved Aerated Concrete* / AAC) beserta produk penyertanya (seperti Semen Mortar). 

Data yang diambil meliputi:
- **Pricing Insight:** Harga asli di pasaran (SRP/Modern Trade maupun harga agen retail independen).
- **Distribusi Geografis:** Melacak dimana sebuah produk brand dijual secara online.
- **Tingkat Penjualan & Rating:** Mengukur sentimen konsumen dan estimasi pergerakan *market share* retail di lapangan.

Data ini sangat krusial digunakan oleh tim *Sales & Marketing* (misal dari pabrikan/distributor) untuk menganalisis **Price Gap** (jarak harga dengan kompetitor seperti Citicon, Blesscon, Grand Elephant) dan **Retail Penetration** di arena digital region Jawa Timur.

---

## 2. Struktur Data Output (Skema)

Hasil dari web scraping diproses berlapis, dari data mentah (*raw DOM*) menjadi data numerik siap hitung, lalu disimpan dalam format **`.csv`**. Berikut adalah struktur tabel beserta tipe data dan relevansi analitiknya:

| Nama Kolom | Tipe Data | Deskripsi | Tujuan Analisis (Konteks Sales) |
|---|---|---|---|
| `scraped_at` | Datetime | Tanggal & waktu data diambil | Melacak fluktuasi harga mingguan/bulanan. |
| `platform` | String | Sumber (Tokopedia / DepoBangunan / Mitra10) | Segmentasi harga berdasarkan channel penjualan. |
| `search_keyword` | String | Kata kunci yang digunakan saat mencari | Mengetahui relevansi produk dengan pencarian. |
| `brand_label` | String | Nama merk (Blesscon, Citicon, dll) | Kategori utama untuk perbandingan Internal vs Competitor. |
| `product_name` | String | Nama lengkap produk di web/apps | Identifikasi spesifikasi (contoh: ukuran 7.5cm vs 10cm). |
| `price_numeric` | Integer | Harga dalam angka (bersih dari "Rp" dll) | Menghitung rata-rata harga pasar dan price gap. |
| `unit_type` | String | Satuan (m3, biji, atau palet) | Normalisasi harga agar bisa dibandingkan secara seimbang. |
| `store_name` | String | Nama toko atau distributor | Mengidentifikasi pemain retail/distributor tumpang tindih. |
| `store_location` | String | Lokasi kota (Surabaya, Sidoarjo, dll) | Analisis kekuatan distribusi per wilayah geografis. |
| `is_east_java` | Boolean | Flag khusus wilayah Jatim | Menyingkirkan harga pencilan yang berasal dari luar target area. |
| `total_sold` | String | Jumlah terjual (raw txt) | Catatan orisinil tulisan terjual dari app. |
| `total_sold_numeric`| Integer | Angka murni dari jumlah barang terjual | Kalkulasi volume dan estimasi *market share*. |
| `rating_product` | Float | Skor bintang produk (1.0 - 5.0) | Mengukur kepuasan pelanggan akan brand/toko. |
| `product_url` | String | Link detail halaman produk | Untuk validasi dan audit rujukan referensi harga. |

---

## 3. Daftar Keyword & Fungsinya

Script memakai list *query* spesifik yang dijalin guna mensimulasikan pencarian natural dari pelanggan di *search bar*. Terdapat **18 Keyword** utama yang dibagi menjadi 3 grup besar.

### Grup A: Brand Awareness (8 Keyword)
Mencari seberapa banyak produk dari merk tertentu muncul ketika user langsung mencari merknya.
- `Bata Ringan Blesscon` (Brand: Blesscon)
- `Bata Ringan Citicon` (Brand: Citicon)
- `Bata Ringan Grand Elephant` (Brand: Grand Elephant)
- `Bata Ringan Falcon` (Brand: Falcon)
- `Bata Ringan Hebel` (Brand: Hebel / General term)
- `Bata Ringan Prime Mortar` (Brand: Prime Mortar)
- `Bata Ringan Focon` (Brand: Focon)
- `Bata Ringan Great Wall` (Brand: Great Wall)

### Grup B: Spesifikasi & Area Jatim / Natural Search (7 Keyword)
Simulasi dari konsumen atau *sub-contractor* yang mencari berdasar lokasi, ukuran, atau satuan tanpa memikirkan merk (membantu mencari siapa *Market Leader* organik).
- `Bata Ringan Surabaya Murah`
- `Bata Ringan Sidoarjo Grosir`
- `Bata Ringan Gresik m3`
- `Bata Ringan 7.5cm`
- `Bata Ringan 10cm`
- `Hebel Surabaya satu rit`
- `Bata Ringan per kubik`

### Grup C: Cross-Selling & Aksesoris (3 Keyword)
Menganalisis pendamping komplementer dari Bata Ringan, yaitu semen instan / perekat untuk mengetahui kombinasi logistik.
- `Semen Mortar Perekat Bata Ringan`
- `Mortar Instan Surabaya`
- `Thinbed Bata Ringan`

---

## 4. Pilihan Web / Platform & Alasannya

Sistem hanya men-scrape data dari platform yang relevan dengan **harga Retail Independent dan Modern Trade** di Jawa Timur.

### ✅ Tokopedia
- **Alasan Bisnis:** Tokopedia adalah barometer kuat untuk "Traditional Retail" atau "Toko Besi Independen" yang berjualan secara online atau para aplikator lokal.
- **Kondisi Khusus:** Script di set default agar menempelkan tag pencarian `location=surabaya`. Algoritma Tokopedia sudah cukup cerdas untuk men-filter area cakupan *Gerbangkertosusila* (Surabaya, Gresik, Sidoarjo, dsk).

### ✅ Depo Bangunan
- **Alasan Bisnis:** Merupakan salah satu pionir Supermarket Bahan Bangunan (*Modern Trade/Modern Retail*) di Indonesia dengan footprint kuat di Jawa Timur.
- **Kondisi Khusus:** Harga di platform ini merupakan Standar Harga Eceran (SRP) resmi (berbeda drastis dengan banting-bantingan harga di Tokopedia) yang berguna jadi harga acuan/atap.

### ✅ Mitra10
- **Alasan Bisnis:** Pesaing kuat Depo Bangunan memperebutkan segmen *Modern Trade*. Harga di Mitra10 bisa menceritakan persaingan promo retail korporasi yang akan dirasakan langsung oleh end-user level menengah atas.
- **Kondisi Khusus:** Menyajikan spesifikasi brand ternama secara akurat.

### 🚫 Shopee (Tidak digunakan)
- **Mengapa tidak dipakai?** Shopee saat ini memiliki mekanisme proteksi *Cloudflare Bot Management* paling agresif dan cenderung memaksa tertutupnya sistem headless automation. 
- Di samping hal teknis, profil Tokopedia ternyata telah sangat memenuhi porsi perwakilan e-commerce *open marketplace*, sehingga hilangnya data Shopee tidak mendistorsi representasi harga industri material konstruksi berat berskala besar di Jawa Timur secara bermakna.

---

## Memulai via Jupyter Notebook

1. Buka Jupyter Notebook atau file `.ipynb`.
2. Pastikan file script `market_intel_scraper.py` berada di direktori selevel. (Sudah clean dan tidak menggunakan code Shopee).
3. Buat cell eksekusi:
```python
import importlib
import market_intel_scraper

# Paksa reload modul jika sebelumnya pernah di import
importlib.reload(market_intel_scraper)

import pandas as pd
df = market_intel_scraper.main(is_colab=False)

df.head()
```
