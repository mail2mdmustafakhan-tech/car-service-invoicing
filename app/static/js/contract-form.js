/* ==========================================================================
   The repair contract editor
   ==========================================================================

   Two line tables rather than one: the repairs the owner asked for (with the
   technician's remarks and a labour cost), and the spare parts fitted.

   As with the invoice editor, the totals here are a preview only -- the
   contract's figures are recalculated on the server when it is saved, and
   again when it becomes an invoice. Shared arithmetic lives in money.js so
   the two editors cannot drift apart.
   ========================================================================== */

(function () {
    "use strict";

    var M = window.CSMoney;
    var form = document.getElementById("contract-form");
    if (!form || !M) { return; }

    var repairsBody = document.getElementById("repairs-body");
    var partsBody = document.getElementById("parts-body");
    var repairTemplate = document.getElementById("repair-template");
    var partTemplate = document.getElementById("part-template");
    var lang = M.lang();
    var catalogById = M.readCatalog();

    var markupHint = document.getElementById("markup-hint");
    var markupBp = markupHint
        ? parseInt(markupHint.getAttribute("data-markup-bp"), 10) || 0
        : 0;

    /* ---------------------------------------------------------------------
       Running estimate
       --------------------------------------------------------------------- */

    function recalculate() {
        var labour = 0;
        Array.prototype.forEach.call(
            repairsBody.querySelectorAll(".line-expense"),
            function (input) { labour += M.toMinor(input.value); }
        );

        var parts = 0;
        Array.prototype.forEach.call(
            partsBody.querySelectorAll(".line-row"),
            function (row) {
                var total = M.lineTotal(
                    M.toMilli(row.querySelector(".line-qty").value),
                    M.toMinor(row.querySelector(".line-price").value)
                );
                row.querySelector(".line-total").textContent = M.formatMinor(total);
                parts += total;
            }
        );

        document.getElementById("t-labour").textContent = M.formatMinor(labour);
        document.getElementById("t-parts").textContent = M.formatMinor(parts);
        document.getElementById("t-estimate").textContent = M.formatMinor(labour + parts);
    }

    /* ---------------------------------------------------------------------
       Filling a line from the catalogue
       --------------------------------------------------------------------- */

    function applyCatalogPick(row, priceSelector) {
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

        var price = row.querySelector(priceSelector);
        if (price) { price.value = item.price; }
        recalculate();
    }

    /* ---------------------------------------------------------------------
       Adding and removing rows. Both tables behave the same way, so one pair
       of helpers drives them with the fields to blank passed in.
       --------------------------------------------------------------------- */

    function addRow(body, template, focus) {
        var row = template.content.firstElementChild.cloneNode(true);
        body.appendChild(row);
        if (focus) {
            var first = row.querySelector(".line-picker, input");
            if (first) { first.focus(); }
        }
        recalculate();
        return row;
    }

    function removeRow(body, row, keepLast) {
        if (keepLast && body.querySelectorAll(".line-row").length <= 1) {
            Array.prototype.forEach.call(row.querySelectorAll("input"), function (input) {
                input.value = input.classList.contains("line-qty") ? "1" : "";
            });
            Array.prototype.forEach.call(row.querySelectorAll("select"), function (select) {
                select.selectedIndex = 0;
            });
            recalculate();
            return;
        }
        row.remove();
        recalculate();
    }

    function wire(body, template, priceSelector, keepLast) {
        body.addEventListener("input", function (event) {
            if (event.target.closest(".line-qty, .line-price, .line-expense")) {
                recalculate();
            }
        });
        body.addEventListener("change", function (event) {
            var row = event.target.closest(".line-row");
            if (row && event.target.classList.contains("line-picker")) {
                applyCatalogPick(row, priceSelector);
            }
            if (row && event.target.classList.contains("line-sourced")) {
                showMarkup(row);
            }
        });
        body.addEventListener("click", function (event) {
            var button = event.target.closest(".line-remove");
            if (button) { removeRow(body, button.closest(".line-row"), keepLast); }
        });
    }

    /* ---------------------------------------------------------------------
       The agency handling percentage.

       The printed notice tells the customer that parts obtained from an
       agency carry a handling charge. This only ever *shows* what that price
       would be -- it never rewrites the figure behind the advisor's back,
       because a price that changes itself is a price nobody trusts.
       --------------------------------------------------------------------- */

    function showMarkup(row) {
        var existing = row.querySelector(".markup-note");
        if (existing) { existing.remove(); }
        if (!markupBp) { return; }

        var sourced = row.querySelector(".line-sourced");
        var price = row.querySelector(".line-price");
        if (!sourced || !price || sourced.value !== "1") { return; }

        var base = M.toMinor(price.value);
        if (!base) { return; }

        var withMarkup = base + Math.round((base * markupBp) / 10000);
        var note = document.createElement("div");
        note.className = "markup-note hint";
        note.textContent = "+" + (markupBp / 100) + "% → " + M.formatMinor(withMarkup);
        price.parentNode.appendChild(note);
    }

    partsBody.addEventListener("input", function (event) {
        if (event.target.classList.contains("line-price")) {
            showMarkup(event.target.closest(".line-row"));
        }
    });

    /* ---------------------------------------------------------------------
       Start-up
       --------------------------------------------------------------------- */

    wire(repairsBody, repairTemplate, null, true);
    wire(partsBody, partTemplate, ".line-price", false);

    document.getElementById("add-repair").addEventListener("click", function () {
        addRow(repairsBody, repairTemplate, true);
    });
    document.getElementById("add-part").addEventListener("click", function () {
        addRow(partsBody, partTemplate, true);
    });

    M.linkCustomerToVehicle(
        document.getElementById("f_customer_id"),
        document.getElementById("f_vehicle_id"),
        document.getElementById("f_odometer")
    );

    // Open each table with a row ready to type into. A contract may end up
    // with no parts at all, and the server drops an untouched row, so an
    // empty one costs nothing and saves a click on every job that does.
    if (!repairsBody.querySelectorAll(".line-row").length) {
        addRow(repairsBody, repairTemplate, false);
    }
    if (!partsBody.querySelectorAll(".line-row").length) {
        addRow(partsBody, partTemplate, false);
    }
    Array.prototype.forEach.call(partsBody.querySelectorAll(".line-row"), showMarkup);
    recalculate();
})();
