/* Warn when a flagged customer is chosen.
 *
 * The register marks some customers "do not receive this car". That decision
 * is worth nothing unless it reaches whoever is booking the car in, at the
 * moment they pick the name -- not on a page they had no reason to open.
 *
 * Two levels of interruption, deliberately:
 *
 *   refuse / check  a modal dialog. The form cannot be filled in behind it
 *                   and it has to be dismissed on purpose.
 *   note            the banner only.
 *
 * The third level exists so the first two keep working. Interrupting someone
 * to tell them a driver's name is how people learn to dismiss warnings
 * without reading them, and then the one that mattered goes unread too.
 */
(function () {
    "use strict";

    var select = document.querySelector("select[name='customer_id']");
    var dialog = document.getElementById("customer-alert");
    var banner = document.getElementById("customer-alert-banner");
    if (!select || !banner) { return; }

    var el = {
        level: document.getElementById("customer-alert-level"),
        name: document.getElementById("customer-alert-name"),
        note: document.getElementById("customer-alert-note"),
        when: document.getElementById("customer-alert-when"),
        bannerLevel: document.getElementById("customer-alert-banner-level"),
        bannerNote: document.getElementById("customer-alert-banner-note")
    };

    /* Dismissing it once should not mean being shown it again on every
       unrelated change to the form -- but picking a different customer and
       coming back is a new decision, and gets a new warning. */
    var warned = null;

    function show(option) {
        var level = option.getAttribute("data-alert-level");
        var label = option.getAttribute("data-alert-label") || "";
        var note = option.getAttribute("data-alert-note") || "";
        var when = option.getAttribute("data-alert-when") || "";

        banner.hidden = false;
        banner.className = "alert-banner alert-" + level;
        el.bannerLevel.textContent = label;
        el.bannerNote.textContent = note;

        if (level === "note" || !dialog || !dialog.showModal) { return; }
        if (warned === option.value) { return; }
        warned = option.value;

        el.level.textContent = label;
        el.level.className = "alert-chip";
        el.name.textContent = option.textContent.trim();
        el.note.textContent = note;
        el.when.textContent = when ? (el.when.getAttribute("data-prefix") || "") + " " + when : "";
        dialog.className = "alert-dialog alert-" + level;
        dialog.showModal();
    }

    function clear() {
        banner.hidden = true;
        banner.className = "alert-banner";
    }

    function check() {
        var option = select.options[select.selectedIndex];
        if (option && option.getAttribute("data-alert-level")) {
            show(option);
        } else {
            clear();
            warned = null;
        }
    }

    var closeButton = document.getElementById("customer-alert-close");
    if (closeButton && dialog) {
        closeButton.addEventListener("click", function () { dialog.close(); });
    }

    select.addEventListener("change", check);

    /* Also on load: an estimate being edited, or a form that arrived with the
       customer already chosen, has exactly the same problem. The banner
       appears; the dialog does not, because nobody just made a choice. */
    var initial = select.options[select.selectedIndex];
    if (initial && initial.getAttribute("data-alert-level")) {
        warned = initial.value;
        show(initial);
    }
})();
