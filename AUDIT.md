# Hasil Audit Keamanan

Tanggal: 25 Oktober 2026
Cakupan: seluruh isi folder `SpendingToolkit`
Metode: pemindaian pola rahasia + pembacaan kode sumber (source-first),
bukan sekadar checklist.

## Ringkasan

**Tidak ada API key, token, password, private key, atau kredensial apa pun.**
Tidak ada kode yang mengirim data ke internet.

Empat temuan ditemukan, semuanya sudah diperbaiki:

| # | Temuan | Tingkat | Status |
|---|--------|---------|--------|
| F1 | Userscript v2.2 punya auto-update ke script pihak ketiga | Sedang | Diperbaiki |
| F2 | Nama orang asli di file contoh & config | Rendah | Diperbaiki |
| F3 | Izin `GM_xmlhttpRequest` diberikan tapi tidak dipakai | Rendah | Diperbaiki |
| F4 | `postMessage(..., '*')` di userscript v3 | Info | Dibiarkan (aman) |

---

## F1 — Auto-update ke pihak ketiga (Sedang)

**Lokasi:** `shopee/1_shopee_popup_v2.2.txt` baris 12-13 (sebelum diperbaiki)

```
// @downloadURL https://update.greasyfork.org/scripts/540269/...
// @updateURL   https://update.greasyfork.org/scripts/540269/...
```

**Kenapa berbahaya:** Tampermonkey membaca dua baris itu dan akan
memperbarui script secara otomatis dari Greasyfork. Artinya versi yang sudah
ditambal (fix delay 30 detik, fix selector mati, fix iframe) bisa **ditimpa
diam-diam** oleh versi yang diunggah pemilik akun Greasyfork lain. Kode
pengganti itu berjalan di `shopee.co.id` dengan izin yang sama, tanpa kamu
meninjaunya lebih dulu.

**Perbaikan:** kedua baris dihapus. Versi dinaikkan ke `2.2.1` supaya jelas
ini salinan lokal yang tidak akan berubah sendiri.

---

## F2 — Nama orang asli (Rendah)

**Lokasi yang terdampak:**

- `config/kategori.txt` — dua baris berisi nama pemilik rekening dan nama
  pihak ketiga (penerima tagihan)
- `BACA DULU.txt` — satu contoh aturan memakai nama pemilik rekening
- `tools/ai_prompt.txt` — contoh baris CSV memakai nama pihak ketiga
- `contoh/transaksi.csv`, `contoh/laporan.html`, `contoh/tracker.xlsx`,
  `contoh/statement_contoh.pdf` — memuat nama pihak ketiga

**Kenapa penting:** nama-nama itu diambil dari data rekening asli waktu
membuat contoh. Toolkit ini dimaksudkan untuk dibagikan, jadi nama pemilik
dan dua pihak lain akan ikut terbawa.

**Perbaikan:** semua diganti nama fiktif. PDF contoh dibuat ulang dari nol,
lalu laporan dan Excel-nya digenerate ulang dari PDF baru itu, jadi tidak ada
sisa teks lama.

---

## F3 — Izin berlebih (Rendah)

**Lokasi:** `shopee/1_shopee_popup_v2.2.txt` baris 9-10 (sebelum diperbaiki)

```
// @grant        GM_xmlhttpRequest
// @connect      shopee.co.id
```

**Kenapa penting:** izin itu tidak pernah dipakai di dalam kode (sudah dicek
dengan pencarian `GM_xmlhttpRequest` — hanya muncul di baris metadata). Izin
yang tidak perlu tetap memperbesar dampak kalau script-nya nanti diganti kode
lain. Prinsip least privilege.

**Perbaikan:** kedua baris dihapus. Sisa `@grant GM_addStyle` saja, yang
memang dipakai untuk menempel CSS panel.

---

## F4 — postMessage target wildcard (Info)

**Lokasi:** `shopee/2_shopee_daftar_v3.txt` baris ~603

```js
window.postMessage({ __sft3: true, data: data }, '*');
```

**Penilaian:** pesan dikirim ke window yang sama, dan penerimanya memeriksa
`ev.source !== window`. Tidak ada data yang keluar dari halaman. Risikonya
hanya teoretis (script lain di halaman yang sama bisa ikut mendengar).
Tidak diubah karena mengubahnya jadi `location.origin` tidak menambah
keamanan nyata di sini.

---

## Yang diperiksa dan hasilnya bersih

**Rahasia / kredensial**
- API key OpenAI/Anthropic (`sk-...`), AWS (`AKIA...`), GitHub (`ghp_...`),
  Google (`AIza...`), Slack (`xox...`) — tidak ada
- Private key block, JWT, bearer token — tidak ada
- Assignment `password=` / `token=` / `api_key=` — tidak ada
- Connection string database — tidak ada
- Email, NIK 16 digit, nomor HP Indonesia — tidak ada

Pemindai diuji dengan *positive control* (file berisi `sk-...` palsu) untuk
memastikan deteksinya memang bekerja, bukan diam-diam gagal.

**Perilaku kode Python**
- Tidak ada `urllib`, `requests`, `http.client`, `socket`, `smtplib` — nol
  panggilan jaringan
- Tidak ada `subprocess`, `os.system`, `shell=True`
- Tidak ada `eval`, `exec`, `pickle`, `marshal`
- Tidak ada `shutil.rmtree`, `os.remove`, `os.unlink` — tidak menghapus file
- Tidak ada path pengguna yang di-hardcode

**Userscript Shopee**
- Tidak ada `@require` (tidak memuat library dari luar)
- Tidak ada request ke domain luar; URL yang ada hanya `shopee.co.id`
  dan satu tautan kredit `github.com` (hanya `<a href>`, tidak dieksekusi)
- Hook `XMLHttpRequest` hanya membaca respons yang sudah dimuat halaman
  sendiri, lalu meneruskannya ke window yang sama — tidak mengirim ke mana pun

**OCR**
- Memakai mesin bawaan Windows (`winocr`), berjalan offline
- Tidak ada upload gambar ke layanan mana pun

---

## Catatan pemakaian

1. Tool menulis file hasil di folder yang sama dengan CSV input
   (`laporan.html`, `tracker.xlsx`, `rekonsiliasi.csv`). Itu memang
   perilaku yang diharapkan, tapi jangan jalankan di folder sistem.
2. `tools/__pycache__/` muncul otomatis setiap kali tool dijalankan. Tidak
   berisi rahasia, tapi jangan di-commit (sudah masuk `.gitignore`).
3. Kalau membagikan folder ini, hapus dulu `contoh/` kalau tidak perlu —
   isinya data contoh, bukan data kamu, tapi tetap lebih bersih.
4. Setelah mengubah `config/kategori.txt`, jalankan ulang `2_analisa.py`.
5. Script Shopee hanya membaca halaman yang kamu buka sendiri. Tidak ada
   login otomatis dan tidak ada data yang dikirim keluar.
