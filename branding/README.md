# Branding

The Advance Repair Center emblem, redrawn as vector artwork from a photograph
of the workshop's printed contract.

| File | Use it for |
| --- | --- |
| `arc-logo.svg` | **The master.** Infinitely scalable — give this to a printer, a sign-maker, or anyone producing artwork. Edit it in any text editor or in Inkscape, Illustrator or Figma. |
| `arc-logo-512.png` | **Upload this one to the software.** Transparent background, plenty of resolution for the ~19 mm it prints at. |
| `arc-logo-1024.png` | Same again, larger, for anywhere that needs more detail. |
| `arc-logo-512-white.png` | Flattened onto white, for anywhere a transparent background is awkward. |

## Uploading it

Settings → Logo → choose `arc-logo-512.png` → Upload logo.

It is stored inside the database, not as a file beside it, so it travels with
every backup you take.

## Changing it

Everything in the SVG derives from four numbers, set near the top of the file:
the centre, the ring's outer radius, the band width, and the letter stroke
weight. Change one and the mark stays in proportion.

Three things in particular are worth knowing how to change:

- **The Arabic** is one line: the text inside `<textPath>`, currently
  `مركز الاصلاح المتقدم`.
- **The colour** is `#26307E`, sampled from the photographed form and
  therefore approximate. If the business has a brand colour, replace every
  occurrence in the `<style>` block.
- **The font** is Noto Kufi Arabic, with fallbacks. Change the `font-family`
  list if the business has a house font.

After editing the SVG, re-export the PNGs at 512 and 1024 pixels tall with a
transparent background, and upload the 512 again.
