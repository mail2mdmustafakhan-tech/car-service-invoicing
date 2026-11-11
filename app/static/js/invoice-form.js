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
   step for step (integer minor units, half-up rounding) so the preview and
   the saved invoice always agree.

   Plain browser JavaScript, no libraries, no build step.
   ========================================================================== */

(function () {
    "use strict";

    var BP_PER_UNIT = 10000;   // 15% is 1500 basis points
    var MINOR = 100;           // halalas per riyal
    var MILLI = 1000;          // thousandths per unit

    var form = document.getElementById("invoice-form");
    if (!form) { return; }

    var body = document.getElementById("lines-body");
    var template = document.getElementById("line-template");
    var lang = document.documentElement.lang === "ar" ? "ar" : "en";

    var catalog = [];
    try {
        catalog = JSON.parse(document.getElementById("catalog-data").textContent) || [];
    } catch (err) {
        catalog = [];
    }

    var catalogById = {};
    catalog.forEach(function (item) { catalogById[String(item.id)] = item; });

    /* ---------------------------------------------------------------------
       Number handling. Mirrors app/money.py: parse to integer minor units,
       round halves up, never carry a fraction in a float.
       --------------------------------------------------------------------- */

    function parseNumber(text) {
        if (text === null || text === undefined) { return 0; }
        var cleaned = String(text)
            .replace(/[٠-٩]/g, function (d) {       // Arabic-Indic digits
                return String(d.charCodeAt(0) - 0x0660);
            })
            .replace(/[۰-۹]/g, function (d) {       // Eastern Arabic-Indic
                return String(d.charCodeAt(0) - 0x06F0);
            })
            .replace(/٫/g, ".")                          // Arabic decimal mark
            .replace(/[,٬\s]/g, "")                      // separators
            .trim();
        var value = parseFloat(cleaned);
        return isFinite(value) ? value : 0;
    }

    /* Math.round takes halves upward for positive numbers, which is the same
       convention as ROUND_HALF_UP on the server. Every amount here is
       positive, so the two agree. */
    function toMinor(text) { return Math.round(parseNumber(text) * MINOR); }
    function toMilli(text) { return Math.round(parseNumber(text) * MILLI); }

    function formatMinor(minor) {
        var sign = minor < 0 ? "-" : "";
        var abs = Math.abs(minor);
        var whole = Math.floor(abs / MINOR);
        var cents = abs % MINOR;
        return sign + whole.toLocaleString("en-US") + "." +
               (cents < 10 ? "0" + cents : String(cents));
    }

    /* ---------------------------------------------------------------------
       Totals -- the same sequence of steps as invoicing.compute_totals()
       --------------------------------------------------------------------- */

    function recalculate() {
        var subtotal = 0;

        Array.prototype.forEach.call(body.querySelectorAll(".line-row"), function (row) {
            var qtyMilli = toMilli(row.querySelector(".line-qty").value);
            var priceMinor = toMinor(row.querySelector(".line-price").value);
            var lineTotal = Math.round((qtyMilli * priceMinor) / MILLI);

            row.querySelector(".line-total").textContent = formatMinor(lineTotal);
            subtotal += lineTotal;
        });

        var rateBp = Math.round(parseNumber(document.getElementById("f_vat_rate").value) * 100);
        if (rateBp < 0) { rateBp = 0; }

        var discount = toMinor(document.getElementById("f_discount").value);
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

        document.getElementById("t-subtotal").textContent = formatMinor(subtotal);
        document.getElementById("t-discount").textContent = "-" + formatMinor(discount);
        document.getElementById("t-taxable").textContent = formatMinor(taxable);
        document.getElementById("t-vat").textContent = formatMinor(vat);
        document.getElementById("t-total").textContent = formatMinor(total);
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
        row.querySelector(".line-desc").value = lang === "ar" && item.name_ar
            ? item.name_ar
            : item.name_en;
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
        if (!row) { return; }
        if (event.target.classList.contains("line-picker")) { applyCatalogPick(row); }
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
       Customer -> vehicle
       --------------------------------------------------------------------- */

    var customerSelect = document.getElementById("f_customer_id");
    var vehicleSelect = document.getElementById("f_vehicle_id");

    function filterVehicles(keepSelection) {
        if (!customerSelect || !vehicleSelect) { return; }
        var customerId = customerSelect.value;
        var current = keepSelection ? vehicleSelect.value : "";
        var stillValid = false;

        Array.prototype.forEach.call(vehicleSelect.options, function (option) {
            if (!option.value) { return; }              // the "no vehicle" option
            var belongs = option.getAttribute("data-customer") === customerId;
            option.hidden = !belongs;
            option.disabled = !belongs;
            if (belongs && option.value === current) { stillValid = true; }
        });

        vehicleSelect.value = stillValid ? current : "";

        // If the customer owns exactly one car, pick it -- that is the common
        // case at a service centre and saves a click on every invoice.
        if (!vehicleSelect.value) {
            var visible = Array.prototype.filter.call(vehicleSelect.options, function (o) {
                return o.value && !o.hidden;
            });
            if (visible.length === 1) { vehicleSelect.value = visible[0].value; }
        }

        copyOdometer();
    }

    function copyOdometer() {
        var odometer = document.getElementById("f_odometer");
        if (!odometer || odometer.value || !vehicleSelect) { return; }
        var option = vehicleSelect.selectedOptions[0];
        if (option) {
            var last = option.getAttribute("data-odometer");
            if (last) { odometer.value = last; }
        }
    }

    if (customerSelect) {
        customerSelect.addEventListener("change", function () { filterVehicles(false); });
    }
    if (vehicleSelect) {
        vehicleSelect.addEventListener("change", copyOdometer);
    }

    /* ---------------------------------------------------------------------
       Start-up
       --------------------------------------------------------------------- */

    if (!body.querySelectorAll(".line-row").length) {
        addLine(false);
    }
    filterVehicles(true);
    recalculate();
})();
