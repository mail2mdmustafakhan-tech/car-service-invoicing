/* Customers who are never charged VAT.
 *
 * Some customers do not pay it, and ticking "excluding VAT" by hand on every
 * document for them is both tedious and a thing to forget -- and forgetting
 * means billing somebody tax they do not owe, which they notice. So the
 * answer lives on their record, and choosing them here ticks the box.
 *
 * Two rules, and the second is the one that keeps this honest:
 *
 *   1. It is a default, not a lock. The box stays usable: a standing
 *      arrangement should save somebody from remembering it, not stop them
 *      departing from it on the one job where it does not apply.
 *   2. It never moves silently. A tick-box that changes by itself with no
 *      explanation is indistinguishable from a bug, and the person at the
 *      counter has no way to tell which it was -- so a line appears beside
 *      it saying who it came from, and it disappears the moment the box is
 *      touched by hand.
 */
(function () {
    "use strict";

    var form = document.querySelector("form[data-vat-aware]");
    if (!form) { return; }

    var customers = form.querySelector('select[name="customer_id"]');
    var exclude = form.querySelector('input[name="exclude_vat"]');
    if (!customers || !exclude) { return; }

    var note = document.createElement("p");
    note.className = "hint vat-note";
    note.hidden = true;
    exclude.closest(".field").appendChild(note);

    /* Set by hand, this is left alone for the rest of the visit. Somebody
       who has made a decision about this document should not have it
       quietly undone by switching the customer and switching back. */
    var touched = false;
    exclude.addEventListener("change", function () {
        touched = true;
        note.hidden = true;
    });

    function apply() {
        if (touched) { return; }

        var chosen = customers.selectedOptions[0];
        var exempt = !!(chosen && chosen.getAttribute("data-no-vat"));

        exclude.checked = exempt;
        note.hidden = !exempt;
        if (exempt) {
            note.textContent = form.getAttribute("data-vat-note") || "";
        }
    }

    customers.addEventListener("change", apply);

    /* Not on arrival at an existing document: what that document says about
       its own VAT is a fact about what was charged, and the customer's
       standing arrangement today must not reach back and restate it. */
    if (!form.hasAttribute("data-editing")) { apply(); }
})();
