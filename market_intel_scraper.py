"""
╔══════════════════════════════════════════════════════════════════╗
║  MARKET INTELLIGENCE SCRAPER — Bata Ringan (AAC) Jawa Timur     ║
║  Project : Market Intelligence Dashboard - Building Materials    ║
║  Platforms: Tokopedia · Shopee · Depo Bangunan · Mitra10        ║
║  Output  : raw_market_data_lightweight_concrete.csv             ║
╚══════════════════════════════════════════════════════════════════╝

CARA PAKAI DI JUPYTER / GOOGLE COLAB:
  1. Jalankan Cell 1  → Install dependencies (sekali saja)
  2. Jalankan Cell 2  → Import & konstanta
  3. Jalankan Cell 3  → Utility functions (driver, scroll, parser)
  4. Jalankan Cell 4  → Scraper per platform
  5. Jalankan Cell 5  → Post-processing helper
  6. Jalankan Cell 6  → MAIN RUNNER (eksekusi scraping)

GOOGLE COLAB SETUP (uncomment jika di Colab):
  !apt-get update -q && apt-get install -y -q chromium-browser chromium-chromedriver
  !pip install selenium webdriver-manager beautifulsoup4 pandas lxml -q
"""

# ══════════════════════════════════════════════════════════════════
# CELL 1 ── Install Dependencies
# ══════════════════════════════════════════════════════════════════
# Uncomment baris berikut jika berjalan di Google Colab:
#
# !apt-get update -q && apt-get install -y -q chromium-browser chromium-chromedriver
# !pip install selenium webdriver-manager beautifulsoup4 pandas lxml -q


# ══════════════════════════════════════════════════════════════════
# CELL 2 ── Import Libraries & Konfigurasi
# ══════════════════════════════════════════════════════════════════
import re
import time
import random
import warnings
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# undetected_chromedriver — bypass Cloudflare/bot-detection Shopee
# Install: pip install undetected-chromedriver
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False
    print("⚠️  undetected_chromedriver tidak tersedia. Shopee mungkin diblokir.")
    print("   Jalankan: pip install undetected-chromedriver")

warnings.filterwarnings("ignore")

# ─── Konstanta Umum ────────────────────────────────────────────────
OUTPUT_FILENAME  = "raw_market_data_lightweight_concrete.csv"
SCROLL_COUNT     = 4       # Jumlah scroll per halaman
SCROLL_PAUSE     = 1.8     # Jeda tiap scroll (detik)
WAIT_TIMEOUT     = 18      # Timeout WebDriverWait (detik)
DELAY_MIN        = 3.5     # Jeda minimum antar keyword (detik)
DELAY_MAX        = 8.0     # Jeda maksimum antar keyword (detik)

# ─── Daftar Keyword & Brand Label ─────────────────────────────────
#
# Kelompok A: Brand Awareness
# Kelompok B: Spesifikasi & Regional
# Kelompok C: Cross-selling (Mortar / Accessories)
#
SEARCH_CONFIG = [
    # ── Brand Awareness ──────────────────────────────────────────
    {"keyword": "Bata Ringan Blesscon",          "brand": "Blesscon",          "group": "Brand"},
    {"keyword": "Bata Ringan Citicon",           "brand": "Citicon",           "group": "Brand"},
    {"keyword": "Bata Ringan Grand Elephant",    "brand": "Grand Elephant",    "group": "Brand"},
    {"keyword": "Bata Ringan Falcon",            "brand": "Falcon",            "group": "Brand"},
    {"keyword": "Bata Ringan Hebel",             "brand": "Hebel",             "group": "Brand"},
    {"keyword": "Bata Ringan Prime Mortar",      "brand": "Prime Mortar",      "group": "Brand"},
    {"keyword": "Bata Ringan Focon",             "brand": "Focon",             "group": "Brand"},
    {"keyword": "Bata Ringan Great Wall",        "brand": "Great Wall",        "group": "Brand"},
    # ── Spesifikasi & Regional ───────────────────────────────────
    {"keyword": "Bata Ringan Surabaya Murah",    "brand": "General",           "group": "Regional"},
    {"keyword": "Bata Ringan Sidoarjo Grosir",   "brand": "General",           "group": "Regional"},
    {"keyword": "Bata Ringan Gresik m3",         "brand": "General",           "group": "Regional"},
    {"keyword": "Bata Ringan 7.5cm",             "brand": "General",           "group": "Spec"},
    {"keyword": "Bata Ringan 10cm",              "brand": "General",           "group": "Spec"},
    {"keyword": "Hebel Surabaya satu rit",       "brand": "Hebel",             "group": "Regional"},
    {"keyword": "Bata Ringan per kubik",         "brand": "General",           "group": "Spec"},
    # ── Cross-selling (Accessories) ──────────────────────────────
    {"keyword": "Semen Mortar Perekat Bata Ringan", "brand": "Mortar/Accessories", "group": "Cross-sell"},
    {"keyword": "Mortar Instan Surabaya",           "brand": "Mortar/Accessories", "group": "Cross-sell"},
    {"keyword": "Thinbed Bata Ringan",              "brand": "Mortar/Accessories", "group": "Cross-sell"},
]

