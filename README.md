<p align="center">
  <img src="assets/hero.svg" alt="Mutasi Mate — rekening koran dan screenshot jadi laporan pengeluaran" width="100%">
</p>

<p align="center">
  <a href="https://nbgate.com/signup?ref=REF-DFGFKG">
    <img src="assets/nbgate.png" alt="NBGate" width="208">
  </a>
</p>

<p align="center">
  <sub><b>POWERED BY NBGATE</b></sub><br>
  <sub>Butuh token AI? Dapatkan sekarang di NBGate &mdash; harga terjangkau dan masuk akal.<br>
  Dengan mengklik link di atas, kamu ikut mendukung pengembangan tool ini.</sub>
</p>

<p align="center">
  <sub>Tool ini sendiri tetap berjalan offline &mdash; tidak butuh token AI untuk dipakai.</sub>
</p>

---

<h3 align="center">Rekening koran, screenshot struk, dan pesanan Shopee jadi laporan pengeluaran.</h3>

<p align="center">
  <em>Offline. Tanpa upload. Tanpa API key. Tanpa macro.</em>
</p>

<p align="center">
  <a href="ENGLISH.md">🇬🇧 Read this in English</a>
</p>

---

Kebanyakan bank di Indonesia cuma kasih satu screenshot "Transaksi Berhasil" per
transaksi — tidak ada e-statement PDF, tidak ada export CSV, tidak ada API. Jadi
riwayat pengeluaran kamu hidup di 97 file JPG dan satu grup chat.

**Mutasi Mate** mengubah kekacauan itu jadi spreadsheet dan dashboard yang bisa
kamu baca. Dia juga menjawab pertanyaan yang semua pengguna e-wallet punya:
*rekening bilang "Top Up ShopeePay Rp 4.310.000" — habis buat apa?*

```
97 screenshot  →  81 transaksi  →  Rp 9,6 juta terlacak  →  0 angka salah
```

---

## Cara kerjanya

<p align="center">
  <img src="assets/pipeline.svg" alt="Alur: ekstrak, kategori, laporan, rekonsiliasi" width="100%">
</p>

| Langkah | Perintah | Hasil |
|---------|----------|-------|
| **1. Ekstrak** | `1_ekstrak.py` | `transaksi.csv` |
| **2. Kategori** | `2_analisa.py` | `laporan.html` + `tracker.xlsx` |
| **3. Rekonsiliasi** *(opsional)* | `3_rekonsiliasi.py` | `rekonsiliasi.csv` |

**Ekstrak** membaca PDF e-statement, folder screenshot, atau satu struk. PDF yang
punya lapisan teks dibaca langsung; halaman hasil scan di-render 300 DPI lalu
di-OCR pakai mesin OCR bawaan Windows. Tanpa download model, tanpa panggilan ke
cloud.

**Kategori** mencocokkan teks merchant dengan aturan milikmu sendiri di
`config/kategori.txt` — satu baris satu aturan. Yang tidak cocok masuk
`Lain-lain` dan didaftarkan di akhir, jadi kamu tahu persis apa yang perlu
ditambah.

**Rekonsiliasi** bagian yang menarik. Dia menelusuri top up dan pembelian urut
waktu lalu menerapkan FIFO: tiap pembelian memakai saldo top up paling tua.
Kalau top up terjadi 1–10 menit sebelum order — yang memang kebiasaan orang —
atribusinya jadi hampir pasti, bukan tebakan.

---

## Mulai cepat

**Syarat:** Python 3.9+ dan Windows 10/11 (mesin OCR-nya sudah ada di Windows).

```bash
pip install pymupdf pillow winocr openpyxl
```

```bash
# 1. ekstrak
py -3 tools/1_ekstrak.py "statement.pdf" --sumber BCA
py -3 tools/1_ekstrak.py "folder_screenshot/" --sumber DG

# 2. laporan
py -3 tools/2_analisa.py transaksi.csv

# 3. opsional: top up e-wallet habis buat apa?
py -3 tools/3_rekonsiliasi.py transaksi.csv order_shopee.csv
```

Atau cukup tarik file ke `1 Ekstrak.bat` dan `2 Laporan.bat`.

### Layout bank kamu tidak dikenali?

Jangan berkelahi dengan flag. Keluarkan teksnya, biar LLM yang menyusun:

```bash
py -3 tools/1_ekstrak.py "statement.pdf" --dump
```

