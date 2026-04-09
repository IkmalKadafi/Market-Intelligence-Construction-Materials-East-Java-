# ============================================================
# MARKET INTELLIGENCE - BATA RINGAN (AAC) TOKOPEDIA SCRAPER
# Project: Market Intelligence Dashboard - Building Materials
# Author  : Sales Data Analyst
# Target  : Tokopedia Product Search
# ============================================================

# ──────────────────────────────────────────────────────────────
# CELL 1 — Install Dependencies (Jalankan hanya sekali di Colab)
# ──────────────────────────────────────────────────────────────
"""
Jika berjalan di Google Colab, uncomment dan jalankan blok ini:

!pip install selenium webdriver-manager beautifulsoup4 pandas lxml -q
"""

# ──────────────────────────────────────────────────────────────
# CELL 2 — Import Libraries
# ──────────────────────────────────────────────────────────────
import time
import random
import re
import warnings
import pandas as pd

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from webdriver_manager.chrome import ChromeDriverManager

warnings.filterwarnings("ignore")
print("✅ Semua library berhasil di-import.")


# ──────────────────────────────────────────────────────────────
# CELL 3 — Konfigurasi & Konstanta
# ──────────────────────────────────────────────────────────────

# Mapping keyword → label brand
SEARCH_CONFIG = [
    {"keyword": "Bata Ringan Blesscon Surabaya",   "brand": "Blesscon"},
    {"keyword": "Bata Ringan Citicon Surabaya",    "brand": "Citicon"},
    {"keyword": "Bata Ringan Grand Elephant",      "brand": "Grand Elephant"},
    {"keyword": "Bata Ringan Falcon",              "brand": "Falcon"},
    {"keyword": "Bata Ringan Hebel",               "brand": "Hebel"},
    {"keyword": "Depo Bangunan Bata Ringan",       "brand": "General / Depo"},
]

# Tokopedia search URL template
TOKOPEDIA_SEARCH_URL = "https://www.tokopedia.com/search?st=product&q={query}&navsource=home"

# Jumlah scroll per halaman
SCROLL_COUNT = 4

# Jeda antar scroll (detik)
SCROLL_PAUSE = 1.5

# Jeda acak antar keyword (detik)
DELAY_MIN = 3
DELAY_MAX = 7

# Timeout WebDriverWait (detik)
WAIT_TIMEOUT = 15

print("✅ Konfigurasi selesai diset.")
print(f"   Total keyword yang akan di-scrape: {len(SEARCH_CONFIG)}")


# ──────────────────────────────────────────────────────────────
# CELL 4 — Setup Chrome Driver (Headless)
# ──────────────────────────────────────────────────────────────

def create_driver() -> webdriver.Chrome:
    """
    Membuat dan mengembalikan instance WebDriver Chrome headless.
    Kompatibel dengan Google Colab dan environment lokal.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # User-Agent manusia agar tidak mudah terdeteksi sebagai bot
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Menyembunyikan tanda otomasi dari JavaScript
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


print("✅ Fungsi create_driver() siap digunakan.")


# ──────────────────────────────────────────────────────────────
# CELL 5 — Fungsi Auto-Scroll
# ──────────────────────────────────────────────────────────────

def auto_scroll(driver: webdriver.Chrome, scroll_count: int = SCROLL_COUNT,
                pause: float = SCROLL_PAUSE) -> None:
    """
    Melakukan scroll ke bawah sebanyak `scroll_count` kali dengan jeda `pause` detik
    agar produk lazy-load sempat ter-render.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")

    for i in range(scroll_count):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            # Halaman tidak bertambah tinggi → sudah habis
            print(f"   ↕  Scroll {i+1}/{scroll_count} — halaman tidak bertambah, berhenti scroll.")
            break

        last_height = new_height
        print(f"   ↕  Scroll {i+1}/{scroll_count} selesai.")


print("✅ Fungsi auto_scroll() siap digunakan.")


# ──────────────────────────────────────────────────────────────
# CELL 6 — Fungsi Parsing Harga
# ──────────────────────────────────────────────────────────────