# ─── Platform URL Templates ────────────────────────────────────────
# ─── Platform URL Templates ────────────────────────────────────────
#
# Catatan Tokopedia:
#   &navsource=home           = navigasi dari home (diperlukan)
#   &location=surabaya        = filter lokasi penjual ke area Surabaya/Jatim
#                               Tokopedia menggunakan nama kota (bukan kode area)
#                               sehingga 'surabaya' otomatis mencakup seller
#                               di Surabaya, Sidoarjo, Gresik (area Gerbangkertosusila)
#
PLATFORM_URLS = {
    "Tokopedia":     (
        "https://www.tokopedia.com/search"
        "?st=product&q={query}&navsource=home"
        "&location=surabaya"   # pre-filter: hanya tampilkan penjual area Jatim
    ),
    "Shopee":        "https://shopee.co.id/search?keyword={query}",
    "DepoBangunan":  "https://www.depobangunan.co.id/catalogsearch/result/?q={query}",
    "Mitra10":       "https://www.mitra10.com/catalogsearch/result/?q={query}",
}

# Platform yang akan di-scrape (set True/False untuk enable/disable)
PLATFORMS_ENABLED = {
    "Tokopedia":    True,
    "Shopee":       True,
    "DepoBangunan": True,
    "Mitra10":      True,
}

print("✅ Libraries imported, konfigurasi selesai.")
print(f"   Total keyword : {len(SEARCH_CONFIG)}")
print(f"   Platform aktif: {[p for p, v in PLATFORMS_ENABLED.items() if v]}")


# ══════════════════════════════════════════════════════════════════
# CELL 3 ── Utility Functions
# ══════════════════════════════════════════════════════════════════

# ─── 3.1 Setup WebDriver ──────────────────────────────────────────
def create_driver(is_colab: bool = False) -> webdriver.Chrome:
    """
    Membuat instance WebDriver Chrome headless.

    Strategi ChromeDriver (berurutan):
      1. Google Colab       → gunakan /usr/bin/chromedriver (system)
      2. Selenium >= 4.6    → Selenium Manager built-in (otomatis)
         Tidak perlu webdriver-manager. Selenium akan download
         ChromeDriver yang sesuai dengan versi Chrome yang terinstall.

    Set is_colab=True jika berjalan di Google Colab.
    """
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=id-ID")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    if is_colab:
        # ─ Google Colab: pakai Chromium system ────────────────────────
        opts.binary_location = "/usr/bin/chromium-browser"
        service = Service("/usr/bin/chromedriver")
        driver  = webdriver.Chrome(service=service, options=opts)
    else:
        # ─ Lokal / Jupyter: Selenium Manager (built-in Selenium 4.6+) ─
        # Biarkan Service() tanpa argumen → Selenium Manager otomatis
        # mendeteksi versi Chrome & mendownload ChromeDriver yang tepat.
        # Ini menggantikan webdriver-manager agar tidak ada mismatch
        # (penyebab WinError 193 di Windows).
        driver = webdriver.Chrome(options=opts)   # <— tidak perlu Service

    # Sembunyikan tanda WebDriver dari JavaScript
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return driver


