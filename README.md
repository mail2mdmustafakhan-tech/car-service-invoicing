# Car Service Invoicing

Invoicing for a car service centre. Runs on one computer in the office, keeps
everything in a single file, and needs no internet connection.

Built to be small enough that one person can understand the whole thing.

---

## How a job flows through

```
car arrives ──► repair contract written ──► customer signs ──► work done
                                                                  │
            invoice paid ◄── invoice issued ◄── contract converted ┘
```

The repair contract is the document the workshop actually runs on. It records
what the owner asked for, what the technician found, which parts went on, and
the owner's signed authorization — all before any money is owed. When the work
is finished, one click turns it into a draft invoice carrying the labour and
parts across, and the two stay linked so any job can be traced from the signed
paper back to what was charged for it.

You can still raise an invoice on its own, for a walk-in who just needs a part.

---

## What it does

- **Repair contracts** — the signed job card: owner and vehicle details, repairs
  requested, technician's remarks, spare parts, a car diagram to mark existing
  damage on, and the bilingual notice and authorization text, all printable on A4
- **Customers and vehicles** — contact details, and the cars each customer owns
  (plate, make, model, year, VIN, colour, odometer)
- **Service and parts catalogue** — your common jobs and parts with prices, so
  invoice lines are picked from a list instead of typed every time
- **Invoices** — raised from a contract or on their own: line items, configurable
  VAT, discounts, draft → issued → void, and an A4 printable copy that saves as
  PDF from any browser
- **Payments** — record full or partial payments, see who still owes you money
- **Arabic and English** — switch at any time; the whole interface mirrors to
  right-to-left, and the printed invoice is labelled in both languages
- **Backup** — one button downloads a copy of the entire database

### What it deliberately does not do, yet

Being honest about the boundaries, so you know what you are starting from:

- No login or user accounts — it assumes one trusted machine in the office
- No ZATCA Phase 2 e-invoicing (XML, cryptographic stamps, QR codes, the
  Fatoora portal integration). If your business is in scope for that, check the
  current ZATCA requirements before relying on this for tax filing
- No inventory levels or stock reordering — the catalogue holds prices, not
  quantities on hand
- No appointments or technician scheduling — a contract records who worked on
  the car, but nothing plans the week
- No accounting ledger, expenses, or payroll

Each of these can be added later. See [Where to take it next](#where-to-take-it-next).

---

## Running it

You have two options. **Docker is the easier one to keep running**; the direct
install is easier to poke at while you are learning.

### Option A — Docker (recommended for the office machine)

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), then:

```bash
git clone https://github.com/YOUR-USERNAME/car-service-invoicing.git
cd car-service-invoicing
docker compose up -d
```

Open **http://localhost:8000**.

That is the whole installation. The database lands in the `data/` folder next
to the compose file. `docker compose down` stops it; `docker compose up -d`
starts it again; nothing is lost in between.

### Option B — Without Docker

