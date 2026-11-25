"""Charts, drawn on the server.

No charting library and no JavaScript. Three reasons, in order of how much
they matter here: the page prints as it looks, a workshop PC with a blocked
or slow network still draws its own dashboard, and the project has no build
step to add one to.

**The bars are HTML, not SVG.** They used to be SVG, and three separate
problems all came from that one decision. An SVG with a viewBox 560 wide,
rendered into a 410-wide column, scales everything by 0.73 -- so 12.5px text
arrived at 9px and the figures were squinting-small. A fixed `height`
attribute alongside `width="100%"` letterboxed the drawing, leaving a band
of blank card above and below it. And right-to-left needed every coordinate
mirrored by hand, which the old code did and documented as a bug source.

A bar chart is a list of rows with a name, a proportional width and a
figure. HTML does all three natively: text renders at its real size at any
column width, percentage widths need no viewBox arithmetic, and logical
properties mirror the whole row for Arabic without a single coordinate being
recomputed. SVG is kept only where it earns its place -- the donut, which
genuinely needs arcs, and the sparkline.

Colour comes from CSS custom properties rather than hex literals here, which
is what lets one chart serve both the light and the dark theme. The old hex
values were chosen against white; on the dark theme the bars and their
labels were drawn in near-black on near-black, and the whole analytics
section rendered as an empty rectangle.

Form follows the job. Comparing magnitudes is a ranked bar, and the bar that
matters most is the one the eye should land on first -- so the largest is
drawn in the accent colour and the rest in one quiet tone. That is emphasis,
not decoration: it encodes which row is the answer. The part-to-whole view
is a donut, capped at six slices with the tail folded into "Other", because
past six the slices become slivers nobody can read or compare.

Every bar and every slice also carries its name and its figure as text. That
is not decoration either: it is what a screen reader gets, what a printer
gets, and what makes the chart readable when two colours are hard to tell
apart.
"""

from __future__ import annotations

from html import escape

#: Slice colours, in fixed order, for the donut -- the only chart here that
#: asks anyone to tell colours apart. Light and dark are separate selections
#: rather than one lightened or darkened, and both were checked for
#: colour-vision separation and for contrast against their own surface
#: before being used. The CSS variables are defined in app.css.
SLICE_SLOTS = 6

#: The tail beyond this many slices is folded into one "Other".
MAX_SLICES = 6

def _clip(text: str, limit: int) -> str:
    """Cut a label to fit its column, with an ellipsis so the cut is visible.

    >>> _clip("BMW", 10)
    'BMW'
    >>> _clip("Timing chain guide wear", 10)
    'Timing ch…'
    """
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _fmt(value: float) -> str:
    """A number as a person would write it.

    >>> _fmt(1), _fmt(1234), _fmt(1234567)
    ('1', '1,234', '1,234,567')
    >>> _fmt(12.5)
    '12.5'
    """
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def meter_list(
    rows: list[tuple[str, float]],
    *,
    title: str = "",
    unit: str = "",
    empty: str = "Nothing to show yet.",
    label_width: int = 150,
) -> str:
    """Named rows, each with a bar and its figure. Bars share one baseline.

    The form for "compare these magnitudes": bars starting from the same edge
    compare far more exactly than segments laid end to end, and the name sits
    beside its own bar rather than in a legend the eye has to cross-reference.

    The largest row is drawn in the accent colour and the rest in one quiet
    tone. That is the question most of these charts are asked -- which make
    do we see most of, which fault comes back -- so the answer is the thing
    the eye lands on, and the rest is context. A ramp of five tints was tried
    first and failed for a plain reason: its pale end was lighter than the
    track behind it, so every small bar was invisible.

    There is no ``rtl`` argument and no coordinate arithmetic. The row is a
    flex line, so Arabic mirrors the whole thing -- name to the right, bar
    growing leftward, figure to the left -- with nothing recomputed. The SVG
    version needed every coordinate mirrored by hand and said so in a
    docstring that called it a source of bugs.

    ``label_width`` is in pixels and buys room for long names at the cost of
    bar length. Names wrap rather than being cut, because an ellipsis loses
    the part of a fault description that says which fault it was.

    >>> html = meter_list([("BMW", 59), ("Audi", 4)], title="Cars by make")
    >>> "BMW" in html and "59" in html
    True
    >>> "is-top" in html          # the largest row is marked
    True
    >>> "Nothing to show yet" in meter_list([])
    True
    >>> "aria-hidden" in meter_list([("BMW", 1)])   # the bar repeats the figure
    True
    """
    if not rows:
        return f'<p class="hint">{escape(empty)}</p>'

    highest = max(value for _, value in rows) or 1
    parts = [
        f'<ul class="meter" style="--meter-label:{int(label_width)}px" '
        f'role="list" aria-label="{escape(title)}">'
    ]
    for label, value in rows:
        # A bar for a real but tiny value still has to be visible, or the row
        # reads as a zero. 1.5% is about two pixels at this width.
        share = (value / highest) * 100 if highest else 0
        width = max(share, 1.5) if value else 0
        top = " is-top" if value == highest and value else ""
        figure = f"{_fmt(value)}{' ' + unit if unit else ''}"
        parts.append(
            f'<li class="meter-row{top}">'
            f'<span class="meter-name">{escape(str(label))}</span>'
            # The track and bar say nothing a screen reader needs: the name
            # and the figure either side of them already carry the row.
            f'<span class="meter-track" aria-hidden="true">'
            f'<span class="meter-bar" style="width:{width:.1f}%"></span></span>'
            f'<span class="meter-figure">{escape(figure)}</span>'
            f"</li>"
        )
    parts.append("</ul>")
    return "".join(parts)