# ─── 3.2 Setup Driver Khusus Shopee (undetected_chromedriver) ───────
def create_shopee_driver(is_colab: bool = False):
    """
    Driver khusus untuk Shopee menggunakan undetected_chromedriver.

    Shopee menggunakan Cloudflare Bot Management yang mendeteksi:
    - navigator.webdriver flag
    - Canvas & WebGL fingerprint khas headless Chrome
    - Chrome automation extension markers

    undetected_chromedriver mem-patch semua ini secara otomatis.
    Di Windows lokal, berjalan non-headless (window terbuka sebentar)
    karena headless masih bisa dideteksi Shopee.
    """
    if is_colab or not UC_AVAILABLE:
        # Fallback ke driver biasa kalau di Colab atau uc belum install
        return create_driver(is_colab=is_colab)

    opts = uc.ChromeOptions()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=id-ID")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # headless=False — window Shopee akan muncul sebentar saat scraping.
    # Ini DISENGAJA karena Shopee mendeteksi headless mode.
    # Window akan otomatis tertutup setelah scraping selesai.
    # Auto-detect versi Chrome agar version_main selalu matching
    chrome_version = 146  # default fallback
    try:
        import subprocess
        # Windows: baca versi Chrome dari registry
        reg = subprocess.run(
            ["reg", "query",
             r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon",
             "/v", "version"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r"(\d+)\.\d+\.\d+\.\d+", reg.stdout)
        if match:
            chrome_version = int(match.group(1))
    except Exception:
        pass
    print(f"   🔍 Chrome version terdeteksi: {chrome_version}")

    driver = uc.Chrome(options=opts, headless=False, version_main=chrome_version)
    print(f"   🛡️  Shopee driver: undetected_chromedriver v{chrome_version} (bypass bot-detection)")
    return driver


# ─── 3.2 Auto-Scroll ──────────────────────────────────────────────
def auto_scroll(driver: webdriver.Chrome,
                count: int = SCROLL_COUNT,
                pause: float = SCROLL_PAUSE) -> None:
    """
    Scroll ke bawah sebanyak `count` kali untuk memuat lazy-load content.
    Berhenti otomatis jika halaman tidak bertambah tinggi.
    """
    last_h = driver.execute_script("return document.body.scrollHeight")
    for i in range(count):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            print(f"      ↕ Scroll {i+1}/{count} — halaman tidak bertambah, stop.")
            break
        last_h = new_h
        print(f"      ↕ Scroll {i+1}/{count} selesai.")


# ─── 3.3 Safe Element Extractor ───────────────────────────────────
def _get_text(card: BeautifulSoup, selectors: list) -> str | None:
    """Coba selector satu per satu, return teks pertama yang berhasil."""
    for sel in selectors:
        try:
            el = card.select_one(sel)
            if el:
                return el.get_text(strip=True) or None
        except Exception:
            continue
    return None


def _get_attr(card: BeautifulSoup, selectors: list, attr: str) -> str | None:
    """Coba selector satu per satu, return atribut pertama yang berhasil."""
    for sel in selectors:
        try:
            el = card.select_one(sel)
            if el and el.get(attr):
                return el[attr]
        except Exception:
            continue
    return None


# ─── 3.4 Price Parser ─────────────────────────────────────────────
def parse_price(text: str | None) -> int | None:
    """
    Ubah string harga → integer.
    Contoh: 'Rp 1.250.000' → 1250000
    """
    if not text:
        return None
    cleaned = re.sub(r"[^0-9]", "", text)
    return int(cleaned) if cleaned else None


# ─── 3.5 Rating Parser ────────────────────────────────────────────
def parse_rating(text: str | None) -> float | None:
    """
    Ubah string rating → float.
    Contoh: '4.8' → 4.8, '(4.5)' → 4.5
    """
    if not text:
        return None
    match = re.search(r"(\d+[.,]\d+|\d+)", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


# ─── 3.6 Unit Type Extractor ──────────────────────────────────────
def extract_unit_type(product_name: str | None) -> str | None:
    """
    Ekstrak satuan dari nama produk.
    Contoh: 'Bata Ringan 7.5cm per m3' → 'm3'
    """
    if not product_name:
        return None
    name_lower = product_name.lower()
    if re.search(r"(per\s*m3|/m3|m³|kubik|per\s*kubik)", name_lower):
        return "m3"
    if re.search(r"\bm3\b", name_lower):
        return "m3"
    if re.search(r"\b(palet|pallet)\b", name_lower):
        return "palet"
    if re.search(r"\b(rit|truk|truck)\b", name_lower):
        return "rit"
    if re.search(r"\b(m2|/m2|per\s*m2)\b", name_lower):
        return "m2"
    if re.search(r"\b(pcs|biji|buah|batu|lembar)\b", name_lower):
        return "pcs"
    return None


# ─── 3.7 Clean Product URL ────────────────────────────────────────
def clean_url(url: str | None, base: str = "") -> str | None:
    """
    Hapus query string tracking dari URL produk.
    Tambahkan base URL jika URL relatif.
    """
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/") and base:
        url = base.rstrip("/") + url
    return url.split("?")[0] if "?" in url else url


print("✅ Utility functions siap.")


# ─── 3.8 Retail Keyword Simplifier ───────────────────────────────
def retail_keyword(keyword: str) -> str:
    """
    Sederhanakan keyword untuk platform retail (Depo Bangunan, Mitra10).

    Platform retail tidak jual per-brand (Blesscon, Citicon, dll),
    sehingga keyword 'Bata Ringan Blesscon' menghasilkan 0 hasil.
    Fungsi ini mengekstrak kategori produk yang relevan:

      'Bata Ringan Blesscon Surabaya' → 'Bata Ringan'
      'Hebel Surabaya satu rit'       → 'Hebel'
      'Semen Mortar Perekat Bata Ringan' → 'Mortar Perekat'
      'Thinbed Bata Ringan'           → 'Thinbed'
    """
    low = keyword.lower()
    if "bata ringan" in low:
        return "Bata Ringan"
    if "thinbed" in low:
        return "Thinbed Mortar"
    if "mortar" in low or "semen perekat" in low:
        return "Mortar Perekat"
    if "hebel" in low:
        return "Hebel"
    # Fallback: dua kata pertama
    return " ".join(keyword.split()[:2])


# ══════════════════════════════════════════════════════════════════
# CELL 4 ── Platform Scrapers
# ══════════════════════════════════════════════════════════════════

# ─── 4.1 Tokopedia Scraper ────────────────────────────────────────
def scrape_tokopedia(driver: webdriver.Chrome,
                     keyword: str,
                     brand: str,
                     scraped_at: str) -> list[dict]:
    """Scrape halaman hasil pencarian Tokopedia."""
    results = []
    url = PLATFORM_URLS["Tokopedia"].format(query=quote_plus(keyword))
    print(f"\n   🛒 [Tokopedia] '{keyword}'")

    try:
        driver.get(url)

        # Tunggu setidaknya satu kartu produk muncul
        # ── Tokopedia UI terbaru: gunakan divSRPContentProducts sebagai penanda ──
        # Selector 'master-product-card' sudah dihapus dari Tokopedia (per 2025)
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='divSRPContentProducts']")
            )
        )
        print("      ✅ Konten SRP terdeteksi.")
    except TimeoutException:
        print(f"      ⚠️  Timeout setelah {WAIT_TIMEOUT}s, lanjut dengan konten yang ada...")
    except Exception as e:
        print(f"      ❌ Error load halaman: {e}")
        return results

    auto_scroll(driver)

    soup = BeautifulSoup(driver.page_source, "lxml")

    # ── Ambil container SRP ───────────────────────────────────────────
    # Tokopedia sekarang membungkus semua produk di dalam satu div container.
    # Kartu individual adalah tag <a> di dalamnya.
    srp_container = (
        soup.select_one("[data-testid='divSRPContentProducts']")
        or soup.select_one("[data-testid='divSRPLazyProductWrapper']")
        or soup.body  # fallback terakhir: seluruh body
    )

    # Setiap <a> yang memiliki href ke produk Tokopedia = 1 kartu produk
    cards = [
        a for a in srp_container.select("a[href]")
        if "/p/" in (a.get("href") or "") or "tokopedia.com" in (a.get("href") or "")
    ]

    # Deduplikasi berdasarkan href (kadang ada <a> ganda dalam 1 kartu)
    seen_hrefs = set()
    unique_cards = []
    for c in cards:
        h = c.get("href", "").split("?")[0]
        if h and h not in seen_hrefs:
            seen_hrefs.add(h)
            unique_cards.append(c)
    cards = unique_cards

    print(f"      📦 {len(cards)} kartu produk ditemukan.")

    for card in cards:
        try:
            all_text_els = card.find_all(string=True)

            # ── Nama Produk ───────────────────────────────────────────
            # Nama biasanya span teks terpanjang dalam kartu, bukan angka/harga
            name = None
            for el in card.find_all(["span", "div", "p"]):
                txt = el.get_text(strip=True)
                # Skip jika teks terlalu pendek, mengandung Rp, atau hanya angka
                if (len(txt) > 10
                        and "Rp" not in txt
                        and not re.match(r"^[\d.,+%\s]+$", txt)
                        and "terjual" not in txt.lower()
                        and len(el.find_all(True)) < 5):  # bukan wrapper kompleks
                    name = txt
                    break

            # ── Harga ─────────────────────────────────────────────────
            # Harga selalu diawali "Rp" di Tokopedia
            raw_price = None
            for el in card.find_all(["span", "div", "p"]):
                txt = el.get_text(strip=True)
                if txt.startswith("Rp") and re.search(r"\d", txt):
                    raw_price = txt
                    break

            # ── Jumlah Terjual ────────────────────────────────────────
            sold = None
            for txt in all_text_els:
                t = str(txt).strip()
                if "terjual" in t.lower() and t != "terjual":
                    sold = t
                    break

            # ── Rating ────────────────────────────────────────────────
            rating_text = None
            for el in card.find_all(["span", "div"]):
                txt = el.get_text(strip=True)
                if re.match(r"^[1-5](\.\d)?$", txt):  # angka 1.0–5.0
                    rating_text = txt
                    break

            # ── Lokasi ───────────────────────────────────────────────
            # Tokopedia menampilkan nama kota sebagai teks pendek di bagian bawah kartu
            location = None
            kota_jatim = (
                "surabaya|sidoarjo|gresik|lamongan|mojokerto|pasuruan|malang|"
                "tuban|bojonegoro|jombang|kediri|blitar|madiun|ngawi|pacitan|"
                "ponorogo|nganjuk|magetan|trenggalek|tulungagung|batu|"
                "probolinggo|lumajang|jember|banyuwangi|situbondo|bondowoso|"
                "bangkalan|sampang|pamekasan|sumenep"
            )
            for el in card.find_all(["span", "div", "p"]):
                txt = el.get_text(strip=True).lower()
                if re.search(kota_jatim, txt) and len(txt) < 30:
                    location = el.get_text(strip=True)
                    break
            # Jika tidak ada kota Jatim spesifik, ambil teks kota terakhir di kartu
            if not location:
                for el in reversed(card.find_all(["span", "div"])):
                    txt = el.get_text(strip=True)
                    if (5 < len(txt) < 25
                            and not re.search(r"(Rp|\d{4,}|terjual|★)", txt)
                            and len(el.find_all(True)) == 0):  # leaf element
                        location = txt
                        break

            # ── Link Produk ───────────────────────────────────────────
            link = clean_url(card.get("href"))

            if name or raw_price:
                results.append(_build_row(
                    scraped_at=scraped_at,
                    platform="Tokopedia",
                    keyword=keyword,
                    brand=brand,
                    name=name,
                    raw_price=raw_price,
                    shop=None,   # nama toko tidak mudah dibedakan strukturnya
                    location=location,
                    sold=sold,
                    rating_text=rating_text,
                    url=link,
                ))
        except Exception as e:
            print(f"      ⚠️  Skip card: {e}")
            continue

    print(f"      ✅ {len(results)} baris data berhasil diambil.")
    return results