Muncul `teks_mentah.txt`. Tempel ke LLM mana saja bersama `tools/ai_prompt.txt` —
prompt-nya sudah menangani jebakan klasik (`05/10/2026` itu 5 Oktober, bukan
10 Mei) dan menyuruh model mengosongkan kolom daripada menebak. Simpan
jawabannya sebagai `transaksi.csv`, lanjut ke langkah 2.

---

## Kontrak data

Semua tool bicara satu format: 7 kolom, pemisah titik koma, UTF-8 BOM
(supaya Excel membukanya tanpa karakter aneh).

```csv
tanggal;waktu;jenis;keterangan;nominal;ref;sumber
2026-05-23;11:01;Top Up E-Wallet;Top Up ShopeePay;202500;SHP83339705N;DG
2026-05-24;12:37;QRIS;ARKYS SMASH CHICKEN;19000;MB1779597443DT5;DG
```

| Kolom | Arti |
|-------|------|
| `tanggal` | `YYYY-MM-DD` |
| `waktu` | `HH:MM`, boleh kosong |
| `jenis` | jenis transaksi; `MASUK` untuk uang masuk |
| `keterangan` | merchant / penerima / deskripsi |
| `nominal` | angka saja, positif, tanpa pemisah |
| `ref` | nomor referensi, boleh kosong |
| `sumber` | nama bank atau aplikasi |

Sudah punya CSV dari bank? Petakan kolomnya saja, tidak perlu format ulang manual.

---

## Yang kamu dapat

`laporan.html` — satu file mandiri (CSS, JS, dan data menyatu di dalamnya). Bisa
dibuka offline, dikirim lewat email, atau ditaruh di HP. Tanpa server, tanpa CDN,
tanpa font yang perlu diunduh.

- total keluar vs belanja nyata vs perpindahan uang
- pengeluaran per kategori, per bulan, per merchant
- 10 transaksi terbesar
- tabel lengkap dengan pencarian

`tracker.xlsx` — sheet `Input` (bisa difilter, header dibekukan) dan sheet
`Ringkasan` dengan total `SUMIF`. Formula biasa, tanpa macro, tanpa peringatan
keamanan.

---

## Bagian Shopee (baca batasannya)

Dua userscript Tampermonkey di `shopee/`:

| Script | Cara kerja | Pakai kalau |
|--------|-----------|-------------|
| `2_shopee_daftar_v3.txt` | menempel hook di XHR halaman, memakai ulang JSON yang halaman itu sudah ambil | butuh banyak order, cepat |
| `1_shopee_popup_v2.2.txt` | memuat tiap order di iframe tersembunyi | butuh detail per order |

**Ini setengah otomatis, dan bisa rusak.** Baca dengan sadar:

1. **Kamu yang mengemudi.** Login, buka *Pesanan Saya*, pilih tab **Selesai**.
2. **Scroll ke paling bawah dulu.** Shopee membuat bar pagination secara malas —
   kalau belum scroll, tombol "Berikutnya" belum ada dan script berhenti di
   halaman satu.
3. **Rusak kalau Shopee ubah layout.** Tanpa peringatan — tiba-tiba hasilnya
   `0 pesanan`. Script membaca struktur halaman, bukan API resmi.
4. **Export segera.** v3 menyimpan hasil di `localStorage`, jadi refresh biasanya
   selamat. v2.2 menyimpan di memori — refresh langsung hilang.
5. **Total belum termasuk ongkir.** `Total Pesanan` = harga barang × jumlah.

Panduan lengkap dan cara menangani kalau rusak:
[`shopee/CARA PAKAI.txt`](shopee/CARA_PAKAI.txt).

> ### ⚠️ Kalau kamu fork untuk Shopee region lain
>
> Script ini disetel untuk **shopee.co.id**. Untuk region lain (SG, MY, PH, TH,
> VN, TW, BR, MX) minimal ini yang harus disesuaikan:
>
> | Bagian | Yang perlu diubah |
> |--------|-------------------|
> | `@match` di metadata | `https://shopee.co.id/*` → domain region kamu |
> | Format uang | `Rp` → mata uang lokal; pemisah ribuan/desimal ikut beda |
> | `microFix()` | sebagian region kirim harga dalam micro-units (×100000) — cek hasilnya |
> | `scrapeCards()` | selector kartu pesanan; nama class tiap region bisa beda |
> | `findNext()` | teks tombol halaman ("Berikutnya" / "Next" / "ถัดไป") |
> | Hook XHR | filter `/api` `/order` `/purchase` — endpoint region bisa berbeda |
> | Tanggal | `dd/mm/yyyy` vs `mm/dd/yyyy` |
>
> Uji dulu dengan **satu halaman** sebelum klik "Auto semua halaman". Kalau
> hasilnya 0, berarti selector region kamu memang beda — itu yang perlu
> diperbaiki lebih dulu.

