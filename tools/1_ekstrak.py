# -*- coding: utf-8 -*-
"""
1_ekstrak.py - ambil transaksi dari PDF e-statement atau gambar/screenshot.

    python 1_ekstrak.py statement.pdf
    python 1_ekstrak.py folder_gambar\
    python 1_ekstrak.py statement.pdf --dump        (cuma keluarkan teksnya)
    python 1_ekstrak.py folder\ --out transaksi.csv

Cara kerja:
  PDF  -> ambil lapisan teks. Kalau halaman itu hasil scan (teks kosong),
          halaman di-render 300 DPI lalu di-OCR pakai mesin Windows.
  IMG  -> langsung OCR pakai mesin Windows (offline, tidak upload).

Kalau layout bank kamu tidak dikenali, pakai --dump lalu tempel teksnya ke
AI dengan prompt di tools/ai_prompt.txt.
"""

import argparse
import asyncio
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (KOLOM, judul, info, norm_tanggal, norm_waktu, parse_uang,
                    perbaiki_angka_ocr, rapikan, rupiah, tulis_csv)

EKSTENSI_GAMBAR = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
# "id" butuh paket bahasa Indonesia di Windows. Kalau tidak ada, otomatis pakai "en".
BAHASA_OCR = None          # None = coba id lalu en
_BAHASA_TERPAKAI = None

# baris yang bukan transaksi
ABAIKAN = (
    "saldo awal", "saldo akhir", "total mutasi", "total debit", "total kredit",
    "halaman", "page ", "periode", "no. rekening", "nomor rekening", "no rek",
    "keterangan", "tanggal transaksi", "uraian", "mutasi rekening", "laporan",
    "dicetak", "cetak pada", "call center", "www.", "http", "customer service",
    "rekening koran", "statement of account", "lanjutan", "bersambung",
)

POLA_TGL = re.compile(
    r"^\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})"
)
POLA_UANG = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?(?![\d])"
                       r"|(?<![\d.,])\d{4,}(?:[.,]\d{2})?(?![\d])")