# ─── 4.2 Shopee Scraper ───────────────────────────────────────────
def scrape_shopee(driver: webdriver.Chrome,
                  keyword: str,
                  brand: str,
                  scraped_at: str) -> list[dict]:
    """Scrape halaman hasil pencarian Shopee.

    Selector dikonfirmasi dari live DOM inspection:
      kartu produk  → li[data-sqe='item']  ← STABLE data attribute
      nama produk   → aria-label 'View product: ...'  ← STABLE
      harga         → span 'Rp' + span angka bersebelahan
      lokasi        → span.ml-[3px] (kota penjual)
      rating        → div teks '5.0' (pola angka 1-5)
      terjual       → tidak selalu muncul, text-based fallback
    """
    results = []
    url = PLATFORM_URLS["Shopee"].format(query=quote_plus(keyword))
    print(f"\n   🛍️  [Shopee] '{keyword}'")

    try:
        driver.get(url)

        # uc.Chrome sudah bypass fingerprint Shopee otomatis.
        # Hanya perlu dismiss popup bahasa jika muncul.
        time.sleep(3)
        try:
            driver.execute_script("""
                document.querySelectorAll('button, span').forEach(el => {
                    if (el.textContent.trim() === 'Bahasa Indonesia') el.click();
                });
            """)
            time.sleep(1)
        except Exception:
            pass

        # Tunggu kartu produk — selector dikonfirmasi live
        WebDriverWait(driver, WAIT_TIMEOUT + 8).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li[data-sqe='item']")
            )
        )
        print("      ✅ Kartu produk Shopee terdeteksi.")
    except TimeoutException:
        print(f"      ⚠️  Timeout Shopee {WAIT_TIMEOUT+8}s — skip keyword ini.")
        return results
    except Exception as e:
        print(f"      ❌ Error load Shopee: {e}")
        return results

    auto_scroll(driver, count=3, pause=2.5)

    soup = BeautifulSoup(driver.page_source, "lxml")

    # li[data-sqe='item'] — dikonfirmasi STABLE dari live inspection
    cards = soup.select("li[data-sqe='item']")
    print(f"      📦 {len(cards)} kartu produk ditemukan.")

    for card in cards:
        try:
            # ── Nama Produk ───────────────────────────────────────────────
            # aria-label="View product: [NAMA]" adalah yang paling stabil
            name = None
            view_link = card.select_one("a[aria-label*='View product']")
            if view_link:
                aria = view_link.get("aria-label", "")
                name = re.sub(r"(?i)^view product:\s*", "", aria).strip() or None
            # Fallback: div dengan line-clamp (nama produk di card body)
            if not name:
                name_el = card.select_one("div.whitespace-normal, div[class*='line-clamp']")
                if name_el:
                    name = name_el.get_text(strip=True) or None

            # ── Harga ─────────────────────────────────────────────────
            # Shopee split harga: <span>Rp</span><span>7.891.200</span>
            # Gabungkan dua span bersebelahan
            raw_price = None
            spans = card.find_all("span")
            for i, sp in enumerate(spans):
                if sp.get_text(strip=True) == "Rp" and i + 1 < len(spans):
                    angka = spans[i + 1].get_text(strip=True)
                    if re.search(r"\d", angka):
                        raw_price = "Rp" + angka
                        break
            # Fallback text-based
            if not raw_price:
                for el in card.find_all(["span", "div"]):
                    txt = el.get_text(strip=True)
                    if txt.startswith("Rp") and re.search(r"\d", txt):
                        raw_price = txt
                        break

            # ── Lokasi ────────────────────────────────────────────────
            # data-testid='a11y-label' dengan prefix 'location-' — STABLE
            location = None
            loc_el = card.select_one("[data-testid='a11y-label'][class*='location']")
            if loc_el:
                location = loc_el.get_text(strip=True)
            # Fallback: span.ml-[3px] atau cek nama kota Jatim secara teks
            if not location:
                for sp in card.find_all("span"):
                    txt = sp.get_text(strip=True)
                    if (3 < len(txt) < 25
                            and not re.search(r"(Rp|\d{3,}|terjual|\+)", txt)
                            and len(sp.find_all(True)) == 0):
                        location = txt
                        break

            # ── Jumlah Terjual ─────────────────────────────────────────────
            sold = None
            for txt in card.find_all(string=True):
                t = str(txt).strip()
                if "terjual" in t.lower() and len(t) < 30:
                    sold = t
                    break

            # ── Rating ─────────────────────────────────────────────────
            # Shopee menampilkan rating sebagai angka 'X.X' di div sendiri
            rating_text = None
            for el in card.find_all(["div", "span"]):
                if len(el.find_all(True)) == 0:  # leaf element
                    txt = el.get_text(strip=True)
                    if re.match(r"^[1-5](\.\d)?$", txt):
                        rating_text = txt
                        break

            # ── Link Produk ───────────────────────────────────────────────
            link_el = card.select_one("a[aria-label*='View product'], a[href]")
            link = None
            if link_el and link_el.get("href"):
                h = link_el["href"]
                link = ("https://shopee.co.id" + h) if h.startswith("/") else h

            if name or raw_price:
                results.append(_build_row(
                    scraped_at=scraped_at,
                    platform="Shopee",
                    keyword=keyword,
                    brand=brand,
                    name=name,
                    raw_price=raw_price,
                    shop=None,   # nama toko tidak tersedia di search card
                    location=location,
                    sold=sold,
                    rating_text=rating_text,
                    url=clean_url(link),
                ))
        except Exception as e:
            print(f"      ⚠️  Skip card: {e}")
            continue

    print(f"      ✅ {len(results)} baris data berhasil diambil.")
    return results


