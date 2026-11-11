/* ==========================================================================
   Shared number handling for the editors
   ==========================================================================

   The browser mirror of app/money.py. Both editors (invoice and repair
   contract) show running totals as the user types, and those previews have to
   agree exactly with what the server will store -- so the arithmetic here
   follows the same rules: integer minor units, integer thousandths for
   quantity, and halves rounding up.

   Attached to the page as a plain global rather than a module, so it works by
   opening the file with no bundler, no imports and no build step.
   ========================================================================== */

window.CSMoney = (function () {
    "use strict";

    var MINOR = 100;    // halalas per riyal
    var MILLI = 1000;   // thousandths per whole unit

    /* Reads what a person actually typed: thousands separators, a currency
       symbol, Arabic-Indic digits, or an Arabic decimal mark. */
    function parseNumber(text) {
        if (text === null || text === undefined) { return 0; }
        var cleaned = String(text)
            .replace(/[٠-٩]/g, function (d) {       // ٠١٢٣٤٥٦٧٨٩
                return String(d.charCodeAt(0) - 0x0660);
            })
            .replace(/[۰-۹]/g, function (d) {       // ۰۱۲۳۴۵۶۷۸۹
                return String(d.charCodeAt(0) - 0x06F0);
            })
            .replace(/٫/g, ".")                          // Arabic decimal mark
            .replace(/[,٬\s]/g, "")                      // separators
            .replace(/(SAR|ر\.س|﷼)/gi, "")
            .trim();
        var value = parseFloat(cleaned);
        return isFinite(value) ? value : 0;
    }

    /* Math.round takes halves upward for positive numbers, matching
       ROUND_HALF_UP on the server. Every amount here is positive. */
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

    /* qty x price, rounded to the nearest halala -- invoicing.line_total(). */
    function lineTotal(qtyMilli, priceMinor) {
        return Math.round((qtyMilli * priceMinor) / MILLI);
    }

    /* Narrows a vehicle <select> to the cars belonging to the chosen customer,
       and copies that car's last odometer reading across when the field is
       still empty. Used by both editors.  */
    function linkCustomerToVehicle(customerSelect, vehicleSelect, odometerInput) {
        if (!customerSelect || !vehicleSelect) { return function () {}; }

        function copyOdometer() {
            if (!odometerInput || odometerInput.value) { return; }
            var option = vehicleSelect.selectedOptions[0];
            if (option) {
                var last = option.getAttribute("data-odometer");
                if (last) { odometerInput.value = last; }
            }
        }

        function filter(keepSelection) {
            var customerId = customerSelect.value;
            var current = keepSelection ? vehicleSelect.value : "";
            var stillValid = false;

            Array.prototype.forEach.call(vehicleSelect.options, function (option) {
                if (!option.value) { return; }          // the "no vehicle" entry
                var belongs = option.getAttribute("data-customer") === customerId;
                option.hidden = !belongs;
                option.disabled = !belongs;
                if (belongs && option.value === current) { stillValid = true; }
            });

            vehicleSelect.value = stillValid ? current : "";

            // One car is the common case at a service centre, so pick it and
            // save a click on every job.
            if (!vehicleSelect.value) {
                var visible = Array.prototype.filter.call(
                    vehicleSelect.options,
                    function (o) { return o.value && !o.hidden; }
                );
                if (visible.length === 1) { vehicleSelect.value = visible[0].value; }
            }
            copyOdometer();
        }

        customerSelect.addEventListener("change", function () { filter(false); });
        vehicleSelect.addEventListener("change", copyOdometer);
        filter(true);
        return filter;
    }

    /* Reads the catalogue embedded in the page by the template. */
    function readCatalog() {
        var node = document.getElementById("catalog-data");
        if (!node) { return {}; }
        var byId = {};
        try {
            JSON.parse(node.textContent).forEach(function (item) {
                byId[String(item.id)] = item;
            });
        } catch (err) { /* a malformed block just means no picker help */ }
        return byId;
    }

    return {
        MINOR: MINOR,
        MILLI: MILLI,
        parseNumber: parseNumber,
        toMinor: toMinor,
        toMilli: toMilli,
        formatMinor: formatMinor,
        lineTotal: lineTotal,
        linkCustomerToVehicle: linkCustomerToVehicle,
        readCatalog: readCatalog,
        lang: function () {
            return document.documentElement.lang === "ar" ? "ar" : "en";
        }
    };
})();
