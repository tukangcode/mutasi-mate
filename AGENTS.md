# AGENTS.md — instruksi untuk AI agent

> Ringkasan Indonesia: file ini dipakai kalau user minta **kamu** yang
> menjalankan toolkit ini, bukan dia manual. Ikuti urutan di bawah, jangan
> mengarang angka, dan selalu verifikasi sebelum melapor.

You are operating a local, offline expense-extraction toolkit. The user hands
you bank statements, receipts, or screenshots; you produce a CSV, a report,
and optionally an e-wallet reconciliation.

Everything runs on the user's machine. **Nothing is uploaded.**

---

## Hard rules

1. **Never invent a transaction.** If OCR or parsing is ambiguous, leave the
   row out and tell the user which file failed. A missing row is recoverable;
   a wrong amount is not.
2. **Never edit the user's source files.** Read-only on their PDFs, images,
   and any CSV they did not ask you to change. Write only into the working
   folder you were given.
3. **Never upload anything** to a remote service. If you must use an LLM to
   structure text, the user pastes it themselves — see `tools/ai_prompt.txt`.
4. **Verify before reporting.** Read the produced CSV and cross-check the
   totals yourself. Do not report "done" from a tool exit code alone.
5. **Ask before guessing categories.** If many rows land in `Lain-lain`,
   show them to the user; do not silently invent rules.

---

## Environment

Windows. Run Python as `py -3` (fall back to `python` if that fails).

Dependencies (already installed on the reference machine):
`pymupdf pillow winocr openpyxl`.

If an import fails, tell the user to run:
`py -3 -m pip install pymupdf pillow winocr openpyxl`

All paths below are relative to this file's directory.

---

## The data contract

Every tool reads and writes the same 7-column CSV, `;`-separated, UTF-8 BOM:

```
tanggal;waktu;jenis;keterangan;nominal;ref;sumber
2026-05-23;11:01;Top Up E-Wallet;Top Up ShopeePay;202500;SHP83339705N;DG
2026-05-24;12:37;QRIS;ARKYS SMASH CHICKEN;19000;MB1779597443DT5;DG
```

- `tanggal` — `YYYY-MM-DD`
- `waktu` — `HH:MM`, may be empty
- `jenis` — transaction type as written; `MASUK` for incoming money
- `keterangan` — merchant / recipient / description
- `nominal` — digits only, positive, no separators
- `ref` — reference number, may be empty
- `sumber` — bank or app name

If the user supplies their own CSV, confirm it matches this contract before
running step 2. Map their column names rather than asking them to reformat.

---

## Step 1 — extract

Choose the input shape:

| User has | Command |
|---|---|
| one PDF statement | `py -3 tools/1_ekstrak.py "statement.pdf" --sumber DG` |
| folder of screenshots | `py -3 tools/1_ekstrak.py "folder/" --sumber DG` |
| one receipt image | `py -3 tools/1_ekstrak.py "struk.jpg" --sumber DG` |

Useful flags:

- `--out nama.csv` — output path (default `transaksi.csv` next to the input)
- `--sumber LABEL` — tag every row with the bank/app name
- `--mode struk|statement` — force a parser; `auto` decides by content
- `--pola first|last|auto` — which number on a line is the amount
  (`statement` mode only)
- `--gaya mdy` — if dates are US-ordered (mm/dd); default is `dmy`
- `--dump` — write raw OCR text only, no CSV

**If the layout is unrecognised** (0 transactions, or nonsense amounts), do
not retry blindly. Run `--dump`, then hand the user `tools/ai_prompt.txt` so
they paste the text into an LLM and return a CSV. That path is more reliable
than tuning flags at random.

---

## Step 2 — report

```
py -3 tools/2_analisa.py transaksi.csv
```

Produces `laporan.html` (open in a browser) and `tracker.xlsx` in the CSV's
folder. Categorisation comes from `config/kategori.txt`.

If the output prints **`BELUM ADA KATEGORI`**, that block is your work queue:
- Look at the listed descriptions.
- Propose new rules to the user, or add obvious ones to `config/kategori.txt`
  in the form `kata kunci|Kategori|jenis` (`belanja` / `pindah` / `masuk`).