# ─── 4.3 Depo Bangunan Scraper ────────────────────────────────────
def scrape_depobangunan(driver: webdriver.Chrome,
                        keyword: str,
                        brand: str,
                        scraped_at: str) -> list[dict]:
    """Scrape halaman pencarian DepoBangunan.co.id.

    Selector dikonfirmasi dari live DOM inspection (Magento 2 — stabil):
      kartu produk  → li.product-item
      nama produk   → a.product-item-link
      harga         → [data-price-type='finalPrice'] .price
      terjual       → strong.sold-qty-count (unik ke DepoBangunan)
      link          → a.product-item-link[href]
    """
    results = []
    # ── Retail keyword: Depo Bangunan tidak membedakan by-brand ────
    # Konfirmasi dari live inspection: 'Bata Ringan Blesscon' → 0 produk
    # karena Depo tidak jual per-brand. Gunakan keyword generik.
    retail_kw = retail_keyword(keyword)
    url = PLATFORM_URLS["DepoBangunan"].format(query=quote_plus(retail_kw))
    print(f"\n   🏗️  [DepoBangunan] '{keyword}' → keyword retail: '{retail_kw}'")

    try:
        driver.get(url)
        # li.product-item = Magento 2 standard, sangat stabil
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li.product-item")
            )
        )
    except TimeoutException:
        print(f"      ⚠️  Timeout atau tidak ada produk ditemukan.")
        return results
    except Exception as e:
        print(f"      ❌ Error load halaman: {e}")
        return results

    auto_scroll(driver, count=2, pause=1.5)
    soup = BeautifulSoup(driver.page_source, "lxml")

    # li.product-item — dikonfirmasi dari live inspection
    cards = soup.select("li.product-item")
    print(f"      📦 {len(cards)} kartu produk ditemukan.")

    for card in cards:
        try:
            # Nama — a.product-item-link (dikonfirmasi live)
            name = _get_text(card, [
                "a.product-item-link",
                ".product-item-name a",
            ])
            # Harga — finalPrice (dikonfirmasi live, ada data-price-amount)
            raw_price = _get_text(card, [
                "[data-price-type='finalPrice'] .price",
                "[data-price-type='finalPrice'] span",
                ".price-wrapper .price",
                "span.price",
            ])
            # Terjual — strong.sold-qty-count (dikonfirmasi dari live HTML)
            sold_el = card.select_one("strong.sold-qty-count")
            sold = (sold_el.get_text(strip=True) + " terjual") if sold_el else None

            # Rating
            rating_text = _get_text(card, ["div.rating-summary span[style]"])

            # Link
            link = _get_attr(card, ["a.product-item-link"], "href")

            if name or raw_price:
                results.append(_build_row(
                    scraped_at=scraped_at,
                    platform="DepoBangunan",
                    keyword=keyword,
                    brand=brand,
                    name=name,
                    raw_price=raw_price,
                    shop="Depo Bangunan",
                    location="Surabaya/Jawa Timur",
                    sold=sold,
                    rating_text=rating_text,
                    url=clean_url(link),
                ))
        except Exception as e:
            print(f"      ⚠️  Skip card: {e}")
            continue

    print(f"      ✅ {len(results)} baris data berhasil diambil.")
    return results