def parse_price(price_text: str) -> int | None:
    """
    Mengubah string harga (misalnya 'Rp 350.000' atau 'Rp2.500.000')
    menjadi integer. Mengembalikan None jika gagal di-parse.
    """
    if not price_text:
        return None
    cleaned = re.sub(r"[^0-9]", "", price_text)
    return int(cleaned) if cleaned else None


# ──────────────────────────────────────────────────────────────
# CELL 7 — Fungsi Utama Scraping per Keyword
# ──────────────────────────────────────────────────────────────

def scrape_tokopedia(driver: webdriver.Chrome, keyword: str, brand_label: str) -> list[dict]:
    """
    Melakukan pencarian di Tokopedia dengan keyword yang diberikan,
    men-scroll halaman, lalu mengambil data produk.

    Returns:
        List of dict, setiap dict berisi data satu produk.
    """
    results = []
    encoded_keyword = keyword.replace(" ", "+")
    url = TOKOPEDIA_SEARCH_URL.format(query=encoded_keyword)

    print(f"\n🔍 Mencari: '{keyword}'  (Brand: {brand_label})")
    print(f"   URL: {url}")

    try:
        driver.get(url)

        # Tunggu kartu produk pertama muncul
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='master-product-card']")
            )
        )
        print("   ✅ Halaman berhasil dimuat, kartu produk terdeteksi.")

    except TimeoutException:
        print(f"   ⚠️  Timeout: Kartu produk tidak ditemukan dalam {WAIT_TIMEOUT} detik. "
              "Mencoba lanjut dengan konten yang ada...")
    except Exception as e:
        print(f"   ❌ Error saat membuka halaman: {e}")
        return results

    # Auto-scroll untuk lazy-load
    auto_scroll(driver)

    # Ambil HTML setelah semua konten ter-render
    soup = BeautifulSoup(driver.page_source, "lxml")

    # Selector kartu produk utama (data-testid lebih stabil dari class)
    product_cards = soup.select("[data-testid='master-product-card']")

    if not product_cards:
        # Fallback selector alternatif
        product_cards = soup.select("div.css-jza1fo")

    print(f"   📦 Ditemukan {len(product_cards)} kartu produk.")

    for card in product_cards:
        try:
            # ── Nama Produk ───────────────────────────────
            product_name = _safe_text(card, [
                "[data-testid='spnSRPPdpName']",
                "span.css-yzwxx8",
                "span[class*='productName']",
                "div[data-testid='divProductName'] span",
            ])

            # ── Harga Mentah (Raw) ───────────────────────
            raw_price_text = _safe_text(card, [
                "[data-testid='linkProductPrice']",
                "span.css-o5uqvq",
                "span[class*='price']",
                "div[data-testid='divProductPrice'] span",
            ])
            price_int = parse_price(raw_price_text)

            # ── Nama Toko ────────────────────────────────
            shop_name = _safe_text(card, [
                "[data-testid='linkProductShopName']",
                "span[class*='shopName']",
                "a[data-testid='linkProductShopName']",
                "div[data-testid='divShopName'] span",
            ])

            # ── Lokasi Toko/Kota ─────────────────────────
            location = _safe_text(card, [
                "[data-testid='spanProductLocation']",
                "span[class*='location']",
                "div[data-testid='divProductLocation'] span",
                "span[class*='Location']",
            ])

            # ── Jumlah Terjual ───────────────────────────
            sold_count = _safe_text(card, [
                "[data-testid='spanProductSoldCount']",
                "span[class*='sold']",
                "span[class*='Sold']",
                "div[data-testid='divProductSoldCount'] span",
            ])

            # ── Link Produk ──────────────────────────────
            product_link = _safe_attr(card, [
                "a[data-testid='lnkProductContainer']",
                "a[href*='/products/']",
                "a[href*='tokopedia.com']",
            ], attr="href")

            # Hapus query string tracking dari link
            if product_link and "?" in product_link:
                product_link = product_link.split("?")[0]

            # Hanya simpan jika minimal ada nama dan harga
            if product_name or raw_price_text:
                results.append({
                    "Brand_Origin":    brand_label,
                    "Keyword":         keyword,
                    "Nama_Produk":     product_name,
                    "Harga_Mentah":    raw_price_text,
                    "Harga_Numerik":   price_int,
                    "Nama_Toko":       shop_name,
                    "Lokasi":          location,
                    "Jumlah_Terjual":  sold_count,
                    "Link_Produk":     product_link,
                })

        except Exception as e:
            print(f"   ⚠️  Skip produk karena error: {e}")
            continue

    print(f"   ✅ Berhasil mengambil {len(results)} data produk dari keyword ini.")
    return results


