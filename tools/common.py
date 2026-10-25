# -*- coding: utf-8 -*-
"""
common.py - fungsi bersama untuk SpendingToolkit.

Format data yang dipakai SEMUA tool (satu kontrak, 7 kolom):

    tanggal    YYYY-MM-DD
    waktu      HH:MM  (boleh kosong)
    jenis      jenis transaksi dari bank: "QRIS", "Transfer", "Top Up E-Wallet", ...
    keterangan nama vendor / deskripsi
    nominal    angka positif, tanpa titik/koma
    ref        nomor referensi (boleh kosong)
    sumber     dari mana datanya: nama bank, "Shopee", dll

Semua tool baca/tulis format ini. Kalau bank kamu beda, cukup ubah 1_ekstrak.py.
"""

import csv
import datetime as dt
import io
import os
import re

KOLOM = ["tanggal", "waktu", "jenis", "keterangan", "nominal", "ref", "sumber"]

# ---------------------------------------------------------------- angka
def parse_uang(nilai):
    """'Rp 1.234.567,89' -> 1234567. '1,234,567.89' -> 1234567. '202500' -> 202500."""
    if nilai is None:
        return 0
    if isinstance(nilai, (int, float)):
        return int(round(nilai))
    t = str(nilai).strip()
    if not t:
        return 0
    negatif = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = re.sub(r"[^\d,.]", "", t)
    if not t:
        return 0

    # OCR sering membuang koma: "252.500100" = "252.500,00"
    m = re.fullmatch(r"(\d{1,3})\.(\d{3})\d{2,3}", t)
    if m:
        v = int(m.group(1) + m.group(2))
        return -v if negatif else v

    ada_koma = "," in t
    ada_titik = "." in t
    if ada_koma and ada_titik:
        # pemisah terakhir = desimal
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif ada_titik:
        bagian = t.split(".")
        # 1.234.567 -> ribuan ; 1234.56 -> desimal
        if len(bagian) > 2 or (len(bagian) == 2 and len(bagian[1]) == 3):
            t = t.replace(".", "")
        else:
            pass
    elif ada_koma:
        bagian = t.split(",")
        if len(bagian) > 2 or (len(bagian) == 2 and len(bagian[1]) == 3):
            t = t.replace(",", "")
        else:
            t = t.replace(",", ".")

    try:
        v = float(t)
    except ValueError:
        return 0
    v = int(round(v))
    return -v if negatif else v


# ---------------------------------------------------------------- tanggal
FORMAT_TANGGAL = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d",
    "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y", "%b %d, %Y",
    "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M",
]

_AMBIGU = {"n": 0}


def norm_tanggal(teks, tahun_default=None, gaya="dmy"):
    """Kembalikan 'YYYY-MM-DD' atau None. gaya='dmy' (Indonesia) atau 'mdy' (US)."""
    if not teks:
        return None
    t = str(teks).strip()
    t = re.sub(r"\s+", " ", t)

    for fmt in FORMAT_TANGGAL:
        try:
            d = dt.datetime.strptime(t, fmt)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # cari pola di dalam teks yang lebih panjang
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", t)
    if m:
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if c < 100:
            c += 2000
        if a > 12 and b <= 12:
            hari, bulan = a, b
        elif b > 12 and a <= 12:
            hari, bulan = b, a
        elif gaya == "mdy":
            bulan, hari = a, b
        else:
            hari, bulan = a, b
            _AMBIGU["n"] += 1
        try:
            return dt.date(c, bulan, hari).isoformat()
        except ValueError:
            return None

    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", t)
    if m:
        bulan_nama = m.group(2).lower()[:3]
        peta = {"jan": 1, "feb": 2, "peb": 2, "mar": 3, "mrt": 3, "apr": 4,
                "mei": 5, "may": 5, "jun": 6, "jul": 7,
                "agu": 8, "agt": 8, "ags": 8, "aug": 8,
                "sep": 9, "okt": 10, "oct": 10, "nov": 11, "nop": 11,
                "des": 12, "dec": 12}
        b = peta.get(bulan_nama)
        if b:
            try:
                return dt.date(int(m.group(3)), b, int(m.group(1))).isoformat()
            except ValueError:
                return None
    return None


def norm_waktu(teks):
    """Ambil jam HH:MM. Titik hanya diterima kalau berdiri sendiri (11.01),
    supaya '202.500' tidak salah dibaca jadi jam 02:50."""
    if not teks:
        return ""
    s = str(teks)
    m = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", s)
    if not m:
        m = re.search(r"(?<!\S)(\d{1,2})\.(\d{2})(?!\S)", s)
    if not m:
        return ""
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return ""
    return "%02d:%02d" % (h, mi)


# ---------------------------------------------------------------- CSV
def tulis_csv(path, baris, kolom=None):
    kolom = kolom or KOLOM
    with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=kolom, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for b in baris:
            w.writerow(b)
    return path


def baca_csv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        contoh = fh.read(4096)
        fh.seek(0)
        delim = ";" if contoh.count(";") >= contoh.count(",") else ","
        return [dict(r) for r in csv.DictReader(fh, delimiter=delim)]


def rapikan(baris):
    """Paksa satu baris sesuai kontrak: tanggal ISO, nominal int, kolom lengkap."""
    out = {}
    out["tanggal"] = norm_tanggal(baris.get("tanggal") or baris.get("date") or "")
    out["waktu"] = norm_waktu(baris.get("waktu") or baris.get("time") or "")
    out["jenis"] = (baris.get("jenis") or baris.get("type") or "").strip()
    out["keterangan"] = (baris.get("keterangan") or baris.get("description")
                         or baris.get("vendor") or "").strip()
    out["nominal"] = parse_uang(baris.get("nominal") or baris.get("amount") or 0)
    out["ref"] = (baris.get("ref") or "").strip()
    out["sumber"] = (baris.get("sumber") or baris.get("source") or "").strip()
    return out


# ---------------------------------------------------------------- util
_PETA_OCR = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1",
                           "S": "5", "B": "8", "|": "1"})


def perbaiki_angka_ocr(teks):
    """'300.OOO,OO' -> '300.000,00'. Hanya token yang mirip angka (>=2 digit)."""
    def ganti(m):
        t = m.group(0)
        if len(t) < 3:
            return t
        if not any(c.isdigit() for c in t) and not any(c in ".," for c in t):
            return t
        return t.translate(_PETA_OCR)
    return re.sub(r"[0-9OolISB|][0-9OolISB.,|]*", ganti, str(teks))


def rupiah(n):
    return "Rp " + format(int(round(n)), ",").replace(",", ".")


def info(pesan):
    print("  " + pesan)


def judul(pesan):
    print("\n" + pesan)
    print("-" * len(pesan))


def cari_python():
    return os.path.abspath(__import__("sys").executable)
