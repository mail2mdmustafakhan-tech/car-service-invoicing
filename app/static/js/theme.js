/* Light and dark.
 *
 * The choice is saved in this browser, not on the server: it is a property
 * of the screen you are sitting at, not of the business. The same database
 * opened on the workshop PC and on a laptop can sensibly want different
 * answers, and nothing about an invoice changes either way.
 *
 * The attribute is applied in the <head>, before the stylesheet loads, so
 * there is no white flash on the way to a dark page. All this file does is
 * flip it and remember the result.
 */
(function () {
    "use strict";

    var KEY = "cs-theme";
    var root = document.documentElement;
    var button = document.getElementById("themetoggle");
    if (!button) { return; }

    function current() {
        var set = root.getAttribute("data-theme");
        if (set === "dark" || set === "light") { return set; }
        /* Nothing chosen yet: follow whatever the computer is set to, so a
           machine already running dark does not get a white page. */
        if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
            return "dark";
        }
        return "light";
    }

    function apply(theme) {
        root.setAttribute("data-theme", theme);
        button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
        try {
            localStorage.setItem(KEY, theme);
        } catch (e) {
            /* Storage unavailable. The theme still applies for this page;
               it just will not be remembered. Not worth telling anyone. */
        }
    }

    apply(current());

    button.addEventListener("click", function () {
        apply(current() === "dark" ? "light" : "dark");
    });

    /* If the computer switches between light and dark -- some do it at
       sunset -- follow along, but only while nobody has made a choice of
       their own here. An explicit choice outranks the operating system. */
    if (window.matchMedia) {
        var query = window.matchMedia("(prefers-color-scheme: dark)");
        var onChange = function (event) {
            var chosen = null;
            try { chosen = localStorage.getItem(KEY); } catch (e) { /* ignore */ }
            if (chosen !== "dark" && chosen !== "light") {
                root.setAttribute("data-theme", event.matches ? "dark" : "light");
            }
        };
        if (query.addEventListener) { query.addEventListener("change", onChange); }
        else if (query.addListener) { query.addListener(onChange); }
    }
})();
