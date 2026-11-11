/* ==========================================================================
   The invoice editor
   ==========================================================================

   Three jobs, and nothing else:

   1. Narrow the vehicle list to the chosen customer's cars.
   2. Fill a line in when a catalogue item is picked.
   3. Keep the totals on screen in step as numbers are typed.

   The totals shown here are a *preview*. The figures that get stored are
   always recalculated on the server by app/invoicing.py -- this file never
   submits a total. The arithmetic below deliberately mirrors that module
   step for step, using the shared helpers in money.js, so the preview and
   the saved invoice always agree.

   Plain browser JavaScript, no libraries, no build step.
   ========================================================================== */

(function () {
    "use strict";

    var M = window.CSMoney;
    var BP_PER_UNIT = 10000;   // 15% is 1500 basis points

    var form = document.getElementById("invoice-form");
    if (!form || !M) { return; }

    var body = document.getElementById("lines-body");
    var template = document.getElementById("line-template");
    var lang = M.lang();
    var catalogById = M.readCatalog();

    /* ---------------------------------------------------------------------
       Totals -- the same sequence of steps as invoicing.compute_totals()
       --------------------------------------------------------------------- */

    function recalculate() {
        var subtotal = 0;

        Array.prototype.forEach.call(body.querySelectorAll(".line-row"), function (row) {
            var total = M.lineTotal(
                M.toMilli(row.querySelector(".line-qty").value),
                M.toMinor(row.querySelector(".line-price").value)
            );
            row.querySelector(".line-total").textContent = M.formatMinor(total);
            subtotal += total;
        });

        var rateBp = Math.round(M.parseNumber(document.getElementById("f_vat_rate").value) * 100);
        if (rateBp < 0) { rateBp = 0; }

        var discount = M.toMinor(document.getElementById("f_discount").value);
        if (discount > subtotal) { discount = subtotal; }   // never go negative

        var afterDiscount = subtotal - discount;
        var includeVat = document.getElementById("f_include_vat").checked;

        var taxable, vat, total;
        if (includeVat) {
            taxable = Math.round((afterDiscount * BP_PER_UNIT) / (BP_PER_UNIT + rateBp));
            vat = afterDiscount - taxable;
            total = afterDiscount;
        } else {
            taxable = afterDiscount;
            vat = Math.round((taxable * rateBp) / BP_PER_UNIT);
            total = taxable + vat;
        }

        document.getElementById("t-subtotal").textContent = M.formatMinor(subtotal);
        document.getElementById("t-discount").textContent = "-" + M.formatMinor(discount);
        document.getElementById("t-taxable").textContent = M.formatMinor(taxable);
        document.getElementById("t-vat").textContent = M.formatMinor(vat);
        document.getElementById("t-total").textContent = M.formatMinor(total);
        document.getElementById("t-rate").textContent = String(rateBp / 100);

        // The discount row only earns its space when there is a discount.
        document.getElementById("t-discount-row").style.display = discount ? "" : "none";
    }

    /* ---------------------------------------------------------------------
       Lines
       --------------------------------------------------------------------- */

    function applyCatalogPick(row) {
        var picker = row.querySelector(".line-picker");
        var item = catalogById[picker.value];
        if (!item) {
            row.querySelector(".line-catalog").value = "";
            return;
        }

        row.querySelector(".line-catalog").value = item.id;
        row.querySelector(".line-desc").value =
            lang === "ar" && item.name_ar ? item.name_ar : item.name_en;
        row.querySelector(".line-desc-ar").value = item.name_ar || "";
        row.querySelector(".line-kind").value = item.kind || "service";
        row.querySelector(".line-price").value = item.price;

        var unit = row.querySelector(".line-unit");
        if (item.unit) { unit.value = item.unit; }

        recalculate();
    }

    function addLine(focus) {
        var row = template.content.firstElementChild.cloneNode(true);
        body.appendChild(row);
        if (focus) { row.querySelector(".line-picker").focus(); }
        recalculate();
        return row;
    }

    function removeLine(row) {
        // Always leave one row, so the form is never empty and unusable.
        if (body.querySelectorAll(".line-row").length <= 1) {
            row.querySelector(".line-desc").value = "";
            row.querySelector(".line-qty").value = "1";
            row.querySelector(".line-price").value = "";
            row.querySelector(".line-catalog").value = "";
            row.querySelector(".line-picker").value = "";
            recalculate();
            return;
        }
        row.remove();
        recalculate();
    }

    /* One set of listeners on the table, rather than per row, so rows added
       later behave the same as rows that were there at load. */
    body.addEventListener("input", function (event) {
        if (event.target.closest(".line-qty, .line-price")) { recalculate(); }
    });

    body.addEventListener("change", function (event) {
        var row = event.target.closest(".line-row");
        if (row && event.target.classList.contains("line-picker")) {
            applyCatalogPick(row);
        }
    });

    body.addEventListener("click", function (event) {
        var button = event.target.closest(".line-remove");
        if (button) { removeLine(button.closest(".line-row")); }
    });

    document.getElementById("add-line").addEventListener("click", function () {
        addLine(true);
    });

    ["f_vat_rate", "f_discount", "f_include_vat"].forEach(function (id) {
        var element = document.getElementById(id);
        if (element) {
            element.addEventListener("input", recalculate);
            element.addEventListener("change", recalculate);
        }
    });

    /* ---------------------------------------------------------------------
       Start-up
       --------------------------------------------------------------------- */

    M.linkCustomerToVehicle(
        document.getElementById("f_customer_id"),
        document.getElementById("f_vehicle_id"),
        document.getElementById("f_odometer")
    );

    if (!body.querySelectorAll(".line-row").length) { addLine(false); }
    recalculate();
})();