---

## Keamanan

Tool ini menyimpan catatan keuanganmu, jadi dia diaudit sebelum dirilis:

- **Tanpa panggilan jaringan.** Nol `urllib`, `requests`, `socket` di kode Python.
- **Tanpa rahasia.** Tidak ada API key, token, atau kredensial di seluruh repo.
- **Tanpa telemetri.** OCR jalan di mesin Windows, lokal.
- **Tanpa `eval`, tanpa `subprocess`, tanpa penghapusan file.**
- Userscript tidak melakukan request ke luar; hook XHR hanya membaca respons
  yang halaman itu sudah muat sendiri.

Audit menemukan dan memperbaiki empat masalah, termasuk userscript yang membawa
`@updateURL`/`@downloadURL` menunjuk ke entri Greasyfork pihak ketiga — artinya
Tampermonkey bisa mengganti script yang sudah ditambal tanpa kamu sadari. Kedua
baris itu sudah dihapus.

Laporan lengkap dengan bukti baris kode: [`AUDIT.md`](AUDIT.md).

---

## Batasan yang jujur

- **Parser-nya heuristik, bukan LLM.** Dia bagus untuk pola "tanggal di awal
  baris" dan struk "label: nilai". Layout tabel yang tidak umum perlu jalur AI.
- **Hasil uji acuan:** 97 struk DG asli → **81 dari 83 transaksi (97,6%)**,
  **nol angka salah**, 2 file ditandai tidak terbaca. Dia menolak menebak:
  nominal yang rusak dibuang dan nama filenya dilaporkan, bukan dikarang.
- **OCR khusus Windows.** Ekstraksi teks PDF jalan di mana saja PyMuPDF jalan,
  tapi jalur gambar hasil scan butuh mesin OCR Windows.
- **Berpusat di Rupiah.** Pembacaan angka mengasumsikan format Indonesia
  (`1.234.567,89`); input gaya Amerika perlu `--gaya mdy` untuk tanggal.

Satu baris hilang masih bisa dikejar. Satu angka salah tidak akan ketahuan.
Perdagangan itu disengaja.

---

## Struktur repo

```
tools/1_ekstrak.py        PDF / gambar → transaksi.csv
tools/2_analisa.py        transaksi.csv → laporan.html + tracker.xlsx
tools/3_rekonsiliasi.py   atribusi e-wallet metode FIFO
tools/common.py           parsing bersama (uang, tanggal, CSV)
tools/ai_prompt.txt       prompt untuk layout yang tidak dikenal
config/kategori.txt       aturan kategori — edit di sini
shopee/                   userscript + panduan pasang & pakai
contoh/                   contoh PDF, CSV, dan laporan hasil generate
assets/                   ilustrasi SVG + logo sponsor
AGENTS.md                 instruksi kalau AI yang menjalankan
AUDIT.md                  hasil audit keamanan
BACA DULU.txt             panduan manual
ENGLISH.md                versi bahasa Inggris dari halaman ini
```

---

## Disclaimer

Tool ini dirancang, ditulis, dan diaudit dengan **bantuan AI** — mulai dari
riset format rekening koran tiap bank, penulisan parser, sampai penelusuran bug
OCR yang bikin nominal kebaca 10× lipat. Semua hasilnya diuji pada data nyata
sebelum dirilis.

Tapi tetap: **periksa sendiri sebelum dipakai untuk keputusan keuangan.**

- OCR bisa salah baca karakter (`0` jadi `O`, `1` jadi `l`)
- Parser bisa salah menebak kolom debit/kredit
- Kategori bisa keliru kalau aturanmu belum lengkap

**CSV hasil ekstraksi adalah sumber kebenaran, bukan laporan HTML-nya.** Buka
`transaksi.csv`, bandingkan dengan beberapa struk, baru percaya angkanya.

Disediakan apa adanya di bawah lisensi MIT, tanpa jaminan apa pun.

---

## Kredit

Userscript Shopee diturunkan dari script berlisensi MIT karya **Ryu-Sena**
(IndoTech Community), awalnya terbit di Greasyfork. Banyak diubah di sini:
perbaikan selector, perbaikan timing, fallback iframe, dan cache localStorage
dengan penanda versi. Rinciannya di [NOTICE](NOTICE).

## Lisensi

MIT — lihat [LICENSE](LICENSE).
