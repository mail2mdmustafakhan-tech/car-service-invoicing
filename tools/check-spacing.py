#!/usr/bin/env python3
"""Find text sitting too close to the edge of the panel it is in.

Run it against a server that is already up:

    python3 -m uvicorn app.main:app --port 8077 &
    python3 tools/check-spacing.py            # or ... --url http://host:port

Why this exists rather than a unit test: a test that reads the stylesheet
and asserts a padding value breaks the first time a rule is renamed and
protects nothing in between (see bug 25 in the project notes). This
measures the rendered page instead, so it keeps working through any
amount of refactoring and catches the thing that actually matters --
whether a reader can see a gap.

Why it measures *text* and not element boxes: padding does not move a
block element's border box, and a table cell's box is meant to reach the
panel border so that its row rule does. Measuring boxes reports both as
crowded when they are perfectly fine. The glyphs are what the eye
judges, so the glyphs are what this measures, via a Range around each
text node.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

#: A panel's body padding is 16px. Half of that is a generous floor:
#: below it, text reads as touching the border.
FLOOR_PX = 8

FIND_TEXT_NEAR_EDGES = """() => {
  const bad = [];
  const seen = new Set();
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walk.nextNode())) {
    if (!node.textContent.trim()) continue;
    const el = node.parentElement;
    if (!el || !el.offsetParent) continue;
    const panel = el.closest('.panel, .card');
    // Contents of a horizontally scrolling box are meant to run past the
    // edge; that is what the scrolling is for.
    if (!panel || el.closest('.scrollx')) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const r = range.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const p = panel.getBoundingClientRect();
    const left = r.left - p.left;
    const right = p.right - r.right;
    if (left < FLOOR || right < FLOOR) {
      const key = el.tagName + '.' + el.className;
      if (seen.has(key)) continue;
      seen.add(key);
      bad.push({
        where: key,
        text: node.textContent.trim().slice(0, 30),
        left: Math.round(left),
        right: Math.round(right),
      });
    }
  }
  return bad;
}"""


async def run(url: str, widths: list[int], langs: list[str]) -> int:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright is not installed; skipping", file=sys.stderr)
        return 0

    script = FIND_TEXT_NEAR_EDGES.replace("FLOOR", str(FLOOR_PX))
    problems = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": widths[0], "height": 900})
        await page.goto(url + "/")
        paths = await page.evaluate(
            """() => [...new Set([...document.querySelectorAll('a[href^="/"]')]
                 .map(a => a.getAttribute('href'))
                 .filter(h => !h.startsWith('/lang/') && !h.includes('.')))]"""
        )
        for extra in ("/settings", "/settings/performance", "/catalog/import"):
            if extra not in paths:
                paths.append(extra)

        for width in widths:
            await page.set_viewport_size({"width": width, "height": 900})
            for lang in langs:
                await page.goto(f"{url}/lang/{lang}")
                for path in paths:
                    response = await page.goto(url + path)
                    if response is None or response.status >= 400:
                        continue
                    for bad in await page.evaluate(script):
                        problems += 1
                        print(
                            f"{width}px {lang} {path}: {bad['where']} "
                            f"left={bad['left']} right={bad['right']} "
                            f"-- {bad['text']!r}"
                        )
        print(
            f"\nchecked {len(paths)} pages x {len(widths)} widths "
            f"x {len(langs)} languages; {problems} crowded"
        )
        await browser.close()
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8077")
    parser.add_argument("--widths", default="1280,390")
    parser.add_argument("--langs", default="en,ar")
    args = parser.parse_args()
    return asyncio.run(
        run(
            args.url.rstrip("/"),
            [int(w) for w in args.widths.split(",")],
            args.langs.split(","),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