You need [Python 3.10 or newer](https://www.python.org/downloads/). On Windows,
tick **"Add Python to PATH"** during installation.

```bash
git clone https://github.com/YOUR-USERNAME/car-service-invoicing.git
cd car-service-invoicing
```

Then:

| Your computer | Command |
| --- | --- |
| Windows | double-click `run.bat` |
| macOS / Linux | `./run.sh` |

The first run builds a small private Python environment and installs four
packages; it takes a minute. Later runs start immediately. Open
**http://localhost:8000**.

### Letting other computers in the office use it

By default the application answers only on the machine it runs on. To let the
manager's PC open it too, serve on all addresses:

```bash
# Docker: already does this — just use http://THAT-PCS-IP:8000
# Without Docker:
CARSERVICE_HOST=0.0.0.0 ./run.sh        # macOS / Linux
set CARSERVICE_HOST=0.0.0.0 && run.bat  # Windows
```

Then from another computer, open `http://192.168.1.42:8000` (substituting the
serving machine's address). Keep this on your own office network — there is no
login, so anyone who can reach the address can edit invoices.

---

## Your first ten minutes

1. **Settings** — business name (English and Arabic), VAT number, commercial
   registration, address, phone. These print at the top of every invoice.
2. **Settings → Tax** — set your VAT rate, or `0` if you are not registered.
   Tick *"Prices I enter already include VAT"* if you quote all-in prices.
3. **Settings → Invoice numbering** — set the prefix and the next number. If
   you are moving from another system or a paper book, continue that series
   here so your numbering never restarts.
4. **Settings → Repair contract** — the notice and authorization text that print
   on the contract come pre-filled. Read them, correct the wording to match your
   own form, and set the contract number series. Write `{business}` in the
   authorization text wherever your business name should appear.
5. **Services & Parts** — add your ten or fifteen most common jobs with prices.
   This is what makes writing up a car fast later.
6. **Customers** → add one → add their vehicle → **Book a car in**.

Want to see it populated before entering anything real?

```bash
python seed_demo.py                 # writes a separate data/demo.db
CARSERVICE_DB=data/demo.db ./run.sh
```

---

## Day to day

**Booking a car in.** New contract → pick the customer (their vehicle fills in
automatically if they only have one) → list what they asked for → note existing
damage → **Print**. The customer signs the paper copy; record that with *Mark as
signed*. As the technician works, add findings in the remarks column and parts
to the spare parts table.

**Finishing a job.** *Mark work complete*, then **Create invoice**. Every repair
with a cost becomes a service line and every part becomes a part line on a new
draft invoice. Check it, then issue it. The contract locks at that point — it is
the signed record of what was agreed, so it stops being editable.

A repair line with a remark but no cost (*"checked the air conditioning — gas
topped up under warranty"*) stays on the contract and is simply not carried onto
the invoice.

**Writing an invoice directly.** New invoice → pick the customer (their vehicle fills in
automatically if they only have one) → pick items from the catalogue → the
totals update as you type. *Issue invoice* makes it final; *Save (Draft)* keeps
it editable.

**Printing.** Open the invoice → **Print**. The print dialogue has a
*"Save as PDF"* destination in every modern browser, which is how you email a
copy. (With Docker, there is also a **Download PDF** button that produces the
file directly.)

**Drafts vs issued vs void.** A draft can be edited or deleted freely and
prints marked "NOT A VALID INVOICE". Once issued, an invoice is a financial
record: it can be voided but never deleted, so its number is always accounted
for and the paper in the customer's hand always matches something in the system.

---

## Backups

**This matters more than anything else in this document.** Everything lives in
one file. If that file is lost, the invoices are gone.

- **Settings → Download backup** makes a safe copy, even while the system is in
  use. Do this weekly and keep copies somewhere other than that computer — a
  USB stick, a network drive, a cloud folder.
- To restore, stop the application, put the backup file at
  `data/carservice.db`, and start it again.
- Copying `data/carservice.db` by hand while the application is running can
  catch it mid-write. Use the backup button, or stop the application first.

Scripted nightly backup, if you want one:

```bash
python -c "from app.db import backup_to; backup_to('backups/carservice-$(date +%F).db')"
```

---

## Where your data lives — and how to query it

One file: `data/carservice.db`. It is a plain [SQLite](https://sqlite.org/)
database, which almost every tool can read directly — no driver, no server, no
export step.

The schema includes three views that present money and quantities as ordinary
decimals, so you can point a BI tool at the file and query it without doing any
arithmetic yourself:

| View | What it gives you |
| --- | --- |
| `v_invoices` | one row per invoice, with totals, amount paid, balance and payment state |
| `v_invoice_lines` | one row per line item, with quantity, unit price and line total |
| `v_payments` | every payment, with its invoice and customer |

```sql
-- Revenue by month
SELECT substr(issue_date, 1, 7) AS month,
       COUNT(*)                 AS invoices,
       ROUND(SUM(total), 2)     AS revenue
FROM v_invoices
WHERE status = 'issued'
GROUP BY month
ORDER BY month DESC;

-- Who owes money
SELECT customer_name, invoice_no, issue_date, balance_due
FROM v_invoices
WHERE payment_state IN ('unpaid', 'partially_paid')
ORDER BY balance_due DESC;

-- Best-selling services and parts
SELECT description, SUM(qty) AS units, ROUND(SUM(line_total), 2) AS revenue
FROM v_invoice_lines
GROUP BY description
ORDER BY revenue DESC
LIMIT 20;
```

**A note on how money is stored.** Every money column ending in `_minor` is an
integer in halalas: `150.75` is stored as `15075`. Quantities ending in
`_milli` are thousandths: `1.5` is `1500`. This is deliberate — floating point
cannot represent `0.10` exactly, so adding prices as decimals drifts by
fractions of a halala until an invoice total disagrees with the sum of its own
lines. The views divide these back out for you.

---

## How the code is organised

Twelve files do the work. Each has one job:

```
app/
├── main.py          every URL, and what happens when it is visited
├── repository.py    every database query, all in one place
├── invoicing.py     the arithmetic: line totals, VAT, discounts  ← most tested
├── money.py         parsing and formatting amounts and quantities
├── db.py            opening the database and applying schema changes
├── forms.py         turning submitted forms into clean, typed values
├── i18n.py          every piece of visible text, English and Arabic side by side
├── pdf.py           the optional PDF download
├── migrations/      numbered .sql files; new ones run automatically on restart
├── templates/       the HTML pages, including the two printable documents
└── static/          one stylesheet for the screen, one for paper, and the
                     editors' scripts (money.js holds the arithmetic both share)
```

The rules that keep it understandable:

- **Nothing except `repository.py` touches the database.** When you want to
  know how something is stored, there is exactly one file to open.
- **`invoicing.py` has no database and no web framework** — just numbers in,
  numbers out. That is why it is easy to test, and the totals are what you
  least want to get wrong.
- **No ORM, no frontend framework, no build step.** The SQL is readable SQL,
  the HTML is readable HTML. Edit a template, refresh the page, see the change.

### Changing something

| You want to… | Edit |
| --- | --- |
| Reword a label, or fix a translation | `app/i18n.py` |
| Change how a page looks | `app/templates/…` and `app/static/css/app.css` |
| Change the printed invoice | `app/templates/invoice_print.html`, `static/css/print.css` |
| Change the printed contract | `app/templates/contract_print.html`, `static/css/print.css` |
| Change the notice or authorization wording | Settings → Repair contract, in the app |
| Change how a total is worked out | `app/invoicing.py` (and its tests) |
| Add a field to a table | a new file in `app/migrations/`, then `repository.py` |

**Adding a database column**, start to finish:

1. Create `app/migrations/002_add_something.sql` containing e.g.
   `ALTER TABLE customers ADD COLUMN whatsapp TEXT NOT NULL DEFAULT '';`
2. Add `"whatsapp"` to `CUSTOMER_FIELDS` in `app/repository.py`
3. Add the input to `app/templates/customer_form.html` and the form parameter
   in `app/main.py`
4. Restart. The migration runs by itself, once, and is recorded so it never
   runs twice.

Never edit `001_initial.sql` after real data exists — it has already run, and
changing it will not re-run it. Always add a new numbered file.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest                # 175 tests, about five seconds
ruff check .          # style and common mistakes
```

Run `pytest` before and after every change you make. It is the fastest way to
find out whether you broke something, and it costs three seconds.

The tests are in three groups, and the split is intentional:

- `tests/test_invoicing.py` — the maths. Rounding, VAT added vs VAT included,
  discounts, a hundred lines of 0.10 totalling exactly 10.00.
- `tests/test_repository.py` — what the database stores and what it refuses:
  invoice numbers never repeating, an issued invoice never being deletable, a
  catalogue price change never altering an invoice already issued.
- `tests/test_contracts.py` — the contract and its conversion: contracts
  numbered in their own series, a contract invoiced exactly once and frozen
  afterwards, and the printed copy looking the same in either language.
- `tests/test_web.py` — the pages load, forms save, bad input comes back as a
  message instead of a crash, Arabic flips the page.

---

## GitHub and CI, briefly

If this is your first repository, here is what the moving parts actually are.

**Git** records snapshots of your files on your own computer. **GitHub** keeps a
copy of that history online. Three commands cover almost everything:

```bash
git add -A                        # choose what goes in the next snapshot
git commit -m "Add WhatsApp field to customers"   # take the snapshot
git push                          # send it to GitHub
```

**Branches.** `main` is the version that works. When you change something,
work on a branch and merge it back once the tests pass:

```bash
git checkout -b add-whatsapp-field
# ...edit, test...
git add -A && git commit -m "Add WhatsApp field to customers"
git push -u origin add-whatsapp-field
```

GitHub then offers to open a **pull request** — a page showing exactly what
changed, where you (or anyone else) can review it before it joins `main`.

**CI** is the file at `.github/workflows/ci.yml`. Every time you push, GitHub
rents a fresh computer, installs this project on it from scratch, runs `ruff`
and `pytest` on four Python versions, and builds and starts the Docker image to
prove it actually runs. You get a green tick or a red cross next to your
commit. You do not have to configure anything — the file being in the
repository is enough.

Why it is worth having: it catches the change that works on your machine but
not on anyone else's, and it proves the install instructions in this README
still work, because CI follows them from nothing every single time.

---

## Where to take it next

Roughly in order of how much they would be worth against how hard they are:

1. **Nightly automatic backup** to a second drive — a scheduled task calling
   `backup_to()`. Small change, removes the biggest risk here.
2. **Logins** if more than one person starts using it, or it leaves the office
   network.
3. **A business summary page** — revenue by month, top services, customers by
   spend. The views above do most of the work already.
4. **Inventory** — stock levels on parts, decremented when an invoice is
   issued, with a low-stock list.
5. **ZATCA e-invoicing** — the real project if the business is in scope for
   Phase 2. Check the current requirements first; it is XML generation,
   cryptographic stamping and a portal integration, and it is considerably more
   work than everything above put together.
7. **WhatsApp or SMS** to send the customer their invoice.

---

## Licence

MIT — see [LICENSE](LICENSE). Use it, change it, sell it, no obligations.