def donut(
    rows: list[tuple[str, float]],
    *,
    title: str = "",
    centre_label: str = "",
    empty: str = "Nothing to show yet.",
    other_label: str = "Other",
) -> str:
    """One whole, split into parts, with a legend naming every one.

    Capped at six slices with the tail folded into a single "Other". Past
    six the slices are slivers: too thin to compare, too thin to label, and
    the reader ends up reading the legend instead -- at which point the
    circle was decoration.

    The legend is not optional and it carries each part's name, figure and
    share. Several of the slice colours do not reach 3:1 against the card
    behind them, and the rule for that is to make sure nothing depends on
    telling the colours apart.

    >>> html = donut([("BMW", 70), ("Audi", 30)], centre_label="100")
    >>> "BMW" in html and "70.0%" in html
    True
    >>> "Nothing to show yet" in donut([])
    True
    >>> many = donut([(str(n), 1) for n in range(12)])
    >>> many.count("donut-legend-row") <= 6
    True
    """
    rows = [(label, value) for label, value in rows if value > 0]
    if not rows:
        return f'<p class="hint">{escape(empty)}</p>'

    rows = sorted(rows, key=lambda r: r[1], reverse=True)
    if len(rows) > MAX_SLICES:
        head = rows[: MAX_SLICES - 1]
        tail_total = sum(value for _, value in rows[MAX_SLICES - 1 :])
        rows = [*head, (other_label, tail_total)]

    total = sum(value for _, value in rows)
    if total <= 0:
        return f'<p class="hint">{escape(empty)}</p>'

    # A ring rather than a disc, drawn with one circle per slice using the
    # dash array: no arc-path arithmetic, and no seams between segments.
    size, stroke = 120, 26
    radius = (size - stroke) / 2
    circumference = 2 * 3.141592653589793 * radius

    svg = [
        f'<svg class="donut" viewBox="0 0 {size} {size}" role="img" '
        f'aria-label="{escape(title)}">'
    ]
    offset = 0.0
    for index, (_, value) in enumerate(rows):
        share = value / total
        length = share * circumference
        svg.append(
            f'<circle cx="{size/2}" cy="{size/2}" r="{radius:.2f}" fill="none" '
            f'stroke="var(--slice-{index + 1})" stroke-width="{stroke}" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {size/2} {size/2})"/>'
        )
        offset += length
    if centre_label:
        svg.append(
            f'<text x="{size/2}" y="{size/2}" class="donut-centre" '
            f'text-anchor="middle" dominant-baseline="central">'
            f"{escape(centre_label)}</text>"
        )
    svg.append("</svg>")

    legend = ['<ul class="donut-legend" role="list">']
    for index, (label, value) in enumerate(rows):
        share = value / total * 100
        legend.append(
            f'<li class="donut-legend-row">'
            f'<span class="donut-swatch" style="background:var(--slice-{index + 1})"'
            f' aria-hidden="true"></span>'
            f'<span class="donut-name">{escape(str(label))}</span>'
            f'<span class="donut-figure">{escape(_fmt(value))}</span>'
            f'<span class="donut-share">{share:.1f}%</span>'
            f"</li>"
        )
    legend.append("</ul>")

    return f'<div class="donut-wrap">{"".join(svg)}{"".join(legend)}</div>'