# --------------------------------------------------------------- OCR
def ocr_gambar(pil_image):
    """OCR -> teks, baris disusun ulang dari posisi kata (bukan urutan mentah)."""
    global _BAHASA_TERPAKAI
    from winocr import recognize_pil

    kandidat = [_BAHASA_TERPAKAI] if _BAHASA_TERPAKAI else (
        [BAHASA_OCR] if BAHASA_OCR else ["id", "en"])

    hasil, error_terakhir = None, None
    for bahasa in kandidat:
        try:
            async def _jalan(b=bahasa):
                return await recognize_pil(pil_image, b)
            hasil = asyncio.run(_jalan())
            _BAHASA_TERPAKAI = bahasa
            break
        except Exception as e:                    # paket bahasa tidak ada
            error_terakhir = e
    if hasil is None:
        raise RuntimeError("OCR gagal: %s" % error_terakhir)

    kata = []
    for baris in hasil.lines:
        for w in baris.words:
            t = (w.text or "").strip()
            if not t:
                continue
            b = w.bounding_rect
            kata.append((b.y + b.height / 2.0, b.x, t, b.height))
    if not kata:
        return ""

    tinggi = sorted(k[3] for k in kata)[len(kata) // 2] or 10
    toleransi = max(6.0, tinggi * 0.6)
    kata.sort(key=lambda k: (k[0], k[1]))

    baris_hasil, sekarang, y_acuan = [], [], None
    for y, x, t, _ in kata:
        if y_acuan is None or abs(y - y_acuan) <= toleransi:
            sekarang.append((x, t))
            y_acuan = y if y_acuan is None else (y_acuan + y) / 2.0
        else:
            sekarang.sort()
            baris_hasil.append(" ".join(t for _, t in sekarang))
            sekarang, y_acuan = [(x, t)], y
    if sekarang:
        sekarang.sort()
        baris_hasil.append(" ".join(t for _, t in sekarang))
    return "\n".join(baris_hasil)


def teks_dari_pdf(path, dpi=300):
    import pymupdf
    from PIL import Image

    doc = pymupdf.open(path)
    potongan = []
    for nomor, page in enumerate(doc, 1):
        teks = page.get_text("text") or ""
        if len(teks.strip()) < 80:                    # halaman scan
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            teks = ocr_gambar(img)
            info("halaman %d: hasil scan, di-OCR (%d karakter)" % (nomor, len(teks)))
        else:
            info("halaman %d: ada lapisan teks (%d karakter)" % (nomor, len(teks)))
        potongan.append(teks)
    return "\n".join(potongan)


def ada_nominal(teks):
    """Apakah teks ini punya angka uang yang bisa dibaca?"""
    bersih = perbaiki_angka_ocr(teks)
    return bool(re.search(r"(?:IDR|Rp)\.?\s*[0-9][0-9.,]{2,}", bersih, re.I))


def teks_dari_gambar(path):
    from PIL import Image
    img = Image.open(path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    teks = ocr_gambar(img)
    if ada_nominal(teks):
        return teks

    # nominal tidak terbaca -> coba ulang 2x lebih besar (huruf besar lebih jelas)
    info("nominal tidak terbaca, coba ulang dengan zoom 2x")
    besar = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    teks2 = ocr_gambar(besar)
    if ada_nominal(teks2):
        return teks2
    return teks


# --------------------------------------------------------------- parser
def parse_teks(teks, sumber, pola="auto"):
    """Teks bebas -> daftar transaksi. Heuristik: tanggal di awal baris + angka."""
    hasil = []
    tanggal_aktif = None
    dilewati = 0

    for mentah in teks.splitlines():
        baris = perbaiki_angka_ocr(mentah.strip())
        if len(baris) < 5:
            continue
        rendah = baris.lower()
        if any(k in rendah for k in ABAIKAN):
            dilewati += 1
            continue

        m = POLA_TGL.match(baris)
        if m:
            tgl = norm_tanggal(m.group(1))
            sisa = baris[m.end():]
        else:
            tgl = tanggal_aktif
            sisa = baris

        if not tgl:
            continue

        angka = [x.group(0) for x in POLA_UANG.finditer(sisa)]
        angka = [a for a in angka if parse_uang(a) > 0]
        # buang nomor telepon / nomor referensi (digit panjang tanpa pemisah)
        angka = [a for a in angka
                 if ("." in a or "," in a or len(re.sub(r"\D", "", a)) <= 9)]
        if not angka:
            # baris tanpa nominal: mungkin judul grup, simpan tanggalnya saja
            if m:
                tanggal_aktif = tgl
            continue

        if pola == "first" or (pola == "auto" and len(angka) >= 2):
            nominal = parse_uang(angka[0])
        else:
            nominal = parse_uang(angka[-1])

        if nominal <= 0 or nominal > 1_000_000_000:
            continue

        ket = sisa
        for a in angka:
            ket = ket.replace(a, " ")
        ket = re.sub(r"\b(Rp|IDR|DB|CR|DEBIT|KREDIT)\b", " ", ket, flags=re.I)
        ket = re.sub(r"[\s|]+", " ", ket).strip(" -.,|")
        if len(ket) < 2:
            ket = baris[:60]

        if nominal <= 0:
            continue

        # deteksi uang masuk (kalau tidak, pemasukan ikut dihitung sebagai belanja)
        jenis = ""
        if re.search(r"\b(masuk|kredit|cr|gaji|terima|bunga|refund|setoran)\b", ket, re.I):
            jenis = "MASUK"

        hasil.append({
            "tanggal": tgl,
            "waktu": norm_waktu(baris),
            "jenis": jenis,
            "keterangan": ket[:120],
            "nominal": nominal,
            "ref": "",
            "sumber": sumber,
        })
        tanggal_aktif = tgl

    info("baris dilewati (judul/footer): %d" % dilewati)
    return hasil


LABEL_JENIS = ("merchant", "penerima", "nama penerima", "deskripsi", "berita",
               "tujuan", "jenis transaksi", "tipe transaksi", "keterangan",
               "vendor", "toko")


def _layak(nilai):
    """Tolak nilai yang isinya kebanyakan angka (nomor rekening, PAN, no. HP)."""
    if len(nilai) < 3:
        return False
    digit = sum(c.isdigit() for c in nilai)
    return digit <= len(nilai) * 0.4


def deteksi_mode(teks):
    """Struk/bukti transfer atau rekening koran?"""
    rendah = teks.lower()
    if "transaksi berhasil" in rendah or "bukti transaksi" in rendah:
        return "struk"
    if "nominal" in rendah and ("idr" in rendah or "rp" in rendah):
        return "struk"
    return "statement"


def parse_struk(teks, sumber):
    """Satu struk / bukti transfer -> satu transaksi. Berbasis label, bukan kolom."""
    baris = [perbaiki_angka_ocr(b.strip()) for b in teks.splitlines() if b.strip()]
    if not baris:
        return []

    tgl, waktu = None, ""
    for b in baris:
        t = norm_tanggal(b)
        if t:
            tgl, waktu = t, norm_waktu(b)
            break
    if not tgl:
        return []

    total, nominal, biaya = 0, 0, 0
    for b in baris:
        if not re.search(r"\b(IDR|Rp)\b", b, re.I):
            continue
        v = parse_uang(b)
        if v <= 0:
            continue
        rendah = b.lower()
        if re.search(r"admin|biaya", rendah):
            biaya = v
        elif rendah.startswith(("nominal", "jumlah")):
            nominal = v
        elif total == 0:
            total = v

    # kalau baris total rusak / kebaca 10x lipat, pakai nominal + biaya
    if nominal:
        wajar = nominal + biaya
        if total <= 0 or abs(total - wajar) > max(1000, wajar * 0.05):
            total = wajar
    # pengaman: tanpa baris Nominal sebagai pembanding, angka >= 10 juta
    # di struk pribadi hampir pasti salah baca (contoh: 50.000 -> 500000100)
    if not nominal and total >= 10_000_000:
        return []
    if total <= 0:
        return []

    ket = ""
    for lab in LABEL_JENIS:
        for b in baris:
            if b.lower().startswith(lab):
                nilai = b[len(lab):].strip(" :-|")
                if _layak(nilai):
                    ket = nilai
                    break
        if ket:
            break
    if not ket:
        for i, b in enumerate(baris):
            if norm_tanggal(b) and i + 1 < len(baris):
                calon = baris[i + 1]
                if _layak(calon):
                    ket = calon
                break

    return [{
        "tanggal": tgl, "waktu": waktu, "jenis": "", "keterangan": ket[:120],
        "nominal": total, "ref": "", "sumber": sumber,
    }]


def buang_ganda(baris):
    """Hapus transaksi kembar (screenshot tumpang tindih)."""
    terlihat, unik = set(), []
    for b in baris:
        kunci = (b["tanggal"], b["nominal"], b["keterangan"][:40].lower())
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        unik.append(b)
    return unik


# --------------------------------------------------------------- main
def kumpulkan_file(target):
    if os.path.isdir(target):
        daftar = []
        for nama in sorted(os.listdir(target)):
            p = os.path.join(target, nama)
            if os.path.isfile(p) and (nama.lower().endswith(".pdf")
                                      or nama.lower().endswith(EKSTENSI_GAMBAR)):
                daftar.append(p)
        return daftar
    return [target]


def main():
    ap = argparse.ArgumentParser(description="Ambil transaksi dari PDF / gambar")
    ap.add_argument("target", help="file PDF, gambar, atau folder")
    ap.add_argument("--out", default="", help="nama CSV hasil (default: transaksi.csv)")
    ap.add_argument("--sumber", default="", help="label sumber, misal DG / BCA / Jago")
    ap.add_argument("--dump", action="store_true", help="cuma simpan teksnya (untuk AI)")
    ap.add_argument("--pola", default="auto", choices=["auto", "first", "last"],
                    help="angka mana yang diambil sebagai nominal (mode statement)")
    ap.add_argument("--mode", default="auto", choices=["auto", "struk", "statement"],
                    help="auto = tebak sendiri; struk = 1 bukti transfer; statement = rekening koran")
    ap.add_argument("--gaya", default="dmy", choices=["dmy", "mdy"],
                    help="urutan tanggal: dmy (Indonesia) atau mdy (US)")
    args = ap.parse_args()

    if not os.path.exists(args.target):
        print("Tidak ada: " + args.target)
        return 1

    file_list = kumpulkan_file(args.target)
    if not file_list:
        print("Tidak ada PDF/gambar di folder itu.")
        return 1

    semua, semua_teks = [], []
    gagal = []
    for path in file_list:
        judul(os.path.basename(path))
        try:
            if path.lower().endswith(".pdf"):
                teks = teks_dari_pdf(path)
            else:
                teks = teks_dari_gambar(path)
        except Exception as e:
            print("  GAGAL: %s (%s)" % (e, type(e).__name__))
            continue

        semua_teks.append("### " + os.path.basename(path) + "\n" + teks)
        sumber = args.sumber or os.path.splitext(os.path.basename(path))[0]

        if args.dump:
            info("%d karakter teks" % len(teks))
            continue

        baris = []
        mode = args.mode if args.mode != "auto" else deteksi_mode(teks)
        if mode == "struk":
            baris = parse_struk(teks, sumber)
            info("dibaca sebagai struk")
        else:
            baris = parse_teks(teks, sumber, args.pola)
            info("dibaca sebagai rekening koran")
        info("%d transaksi terbaca" % len(baris))
        if not baris:
            gagal.append(os.path.basename(path))
        semua.extend(baris)

    dasar = os.path.dirname(os.path.abspath(file_list[0]))
    if args.dump:
        keluar = os.path.join(dasar, "teks_mentah.txt")
        with io.open(keluar, "w", encoding="utf-8") as fh:
            fh.write("\n\n".join(semua_teks))
        print("\nTeks disimpan: " + keluar)
        print("Buka file itu, lalu tempel isinya ke AI pakai tools/ai_prompt.txt")
        return 0

    if not semua:
        print("\nTidak ada transaksi yang terbaca.")
        print("Coba: python 1_ekstrak.py \"%s\" --dump" % args.target)
        print("lalu tempel teksnya ke AI dengan prompt di tools/ai_prompt.txt")
        return 1

    semua = [rapikan(b) for b in semua]
    sebelum = len(semua)
    semua = buang_ganda(semua)
    if len(semua) != sebelum:
        info("%d kembar dibuang" % (sebelum - len(semua)))

    semua.sort(key=lambda b: (b["tanggal"] or "", b["waktu"] or ""))
    keluar = args.out or os.path.join(dasar, "transaksi.csv")
    tulis_csv(keluar, semua)

    total = sum(b["nominal"] for b in semua)
    print("\n%d transaksi, total %s" % (len(semua), rupiah(total)))
    if gagal:
        print("\nPERHATIAN - %d file tidak terbaca:" % len(gagal))
        for nama in gagal[:15]:
            print("  " + nama)
        print("  Isi manual, atau kirim ke AI pakai tools/ai_prompt.txt")
    print("Disimpan: " + keluar)
    print("Langkah berikut: python 2_analisa.py \"%s\"" % keluar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