# ─── 4.4 Mitra10 Scraper ─────────────────────────────────────────
def scrape_mitra10(driver: webdriver.Chrome,
                   keyword: str,
                   brand: str,
                   scraped_at: str) -> list[dict]:
    """
    Scrape halaman pencarian Mitra10.com.

    Karakteristik Mitra10:
    - Framework: Material-UI (React), perlu Selenium untuk render JS
    - Navigasi: Paginasi standar (bukan infinite scroll)
    - Harga: Tanpa login, kurs IDR ditampilkan langsung
    - Lokasi toko: Diambil dari header 'Anda Belanja Di'
    - Selector utama (hasil live inspection):
        kartu produk  → a.gtm_mitra10_cta_product
        nama produk   → a.gtm_mitra10_cta_product p
        harga         → span.price__final  (atau span[class*='price__final'])
        total terjual → elemen teks mengandung 'terjual'
        rating        → p.rating-count  (atau p[class*='rating-count'])
    """
    results = []
    # ── Retail keyword: Mitra10 tidak membedakan by-brand ──────────
    # Konfirmasi dari live inspection: 'Bata Ringan Blesscon' → 0 produk
    retail_kw = retail_keyword(keyword)
    url = PLATFORM_URLS["Mitra10"].format(query=quote_plus(retail_kw))
    print(f"\n   🏪 [Mitra10] '{keyword}' → keyword retail: '{retail_kw}'")

    try:
        driver.get(url)

        # Mitra10 pakai React/MUI — tunggu kartu produk selesai render
        WebDriverWait(driver, WAIT_TIMEOUT + 5).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a.gtm_mitra10_cta_product")
            )
        )
    except TimeoutException:
        print(f"      ⚠️  Timeout: produk Mitra10 tidak terdeteksi dalam {WAIT_TIMEOUT+5}s.")
        return results
    except Exception as e:
        print(f"      ❌ Error load halaman Mitra10: {e}")
        return results

    # Mitra10 pakai paginasi, bukan infinite scroll —
    # scroll tetap dilakukan agar lazy-load gambar ter-trigger
    auto_scroll(driver, count=2, pause=1.5)

    # ── Ambil lokasi toko dari header global ──────────────────────
    try:
        store_header = driver.find_element(
            By.XPATH,
            "//*[contains(text(), 'Anda Belanja Di') or contains(text(), 'MITRA10')]"
        ).text
        # Contoh: 'Anda Belanja Di MITRA10 KEDUNGDORO' → 'MITRA10 KEDUNGDORO'
        mitra_location = re.sub(
            r"(?i)(anda\s+belanja\s+di\s*)", "", store_header
        ).strip()
    except Exception:
        mitra_location = "Mitra10 (Jawa Timur)"

    soup = BeautifulSoup(driver.page_source, "lxml")

    # Kartu produk utama — setiap <a> adalah satu produk
    cards = (
        soup.select("a.gtm_mitra10_cta_product")
        or soup.select("a[class*='gtm_mitra10']")
        or soup.select("div[class*='product'] a[href]")
    )
    print(f"      📦 {len(cards)} kartu produk ditemukan. (Lokasi: {mitra_location})")

    for card in cards:
        try:
            # Nama produk — tag <p> pertama di dalam kartu
            name = _get_text(card, [
                "p",
                "span[class*='name']",
                "div[class*='name']",
            ])

            # Harga — gunakan span.price__final (dikonfirmasi dari live inspection)
            raw_price = _get_text(card, [
                "span.price__final",
                "span[class*='price__final']",
                "span[class*='price']",
                "div[class*='price'] span",
            ])

            # Total terjual — .sold-container p (dikonfirmasi live) + text fallback
            sold = None
            sold_el = card.select_one(".sold-container p, p[class*='sold']")
            if sold_el:
                sold = sold_el.get_text(strip=True)
            if not sold:
                for txt in card.find_all(string=True):
                    if "terjual" in str(txt).lower():
                        sold = str(txt).strip()
                        break

            # Rating — p.rating-count berisi angka skor
            rating_text = _get_text(card, [
                "p.rating-count",
                "p[class*='rating-count']",
                "span[class*='rating']",
                "div[class*='rating'] p",
            ])

            # Link produk — href dari elemen <a> itu sendiri
            link = card.get("href")

            if name or raw_price:
                results.append(_build_row(
                    scraped_at=scraped_at,
                    platform="Mitra10",
                    keyword=keyword,
                    brand=brand,
                    name=name,
                    raw_price=raw_price,
                    shop=mitra_location,        # nama cabang Mitra10
                    location=mitra_location,
                    sold=sold,
                    rating_text=rating_text,
                    url=clean_url(link, "https://www.mitra10.com"),
                ))
        except Exception as e:
            print(f"      ⚠️  Skip card: {e}")
            continue

    print(f"      ✅ {len(results)} baris data berhasil diambil.")
    return results


