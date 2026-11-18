/* The customer picker's search box.
 *
 * The page arrives with a short list of customers in the <select>. Typing in
 * the box above it replaces that list with what the server matches, so the
 * four thousand customers nobody could scroll through are reachable in three
 * keystrokes instead of being shipped to the browser on every page load.
 *
 * Three rules this follows, each of which is a bug if broken:
 *
 *   1. The chosen customer is never dropped from the list. Replacing the
 *      options while one is selected would clear the field, and on an edit
 *      form that means saving an invoice onto nobody.
 *   2. A reply that arrives after a newer one is thrown away. Typing "mu" then
 *      "muh" fires two requests, and the slower one must not win.
 *   3. Emptying the box puts the original list back, rather than leaving the
 *      last search's results looking like the whole list.
 *
 * The alert data travels on each <option>, so customer-alert.js keeps working
 * on searched results exactly as it does on the ones rendered by the server.
 */
(function () {
    "use strict";

    var DEBOUNCE_MS = 180;

    function optionFor(item) {
        var option = document.createElement("option");
        option.value = String(item.id);
        option.textContent = item.label;
        if (item.no_vat) {
            option.setAttribute("data-no-vat", "1");
        }
        if (item.alert_level) {
            option.setAttribute("data-alert-level", item.alert_level);
            option.setAttribute("data-alert-label", item.alert_label || "");
            option.setAttribute("data-alert-note", item.alert_note || "");
            option.setAttribute("data-alert-when", item.alert_when || "");
        }
        return option;
    }

    function setUp(search) {
        var select = document.getElementById(
            search.getAttribute("data-picker-search")
        );
        if (!select) { return; }

        /* The list the server sent, kept so an emptied box can restore it. */
        var original = Array.prototype.slice.call(select.options);
        var blank = original[0];
        var timer = null;
        var inFlight = 0;

        function show(items) {
            /* Hold on to the selection, including its alert attributes: if
               the chosen customer is not among the matches we put the very
               same option back rather than rebuilding it from a label. */
            var chosen = select.selectedOptions[0];
            var keep = chosen && chosen.value ? chosen : null;

            select.textContent = "";
            if (blank) { select.appendChild(blank); }

            var seen = {};
            if (keep) {
                select.appendChild(keep);
                seen[keep.value] = true;
            }
            items.forEach(function (item) {
                if (seen[String(item.id)]) { return; }
                select.appendChild(optionFor(item));
            });
            select.value = keep ? keep.value : "";
        }

        function restore() {
            var chosen = select.value;
            select.textContent = "";
            original.forEach(function (option) { select.appendChild(option); });
            select.value = chosen;
        }

        function run() {
            var q = search.value.trim();
            if (!q) { restore(); return; }

            var mine = ++inFlight;
            fetch("/api/customers?q=" + encodeURIComponent(q),
                  { headers: { "Accept": "application/json" } })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (items) {
                    if (mine !== inFlight || items === null) { return; }
                    show(items);
                })
                .catch(function () {
                    /* Offline, or the server said no: leave the list alone
                       rather than emptying it. A picker with nothing in it
                       reads as "no such customer", which is a lie. */
                });
        }

        search.addEventListener("input", function () {
            window.clearTimeout(timer);
            timer = window.setTimeout(run, DEBOUNCE_MS);
        });

        /* Enter in a search box would otherwise submit the form, and on a
           form whose first field is the customer that means saving before
           anybody has chosen one. */
        search.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                window.clearTimeout(timer);
                run();
            }
        });
    }

    Array.prototype.forEach.call(
        document.querySelectorAll("[data-picker-search]"),
        setUp
    );
})();