def trend(
    points: list[tuple[str, float]],
    *,
    title: str = "",
    unit: str = "",
    empty: str = "Not enough history yet.",
) -> str:
    """One quantity over time, as a line with a soft fill under it.

    Only the last point is labelled. A number on every point is chaos and
    goes unread; the figure that matters on a trend is where it stands now,
    and the axis carries the rest.

    >>> svg = trend([("2026-01", 100.0), ("2026-02", 180.0)], title="Owed")
    >>> "polyline" in svg
    True
    >>> "Not enough history" in trend([("2026-01", 5.0)])
    True
    """
    if len(points) < 2:
        return f'<p class="hint">{escape(empty)}</p>'

    width, height = 560, 170
    pad_left, pad_right, pad_top, pad_bottom = 8, 104, 14, 26
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    values = [value for _, value in points]
    highest = max(values) or 1
    lowest = min(min(values), 0)
    span = (highest - lowest) or 1

    def x_at(i: int) -> float:
        return pad_left + (i / (len(points) - 1)) * plot_w

    def y_at(v: float) -> float:
        return pad_top + plot_h - ((v - lowest) / span) * plot_h

    line = " ".join(f"{x_at(i):.1f},{y_at(v):.1f}" for i, v in enumerate(values))
    area = (
        f"{pad_left:.1f},{pad_top + plot_h:.1f} {line} "
        f"{x_at(len(points) - 1):.1f},{pad_top + plot_h:.1f}"
    )

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'direction="ltr" role="img" aria-label="{escape(title)}" class="chart">'
    ]
    # Two hairlines, solid: a dashed grid reads as a threshold when it is
    # only a grid.
    for fraction in (0.0, 0.5, 1.0):
        y = pad_top + plot_h * fraction
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{pad_left + plot_w}" '
            f'y2="{y:.1f}" stroke="var(--rule)" stroke-width="1"/>'
        )
    parts.append(f'<polygon points="{area}" fill="var(--chart-fill)" opacity="0.75"/>')
    parts.append(
        f'<polyline points="{line}" fill="none" stroke="var(--chart-line)" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    last_x, last_y = x_at(len(points) - 1), y_at(values[-1])
    parts.append(
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="var(--chart-line)" '
        f'stroke="var(--surface)" stroke-width="2"/>'
        f'<text x="{last_x + 9:.1f}" y="{last_y + 4:.1f}" font-size="12.5" '
        f'fill="var(--ink)" style="font-variant-numeric:tabular-nums">'
        f'{escape(_fmt(values[-1]))}{escape(" " + unit if unit else "")}</text>'
    )

    # First and last period only. Every label would collide at this width.
    parts.append(
        f'<text x="{pad_left}" y="{height - 6}" font-size="11.5" fill="var(--ink-faint)">'
        f'{escape(points[0][0])}</text>'
        f'<text x="{pad_left + plot_w}" y="{height - 6}" font-size="11.5" '
        f'fill="var(--ink-faint)" text-anchor="end">{escape(points[-1][0])}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def sparkline(points: list[tuple[float, float]], *, label: str = "") -> str:
    """A small shape for a series of readings over time.

    Deliberately not a real chart: no axes, no gridlines, no numbers along
    the bottom. The only question it answers is "what shape is this" -- flat,
    climbing, or sawtoothing -- and the figures either side of it in the page
    give the actual values. Anything more would be furniture.

    Scaled from zero rather than from the lowest reading. Scaled from the
    low, a wobble of two megabytes over a day looks like a cliff, which is
    how a chart tells a lie without a single wrong number in it.
    """
    values = [value for _, value in points]
    if not values:
        return ""

    top = max(values) or 1.0
    bars = []
    for value in values:
        height = max(2.0, 100.0 * value / top)
        bars.append(f'<span class="spark-bar" style="--h: {height:.1f}%"></span>')

    return (
        f'<div class="spark" role="img" aria-label="{escape(label)}">'
        + "".join(bars)
        + "</div>"
    )