- Re-run step 2.

Rules are first-match, top to bottom. Put specific keywords above generic ones.

---

## Step 3 — e-wallet reconciliation (optional)

Only when the user asks what a top-up was spent on.

```
py -3 tools/3_rekonsiliasi.py transaksi.csv order_shopee.csv
```

`order_shopee.csv` needs at least date, description, amount — the Shopee
userscript export already satisfies this. Method is FIFO: each purchase
consumes the oldest top-up balance. Works best when top-ups happen minutes
before the purchase (common); say so if the gap is large, because then the
attribution is weaker.

---

## Reading the output

Step 1 ends with a summary like:

```
81 transaksi, total Rp 9.635.600

PERHATIAN - 2 file tidak terbaca:
  Screenshot_....jpg
```

That list is **not optional detail**. Report those filenames to the user and
ask for the missing date and amount, or route them through `--dump`.

Step 2 prints `Belanja` / `Pindah dana` / `Uang masuk`. `Pindah dana` is
money movement, not spending — do not add it to the expense total.

---

## Failure modes and what to do

| Symptom | Cause | Action |
|---|---|---|
| `0 transaksi terbaca` on a receipt | amount line lost by OCR | `--dump`, inspect, or AI path |
| every file says 0 | wrong `--mode` | try `--mode struk` or `--mode statement` |
| amounts look 10x too big | OCR dropped the decimal comma | already guarded; if it recurs, report it |
| `Failed to read findings JSON` | unrelated skill, not this toolkit | ignore |
| `ModuleNotFoundError: winocr` | deps missing | give the pip command above |
| duplicate rows in output | overlapping screenshots | dedupe is automatic; if still present, dedupe on (date, amount, description) |

---

## Verification checklist — run this before you report

1. Row count in the CSV equals the number of transactions the tool claimed.
2. `sum(nominal)` for `belanja` + `pindah` + `masuk` equals the sum of all
   `nominal` in the file.
3. Date range is what the user expects. If they asked for one month, filter
   and say how many rows were dropped as out-of-range.
4. Any `MASUK` rows are excluded from spending totals.
5. Open `laporan.html` once (or parse it) to confirm it is not blank.
6. State the failed-file count explicitly, even when it is zero.

---

## Report template (Bahasa Indonesia)

```
Selesai.

[Sebutkan folder output dan file utamanya.]

| | |
|---|---|
| Periode | ... |
| Transaksi | N |
| Total keluar | Rp ... |
| Belanja | Rp ... |
| Pindah dana | Rp ... |
| Uang masuk | Rp ... |

Kategori terbesar: ... (Rp ...)

Perlu kamu cek:
- N file gagal dibaca: [nama file]
- N transaksi belum ada kategori: [deskripsi]
```

Keep it short. State limits plainly; never claim a month is complete when
files failed.

---

## Files

| Path | Role |
|---|---|
| `BACA DULU.txt` | human-facing manual |
| `AUDIT.md` | security review of this toolkit |
| `config/kategori.txt` | categorisation rules, user-editable |
| `tools/1_ekstrak.py` | PDF / image → `transaksi.csv` |
| `tools/2_analisa.py` | CSV → `laporan.html` + `tracker.xlsx` |
| `tools/3_rekonsiliasi.py` | FIFO e-wallet attribution |
| `tools/ai_prompt.txt` | prompt for unknown layouts |
| `shopee/` | userscripts + install guide + `CARA PAKAI.txt` (harvest steps, limits) |
| `contoh/` | sample PDF, CSV, and generated report |

---

## Known limits — say these out loud when relevant

- The parser is heuristic, not an LLM. It handles "date at line start" and
  "label: value" receipts well; unusual table layouts need the AI path.
- Reference test: 97 real receipts → 81 of 83 transactions (97.6%), zero
  wrong amounts, 2 files flagged unreadable. Expect similar, not perfect.
- Shopee userscript totals are item price × quantity, excluding shipping.
- OCR uses the Windows built-in engine, offline. Indonesian language pack is
  optional; it falls back to English automatically.