# ──────────────────────────────────────────────────────────────
# CELL 8 — Helper: Safe Text & Attribute Extractor
# ──────────────────────────────────────────────────────────────

def _safe_text(card: BeautifulSoup, selectors: list[str]) -> str | None:
    """
    Mencoba setiap selector secara berurutan dan mengembalikan teks pertama
    yang berhasil ditemukan. Mengembalikan None jika semua gagal.
    """
    for selector in selectors:
        try:
            element = card.select_one(selector)
            if element:
                return element.get_text(strip=True)
        except Exception:
            continue
    return None


def _safe_attr(card: BeautifulSoup, selectors: list[str], attr: str) -> str | None:
    """
    Mencoba setiap selector secara berurutan dan mengembalikan nilai atribut
    pertama yang berhasil ditemukan. Mengembalikan None jika semua gagal.
    """
    for selector in selectors:
        try:
            element = card.select_one(selector)
            if element and element.get(attr):
                return element[attr]
        except Exception:
            continue
    return None


print("✅ Fungsi helper _safe_text() dan _safe_attr() siap digunakan.")


# ──────────────────────────────────────────────────────────────
# CELL 9 — Eksekusi Utama (Main Runner)
# ──────────────────────────────────────────────────────────────

def main():
    all_data = []
    driver = create_driver()
    print("🚀 Browser headless berhasil diinisialisasi.\n")
    print("=" * 60)

    try:
        for idx, config in enumerate(SEARCH_CONFIG):
            keyword    = config["keyword"]
            brand      = config["brand"]

            # Scrape keyword ini
            result = scrape_tokopedia(driver, keyword, brand)
            all_data.extend(result)

            # Jeda acak antar keyword (kecuali keyword terakhir)
            if idx < len(SEARCH_CONFIG) - 1:
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                print(f"\n⏳ Jeda {delay:.1f} detik sebelum keyword berikutnya...\n")
                time.sleep(delay)

    except KeyboardInterrupt:
        print("\n⛔ Proses dihentikan manual oleh pengguna.")

    finally:
        driver.quit()
        print("\n🔒 Browser ditutup.")

    # ── Buat DataFrame ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📊 Membuat DataFrame...")

    df = pd.DataFrame(all_data)

    if df.empty:
        print("⚠️  Tidak ada data yang berhasil di-scrape.")
        return df

    # Reorder kolom
    column_order = [
        "Brand_Origin", "Keyword", "Nama_Produk",
        "Harga_Mentah", "Harga_Numerik",
        "Nama_Toko", "Lokasi", "Jumlah_Terjual", "Link_Produk",
    ]
    df = df[[col for col in column_order if col in df.columns]]

    # Reset index
    df = df.reset_index(drop=True)

    print(f"\n✅ DataFrame berhasil dibuat!")
    print(f"   Total baris : {len(df)}")
    print(f"   Total kolom : {len(df.columns)}")
    print(f"\n📋 Preview 5 baris pertama:")
    print(df.head())

    # ── Ekspor ke CSV ─────────────────────────────────────────
    output_filename = "raw_market_data_lightweight_concrete.csv"
    df.to_csv(output_filename, index=False, encoding="utf-8-sig")
    print(f"\n💾 Data berhasil disimpan ke: {output_filename}")

    # ── Ringkasan per Brand ───────────────────────────────────
    print("\n📈 Ringkasan per Brand:")
    summary = df.groupby("Brand_Origin").agg(
        Jumlah_Produk=("Nama_Produk", "count"),
        Harga_Rata_Rata=("Harga_Numerik", "mean"),
        Harga_Minimum=("Harga_Numerik", "min"),
        Harga_Maksimum=("Harga_Numerik", "max"),
    ).round(0)
    print(summary.to_string())

    return df


# Jalankan!
df_result = main()
