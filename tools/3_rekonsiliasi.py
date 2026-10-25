# -*- coding: utf-8 -*-
"""
3_rekonsiliasi.py - cari tahu uang e-wallet (ShopeePay/OVO/GoPay/dll) dipakai buat apa.

Masalah: di rekening cuma kelihatan "Top Up ShopeePay Rp 200.000" tanpa detail.
Solusi: cocokkan dengan daftar belanja (order Shopee) pakai metode FIFO.

    python 3_rekonsiliasi.py transaksi.csv belanja.csv
    python 3_rekonsiliasi.py transaksi.csv belanja.csv --topup "top up"

transaksi.csv : hasil 1_ekstrak.py dari rekening bank
belanja.csv   : daftar order (dari script Shopee, atau CSV buatan sendiri)

Format belanja.csv minimal punya kolom: tanggal, keterangan, nominal
(boleh juga pakai nama kolom Inggris: date, item/description, total/amount)

Hasil: rekonsiliasi.csv + ringkasan di layar.
"""

import argparse
import datetime as dt
import io
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import baca_csv, judul, norm_tanggal, norm_waktu, parse_uang, rapikan, rupiah

MAMAK = ["chondromax", "gamis"]


def ambil(baris, *nama):
    for n in nama:
        if n in baris and baris[n] not in (None, ""):
            return baris[n]
    for k, v in baris.items():
        if k and k.strip().lower() in nama and v not in (None, ""):
            return v
    return ""


def ke_waktu(tgl, jam=""):
    try:
        d = dt.datetime.strptime(tgl, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    j = norm_waktu(jam)
    if j:
        h, m = j.split(":")
        return d.replace(hour=int(h), minute=int(m))
    return d


def main():
    ap = argparse.ArgumentParser(description="Rekonsiliasi saldo e-wallet (FIFO)")
    ap.add_argument("transaksi", help="CSV transaksi rekening bank")
    ap.add_argument("belanja", help="CSV daftar order/belanja")
    ap.add_argument("--topup", default="top up", help="kata kunci baris top up")
    ap.add_argument("--out", default="", help="file CSV hasil")
    args = ap.parse_args()

    for p in (args.transaksi, args.belanja):
        if not os.path.exists(p):
            print("Tidak ada: " + p)
            return 1

    # ---- top up dari rekening
    topup = []
    for r in baca_csv(args.transaksi):
        b = rapikan(r)
        teks = (b["keterangan"] + " " + b["jenis"]).lower()
        if args.topup.lower() not in teks:
            continue
        when = ke_waktu(b["tanggal"], b["waktu"])
        if not when:
            continue
        topup.append({"dt": when, "d": b["tanggal"], "t": b["waktu"],
                      "nominal": b["nominal"], "sisa": b["nominal"], "pakai": []})
    topup.sort(key=lambda x: x["dt"])

    # ---- belanja
    belanja = []
    for r in baca_csv(args.belanja):
        tgl = norm_tanggal(ambil(r, "tanggal", "date", "order date"))
        nom = parse_uang(ambil(r, "nominal", "total", "total pesanan", "amount", "harga"))
        if not tgl or nom <= 0:
            continue
        ket = str(ambil(r, "keterangan", "item", "description", "barang", "nama"))
        when = ke_waktu(tgl, ambil(r, "waktu", "time", "jam"))
        belanja.append({"dt": when, "d": tgl, "ket": ket.strip(),
                        "total": nom, "dibayar": 0, "dari": []})
    belanja.sort(key=lambda x: x["dt"])

    if not topup:
        print("Tidak ada baris top up yang cocok dengan kata '%s'." % args.topup)
        print("Coba lihat isi kolom keterangan di CSV kamu, lalu pakai --topup \"...\"")
        return 1

    # ---- FIFO
    antre = []
    kejadian = [("in", t["dt"], t) for t in topup] + [("out", b["dt"], b) for b in belanja]
    kejadian.sort(key=lambda e: (e[1], 0 if e[0] == "in" else 1))

    for jenis, _, obj in kejadian:
        if jenis == "in":
            antre.append(obj)
            continue
        butuh = obj["total"]
        while butuh > 0 and antre:
            tp = antre[0]
            ambil_n = min(tp["sisa"], butuh)
            tp["sisa"] -= ambil_n
            butuh -= ambil_n
            obj["dibayar"] += ambil_n
            obj["dari"].append(tp)
            tp["pakai"].append((obj, ambil_n))
            if tp["sisa"] <= 0:
                antre.pop(0)

    total_topup = sum(t["nominal"] for t in topup)
    terpakai = sum(b["dibayar"] for b in belanja)
    sisa = sum(t["sisa"] for t in topup)

    judul("RINGKASAN")
    print("  Top up masuk      : %s  (%d transaksi)" % (rupiah(total_topup), len(topup)))
    print("  Terpakai belanja  : %s" % rupiah(terpakai))
    print("  Sisa di saldo     : %s" % rupiah(sisa))
    print("  Belanja total     : %s  (%d order)" % (
        rupiah(sum(b["total"] for b in belanja)), len(belanja)))
    print("  Bayar cara lain   : %s" % rupiah(
        sum(b["total"] - b["dibayar"] for b in belanja)))

    judul("PER KATEGORI (yang dibayar dari saldo)")
    per = defaultdict(int)
    for b in belanja:
        if b["dibayar"]:
            per["MAMAK" if any(k in b["ket"].lower() for k in MAMAK) else "biasa"] += b["dibayar"]
    for k, v in sorted(per.items(), key=lambda x: -x[1]):
        print("  %-10s %s" % (k, rupiah(v)))

    judul("TOP UP MANA MEMBAYAR APA")
    for t in topup:
        print("  %s %s  %s" % (t["d"], t["t"], rupiah(t["nominal"])))
        if not t["pakai"]:
            print("      (tidak terpakai)")
        for obj, n in t["pakai"]:
            tanda = "  <== MAMAK" if any(k in obj["ket"].lower() for k in MAMAK) else ""
            print("      - %s  %-9s %s%s" % (obj["d"], rupiah(n), obj["ket"][:48], tanda))

    keluar = args.out or os.path.join(os.path.dirname(os.path.abspath(args.belanja)),
                                      "rekonsiliasi.csv")
    with io.open(keluar, "w", encoding="utf-8-sig", newline="") as fh:
        import csv as _csv
        w = _csv.writer(fh, delimiter=";")
        w.writerow(["tanggal", "keterangan", "total", "dibayar_dari_saldo",
                    "bayar_cara_lain", "mamak"])
        for b in belanja:
            w.writerow([b["d"], b["ket"], b["total"], b["dibayar"],
                        b["total"] - b["dibayar"],
                        "MAMAK" if any(k in b["ket"].lower() for k in MAMAK) else ""])
    print("\n  CSV: " + keluar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
