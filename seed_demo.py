"""Fill a database with realistic sample data, for trying the system out.

    python seed_demo.py                     # writes to data/demo.db
    python seed_demo.py --db data/trial.db  # or wherever you like

Then start the application pointed at that file::

    CARSERVICE_DB=data/demo.db ./run.sh          # macOS / Linux
    set CARSERVICE_DB=data\\demo.db && run.bat    # Windows

This is for demonstrations and for finding your way around. It refuses to
write into a database that already has customers in it, so it cannot
accidentally be run against the real one.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from app import repository as repo
from app.db import init_db

CATALOGUE = [
    ("SVC-OIL", "Engine oil change (5W-30, 5L)", "تغيير زيت المحرك", "service", "pcs", 18500),
    ("SVC-LAB", "Labour", "أجرة عمل", "service", "hour", 9000),
    ("SVC-AL", "Wheel alignment", "ضبط زوايا العجلات", "service", "pcs", 12000),
    ("SVC-AC", "Air conditioning service", "صيانة المكيف", "service", "pcs", 25000),
    ("SVC-DIAG", "Computer diagnostics", "فحص كمبيوتر", "service", "pcs", 15000),
    ("SVC-WASH", "Wash and interior clean", "غسيل وتنظيف داخلي", "service", "pcs", 5000),
    ("PRT-OF", "Oil filter", "فلتر زيت", "part", "pcs", 4500),
    ("PRT-AF", "Air filter", "فلتر هواء", "part", "pcs", 6500),
    ("PRT-CF", "Cabin filter", "فلتر مكيف", "part", "pcs", 7500),
    ("PRT-BP", "Brake pads (front set)", "فحمات فرامل أمامية", "part", "set", 32000),
    ("PRT-BAT", "Battery 70Ah", "بطارية ٧٠ أمبير", "part", "pcs", 38000),
    ("PRT-WB", "Wiper blades (pair)", "مساحات زجاج (زوج)", "part", "set", 8500),
]

CUSTOMERS = [
    ("Ahmed Al-Qahtani", "أحمد القحطاني", "0551234567", "ahmed@example.com", "Al Malaz, Riyadh", ""),
    ("Fatimah Al-Dosari", "فاطمة الدوسري", "0509876543", "", "Al Olaya, Riyadh", ""),
    ("Riyadh Logistics Co.", "شركة الرياض اللوجستية", "0112345678", "fleet@example.com",
     "Industrial City 2, Riyadh", "300099887700003"),
    ("Khalid Al-Harbi", "خالد الحربي", "0566677788", "", "Al Naseem, Riyadh", ""),
    ("Sara Al-Mutairi", "سارة المطيري", "0533344455", "", "Al Rawdah, Riyadh", ""),
]

VEHICLES = [
    (1, "ر ن د 4821", "Toyota", "Land Cruiser", 2021, "White", 84500, "JTMHV05J204123456"),
    (1, "ع ب ا 7730", "Lexus", "ES 350", 2019, "Silver", 112300, ""),
    (2, "ك ل م 2284", "Hyundai", "Sonata", 2022, "Blue", 41800, ""),
    (3, "ب ك م 1193", "Isuzu", "NPR", 2019, "White", 212300, ""),
    (3, "ب ك م 1194", "Isuzu", "NPR", 2020, "White", 186400, ""),
    (4, "س ه و 5512", "Nissan", "Patrol", 2018, "Black", 158900, ""),
    (5, "د ر ق 9087", "Kia", "Sportage", 2023, "Grey", 18200, ""),
]

TECHNICIANS = ["Rashid", "Imran", "Saleh", "Bilal"]

DAMAGE_NOTES = [
    "",
    "Scratch on rear bumper, left side.",
    "Small dent on front passenger door.",
    "Front right wheel trim missing. Windscreen chip, driver's side.",
    "Paint scuffed along offside sill.",
]

JOBS = [
    ([("SVC-OIL", 1), ("PRT-OF", 1), ("SVC-LAB", 0.5)], "Next service due in 10,000 km."),
    ([("SVC-AC", 1), ("PRT-CF", 1)], ""),
    ([("PRT-BP", 1), ("SVC-LAB", 2)], "Front discs still within tolerance."),
    ([("SVC-DIAG", 1), ("SVC-LAB", 1)], "Fault code cleared; recommend re-check in a month."),
    ([("PRT-BAT", 1), ("SVC-LAB", 0.5)], "Old battery disposed of."),
    ([("SVC-OIL", 1), ("PRT-OF", 1), ("PRT-AF", 1), ("SVC-LAB", 1)], ""),
    ([("SVC-AL", 1), ("SVC-WASH", 1)], ""),
    ([("PRT-WB", 1), ("SVC-WASH", 1)], ""),
]


def seed(db_file: Path, *, invoice_count: int = 24, force: bool = False) -> None:
    conn = init_db(db_file, verbose=True)

    existing = conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
    if existing and not force:
        print(
            f"\n{db_file} already contains {existing} customer(s).\n"
            "Refusing to add demo data on top of real records.\n"
            "Point --db at a new file, or pass --force if you are sure.",
            file=sys.stderr,
        )
        sys.exit(1)

    rng = random.Random(20261111)   # fixed seed: the same demo data every time

    repo.update_settings(
        conn,
        {
            "business_name_en": "Al Faisal Auto Service",
            "business_name_ar": "مركز الفيصل لخدمة السيارات",
            "vat_number": "300012345600003",
            "cr_number": "1010123456",
            "address_en": "Exit 9, Eastern Ring Road, Riyadh 12345",
            "address_ar": "مخرج ٩، الطريق الدائري الشرقي، الرياض ١٢٣٤٥",
            "phone": "+966 11 234 5678",
            "email": "service@alfaisal.example",
            "vat_rate_bp": 1500,
            "currency_code": "SAR",
            "invoice_prefix": "AF-",
            "next_invoice_seq": 1041,
            "invoice_footer_en": "Parts carry a 6-month warranty. Thank you for your business.",
            "invoice_footer_ar": "قطع الغيار مشمولة بضمان ٦ أشهر. شكراً لتعاملكم معنا.",
        },
    )

    by_code = {}
    for code, name_en, name_ar, kind, unit, price in CATALOGUE:
        by_code[code] = repo.create_catalog_item(
            conn,
            {"code": code, "name_en": name_en, "name_ar": name_ar, "kind": kind,
             "unit": unit, "unit_price_minor": price},
        )

    for name, name_ar, phone, email, address, vat in CUSTOMERS:
        repo.create_customer(
            conn,
            {"name": name, "name_ar": name_ar, "phone": phone, "email": email,
             "address": address, "vat_number": vat},
        )

    for customer_id, plate, make, model, year, colour, odo, vin in VEHICLES:
        repo.create_vehicle(
            conn,
            {"customer_id": customer_id, "plate_no": plate, "make": make, "model": model,
             "model_year": year, "colour": colour, "odometer": odo, "vin": vin},
        )

    catalogue = {c[0]: c for c in CATALOGUE}
    today = date.today()

    # Every job starts life as a repair contract, the way it does in the
    # workshop. Most are then converted to an invoice; a few are left open with
    # the car still in, and a couple are finished but not yet invoiced.
    for n in range(invoice_count):
        vehicle = VEHICLES[rng.randrange(len(VEHICLES))]
        customer_id = vehicle[0]
        vehicle_id = VEHICLES.index(vehicle) + 1

        lines_spec, note = JOBS[rng.randrange(len(JOBS))]
        items, parts = [], []
        for code, qty in lines_spec:
            _, name_en, name_ar, kind, unit, price = catalogue[code]
            if kind == "part":
                parts.append(
                    {"catalog_item_id": by_code[code], "part_number": "",
                     "description": name_en, "description_ar": name_ar,
                     "qty_milli": int(qty * 1000), "unit_price_minor": price,
                     "sourced_externally": 1 if rng.random() < 0.3 else 0}
                )
            else:
                items.append(
                    {"catalog_item_id": by_code[code], "description": name_en,
                     "description_ar": name_ar,
                     "expense_minor": int(price * qty),
                     "technician_remarks": rng.choice(
                         ["Done", "Completed and tested", "OK", ""]
                     )}
                )
        if not items:   # a parts-only job still needs fitting
            items.append(
                {"catalog_item_id": by_code["SVC-LAB"], "description": "Labour",
                 "description_ar": "أجرة عمل", "expense_minor": 9000,
                 "technician_remarks": "Fitted"}
            )

        days_back = rng.randrange(0, 14) if n % 3 == 0 else rng.randrange(0, 150)
        date_in = today - timedelta(days=days_back)

        order_id = repo.create_repair_order(
            conn,
            {"customer_id": customer_id, "vehicle_id": vehicle_id,
             "date_in": date_in.isoformat(),
             "expected_date_out": (date_in + timedelta(days=2)).isoformat(),
             "odometer": vehicle[6] - rng.randrange(0, 9000),
             "car_code": "", "technician_name": rng.choice(TECHNICIANS),
             "status": "open", "notes": note,
             "damage_notes": rng.choice(DAMAGE_NOTES)},
            items,
            parts,
        )
        repo.sign_repair_order(conn, order_id, True)

        # The most recent handful are still in the workshop.
        if n >= invoice_count - 3:
            continue
        if n >= invoice_count - 5:
            repo.set_order_status(conn, order_id, "completed")
            continue

        invoice_id = repo.convert_order_to_invoice(conn, order_id)
        repo.update_invoice(
            conn,
            invoice_id,
            {"issue_date": date_in.isoformat(), "status": "issued",
             "discount_minor": rng.choice([0, 0, 0, 2500, 5000])},
            [dict(line) for line in repo.get_invoice_items(conn, invoice_id)],
        )

        total = repo.get_invoice(conn, invoice_id)["total_minor"]
        roll = rng.random()
        paid = total if roll < 0.65 else (total // 2 if roll < 0.85 else 0)
        if paid:
            repo.add_payment(
                conn,
                {"invoice_id": invoice_id, "amount_minor": paid,
                 "paid_on": date_in.isoformat(),
                 "method": rng.choice(["cash", "card", "transfer"])},
            )

    stats = repo.dashboard_stats(conn)
    invoices = conn.execute("SELECT COUNT(*) AS n FROM invoices").fetchone()["n"]
    conn.close()

    print(
        f"\nDemo data written to {db_file}\n"
        f"  {len(CUSTOMERS)} customers, {len(VEHICLES)} vehicles, "
        f"{len(CATALOGUE)} catalogue items\n"
        f"  {invoice_count} repair contracts, {invoices} invoices, "
        f"{stats['open_contract_count']} cars still in the workshop\n"
        f"  Outstanding: {stats['outstanding_minor'] / 100:,.2f} SAR "
        f"across {stats['outstanding_count']} invoice(s)\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/demo.db", help="database file to write")
    parser.add_argument("--invoices", type=int, default=24, help="how many invoices")
    parser.add_argument(
        "--force", action="store_true", help="write even if the database has data"
    )
    args = parser.parse_args()
    seed(Path(args.db), invoice_count=args.invoices, force=args.force)


if __name__ == "__main__":
    main()