# ══════════════════════════════════════════════════════════════════
# CELL 5 ── Row Builder & Post-Processing
# ══════════════════════════════════════════════════════════════════

# ─── 5.1 Row Builder (Schema Standar) ─────────────────────────────
def _build_row(scraped_at, platform, keyword, brand,
               name, raw_price, shop, location,
               sold, rating_text, url) -> dict:
    """
    Membangun satu baris data sesuai skema kolom yang telah disepakati.

    Kolom Output:
    scraped_at | search_keyword | brand_label | platform
    product_name | price_numeric | unit_type
    store_name | store_location | total_sold | rating_product | product_url
    """
    return {
        "scraped_at":     scraped_at,
        "search_keyword": keyword,
        "brand_label":    brand,
        "platform":       platform,
        "product_name":   name,
        "price_numeric":  parse_price(raw_price),
        "unit_type":      extract_unit_type(name),
        "store_name":     shop,
        "store_location": location,
        "total_sold":     sold,
        "rating_product": parse_rating(rating_text),
        "product_url":    url,
    }


# ─── 5.2 Post-Processing DataFrame ────────────────────────────────
def post_process(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bersihkan dan enrichment DataFrame sebelum di-export:
    - Drop baris tanpa nama_produk DAN price_numeric
    - Standarisasi store_location (filter Surabaya/Sidoarjo/Gresik)
    - Normalisasi total_sold (angka saja)
    - Tambah flag is_east_java
    """
    if df.empty:
        return df

    # Drop baris kosong
    df = df.dropna(subset=["product_name", "price_numeric"], how="all")

    # ── Flag wilayah Jawa Timur ────────────────────────────────────────────
    # Mencakup semua 38 kabupaten/kota Jawa Timur:
    # 9 kota: Surabaya, Malang, Madiun, Kediri, Blitar, Pasuruan,
    #          Mojokerto, Probolinggo, Batu
    # 29 kabupaten: Sidoarjo, Gresik, Lamongan, Tuban, Bojonegoro,
    #               Jombang, Nganjuk, Madiun, Magetan, Ngawi, Ponorogo,
    #               Pacitan, Trenggalek, Tulungagung, Blitar, Kediri,
    #               Malang, Lumajang, Jember, Banyuwangi, Bondowoso,
    #               Situbondo, Probolinggo, Pasuruan, Mojokerto, Jombang,
    #               Bangkalan, Sampang, Pamekasan, Sumenep (Madura)
    jatim_pattern = (
        r"(surabaya|sidoarjo|gresik|lamongan|tuban|bojonegoro"
        r"|jombang|nganjuk|mojokerto|jombang"
        r"|madiun|magetan|ngawi|ponorogo|pacitan|trenggalek"
        r"|tulungagung|blitar|kediri|malang|batu"
        r"|lumajang|jember|banyuwangi|bondowoso|situbondo"
        r"|probolinggo|pasuruan"
        r"|bangkalan|sampang|pamekasan|sumenep"
        r"|jawa timur|jawa\.timur|jatim|east java)"
    )
    df["is_east_java"] = df["store_location"].str.lower().str.contains(
        jatim_pattern, na=False, regex=True
    )

    # Normalisasi total_sold → numerik estimasi
    def normalize_sold(txt):
        if pd.isna(txt):
            return None
        txt = str(txt).lower()
        match_rb = re.search(r"([\d,.]+)\s*rb", txt)
        match_num = re.search(r"([\d,.]+)", txt)
        if match_rb:
            return int(float(match_rb.group(1).replace(",", ".")) * 1000)
        elif match_num:
            return int(float(match_num.group(1).replace(",", "").replace(".", "")))
        return None

    df["total_sold_numeric"] = df["total_sold"].apply(normalize_sold)

    # ── Deduplikasi ──────────────────────────────────────────────────────
    # Layer 1: URL-based — produk yang sama muncul di pencarian keyword berbeda
    # Contoh: Depo "Bata Ringan" muncul 18x (satu per keyword brand)
    #         karena retail_keyword() semua brand → "Bata Ringan"
    before = len(df)
    url_mask = df["product_url"].notna() & (df["product_url"] != "")
    df_with_url    = df[url_mask].drop_duplicates(
        subset=["platform", "product_url"], keep="first"
    )
    df_without_url = df[~url_mask]
    df = pd.concat([df_with_url, df_without_url], ignore_index=True)

    # Layer 2: Content-based — produk tanpa URL atau URL berbeda tapi konten sama
    # Kunci: platform + nama produk (lowercase) + harga
    df["_name_key"] = df["product_name"].str.lower().str.strip().str[:60]
    df = df.drop_duplicates(
        subset=["platform", "_name_key", "price_numeric"], keep="first"
    )
    df = df.drop(columns=["_name_key"])

    after = len(df)
    if before > after:
        print(f"   🧹 Deduplikasi: {before} baris → {after} baris "
              f"({before - after} duplikat dihapus)")

    # Reset index
    df = df.reset_index(drop=True)

    # Urutan kolom final
    col_order = [
        "scraped_at", "platform", "search_keyword", "brand_label",
        "product_name", "price_numeric", "unit_type",
        "store_name", "store_location", "is_east_java",
        "total_sold", "total_sold_numeric",
        "rating_product", "product_url",
    ]
    df = df[[c for c in col_order if c in df.columns]]
    return df


print("✅ Row builder & post-processing siap.")


# ══════════════════════════════════════════════════════════════════
# CELL 6 ── MAIN RUNNER
# ══════════════════════════════════════════════════════════════════

def main(is_colab: bool = False) -> pd.DataFrame:
    """
    Eksekusi utama scraping semua keyword × semua platform aktif.

    Args:
        is_colab: Set True jika berjalan di Google Colab.

    Returns:
        pd.DataFrame hasil scraping yang sudah diproses.
    """
    all_data   = []
    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Buat driver reguler (Tokopedia, Depo, Mitra10) ───────────
    driver = create_driver(is_colab=is_colab)

    # ── Buat driver khusus Shopee (undetected_chromedriver) ───────
    shopee_driver = None
    if PLATFORMS_ENABLED.get("Shopee"):
        try:
            shopee_driver = create_shopee_driver(is_colab=is_colab)
        except Exception as e:
            print(f"   ⚠️  Gagal buat Shopee driver: {e}  → fallback ke driver reguler")
            shopee_driver = driver

    print("🚀 Browser headless berhasil diinisialisasi.")
    print(f"   Waktu scraping : {scraped_at}")
    print(f"   Total keyword  : {len(SEARCH_CONFIG)}")
    print(f"   Platform aktif : {[p for p, v in PLATFORMS_ENABLED.items() if v]}")
    print("=" * 65)

    scraper_map = {
        "Tokopedia":    scrape_tokopedia,
        "Shopee":       scrape_shopee,
        "DepoBangunan": scrape_depobangunan,
        "Mitra10":      scrape_mitra10,
    }

    try:
        total_combos = sum(
            1 for cfg in SEARCH_CONFIG
            for p, enabled in PLATFORMS_ENABLED.items() if enabled
        )
        current = 0

        for cfg in SEARCH_CONFIG:
            keyword = cfg["keyword"]
            brand   = cfg["brand"]
            group   = cfg.get("group", "")

            print(f"\n{'─'*65}")
            print(f"🔍 Keyword  : {keyword}")
            print(f"   Brand    : {brand}  |  Grup: {group}")

            for platform, enabled in PLATFORMS_ENABLED.items():
                if not enabled:
                    continue

                current += 1
                print(f"   Progress : {current}/{total_combos}")

                # Pilih driver yang tepat per platform
                active_driver = shopee_driver if platform == "Shopee" and shopee_driver else driver

                try:
                    rows = scraper_map[platform](active_driver, keyword, brand, scraped_at)
                    all_data.extend(rows)
                except Exception as e:
                    print(f"      ❌ Error platform {platform}: {e}")

                # Jeda acak antar platform dalam 1 keyword
                if current < total_combos:
                    d = random.uniform(DELAY_MIN, DELAY_MAX)
                    print(f"\n   ⏳ Jeda {d:.1f}s sebelum request berikutnya...")
                    time.sleep(d)

    except KeyboardInterrupt:
        print("\n\n⛔ Proses dihentikan manual.")

    finally:
        driver.quit()
        if shopee_driver and shopee_driver is not driver:
            shopee_driver.quit()
        print("\n🔒 Semua browser ditutup.")

    # ── Bangun DataFrame ──────────────────────────────────────────
    print("\n" + "=" * 65)
    print("📊 Membangun DataFrame...")

    if not all_data:
        print("⚠️  Tidak ada data yang berhasil diambil.")
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df = post_process(df)

    print(f"\n✅ DataFrame berhasil dibuat!")
    print(f"   Total baris  : {len(df):,}")
    print(f"   Total kolom  : {len(df.columns)}")

    # ── Export CSV ────────────────────────────────────────────────
    df.to_csv(OUTPUT_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\n💾 Disimpan ke: {OUTPUT_FILENAME}")

    # ── Ringkasan Harga per Brand × Platform ─────────────────────
    print("\n📈 Ringkasan Harga per Brand:")
    summary = (
        df[df["price_numeric"].notna()]
        .groupby(["brand_label", "platform"])
        .agg(
            Jumlah_Produk   = ("product_name",  "count"),
            Harga_Min       = ("price_numeric",  "min"),
            Harga_Rata2     = ("price_numeric",  "mean"),
            Harga_Max       = ("price_numeric",  "max"),
            Avg_Rating      = ("rating_product", "mean"),
        )
        .round({"Harga_Rata2": 0, "Avg_Rating": 2})
    )
    print(summary.to_string())

    print("\n📍 Distribusi Produk per Lokasi Jawa Timur:")
    jatim_df = df[df["is_east_java"] == True]
    print(f"   Produk dari Jatim : {len(jatim_df):,} dari {len(df):,} total")

    return df


# ─── Jalankan! ────────────────────────────────────────────────────
# Ganti is_colab=True jika berjalan di Google Colab
df_result = main(is_colab=False)
print("\n✅ Scraping selesai! Hasil tersimpan di:", OUTPUT_FILENAME)
