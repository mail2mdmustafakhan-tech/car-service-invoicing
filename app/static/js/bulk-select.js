/*
  Ticking rows in a list and acting on all of them with one button.

  Written to be generic: any form marked data-bulk gets this, so the
  next list that wants it needs no new script. The markup contract is
  four attributes --

    data-bulk          on the form
    data-bulk-all      the checkbox in the table head
    data-bulk-bar      the strip holding the button
    data-bulk-count    where "7 selected" is written
    data-confirm       the sentence shown before the form submits

  Everything here is a convenience over markup that already works. With
  JavaScript switched off the checkboxes still tick, the bar is simply
  always visible, and the button still submits. The only thing lost is
  the select-all and the running count, and neither is load-bearing.
*/
(function () {
    "use strict";

    function wire(form) {
        var boxes = [].slice.call(
            form.querySelectorAll('input[type="checkbox"][name="ids"]'));
        var all = form.querySelector("[data-bulk-all]");
        var bar = form.querySelector("[data-bulk-bar]");
        var count = form.querySelector("[data-bulk-count]");
        if (!boxes.length) { return; }

        /* The count template comes from the page so it stays translated:
           "{n} selected" in English, and its own wording in Arabic. */
        var template = (count && count.getAttribute("data-template")) || "";

        function ticked() {
            return boxes.filter(function (b) { return b.checked; }).length;
        }

        function refresh() {
            var n = ticked();
            if (bar) { bar.hidden = n === 0; }
            if (count) {
                count.textContent = template
                    ? template.replace("{n}", String(n))
                    : String(n);
            }
            if (all) {
                all.checked = n === boxes.length && n > 0;
                /* Neither on nor off: some rows are ticked. Without this
                   the header box reads as "none selected" while seven
                   are, which is worse than showing nothing at all. */
                all.indeterminate = n > 0 && n < boxes.length;
            }
        }

        if (all) {
            all.addEventListener("change", function () {
                boxes.forEach(function (b) { b.checked = all.checked; });
                refresh();
            });
        }
        boxes.forEach(function (b) {
            b.addEventListener("change", refresh);
        });

        form.addEventListener("submit", function (event) {
            if (ticked() === 0) {
                /* The button is hidden in this state, so reaching here
                   means something else submitted the form. Stop rather
                   than make a round trip to be told nothing happened. */
                event.preventDefault();
                return;
            }
            var question = form.getAttribute("data-confirm");
            if (question && !window.confirm(question)) {
                event.preventDefault();
            }
        });

        refresh();
    }

    function start() {
        [].slice.call(document.querySelectorAll("form[data-bulk]")).forEach(wire);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}());
