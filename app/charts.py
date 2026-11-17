"""Charts, drawn as SVG on the server.

No charting library and no JavaScript. Three reasons, in order of how much
they matter here: the page prints as it looks, a workshop PC with a blocked
or slow network still draws its own dashboard, and the project has no build
step to add one to.

Form follows the job the data is doing, and every chart in this file is doing
one of two jobs: comparing magnitudes, or showing one quantity over time.
Neither is about identity, so none of this uses a palette of different hues.
One hue, more-is-darker, which is the form that is hardest to misread -- and
it sidesteps the question of whether eight colours can be told apart by
someone who sees colour differently, by not asking anyone to tell colours
apart at all.

Every bar also carries its name and its figure as text beside it. That is not
decoration: the pale end of a sequential ramp does not carry 3:1 contrast
against white, so the figures are what make the chart readable rather than
merely pretty, and they are what a screen reader and a printer get.
"""

from __future__ import annotations

from html import escape

#: One hue, light to dark. Contrast against white runs 1.25 -> 8.75 and rises
#: at every step, so a bigger value is always a darker bar, at every size and
#: in grayscale.
RAMP = ("#dce7f2", "#a8c6e2", "#6b9bc9", "#3d74aa", "#1f4d7a")

INK = "#16202b"
INK_SOFT = "#4a5a6a"
INK_FAINT = "#7c8a98"
RULE = "#dce1e6"
SURFACE = "#ffffff"


def _step(value: float, highest: float) -> str:
    """Pick a ramp step by size, so the darkest bar is the biggest."""
    if highest <= 0:
        return RAMP[2]
    share = value / highest
    for index, threshold in enumerate((0.2, 0.4, 0.6, 0.8)):
        if share <= threshold:
            return RAMP[index]
    return RAMP[4]


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
    rtl: bool = False,
    label_width: int = 150,
) -> str:
    """Named rows, each with a bar and its figure. Bars share one baseline.

    The form for "compare these magnitudes": bars starting from the same edge
    compare far more exactly than segments laid end to end, and the name sits
    beside its own bar rather than in a legend the eye has to cross-reference.

    ``rtl`` mirrors the whole row -- name on the right, bar growing leftward,
    figure on the left. The coordinates are computed here rather than left to
    the `direction` property: an SVG that inherits `direction: rtl` moves its
    text anchors but not the rectangles, which put every label off the canvas
    and left a page of unlabelled bars.

    ``label_width`` buys room for long names at the cost of bar length. Names
    are cut to fit it rather than drawn over the bars, because a label that
    runs under a bar is worse than one that ends in an ellipsis.

    >>> svg = meter_list([("BMW", 59), ("Audi", 4)], title="Cars by make")
    >>> "BMW" in svg and "59" in svg
    True
    >>> mirrored = meter_list([("BMW", 59)], rtl=True)
    >>> "BMW" in mirrored and "59" in mirrored
    True
    >>> "Nothing to show yet" in meter_list([])
    True
    >>> "…" in meter_list([("A very long name indeed that will not fit", 1)])
    True
    """
    if not rows:
        return f'<p class="hint">{escape(empty)}</p>'

    highest = max(value for _, value in rows) or 1
    row_height, gap, bar_height = 30, 6, 10
    figure_width = 64
    width = 560
    track_width = width - label_width - figure_width - 16
    # Roughly the width of a character at this size. Approximate on purpose:
    # measuring text properly needs a font engine, and erring a little short
    # costs one character where erring long costs a label across a bar.
    max_chars = max(int(label_width / 6.6), 8)
    height = len(rows) * (row_height + gap)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'direction="ltr" role="img" aria-label="{escape(title)}" class="chart">'
    ]
    # Mirror the three zones rather than only the anchors. Putting the figure
    # at x=0 while the track also started there buried it under the longest
    # bar -- the one row whose number a reader most wants.
    track_x = figure_width + 16 if rtl else label_width
    for index, (label, value) in enumerate(rows):
        y = index * (row_height + gap)
        text_y = y + row_height / 2 + 4
        bar_y = y + (row_height - bar_height) / 2
        length = max((value / highest) * track_width, 2 if value else 0)
        # Growing leftward from the right end of its own track, so every bar
        # still starts from one shared edge.
        bar_x = track_x + track_width - length if rtl else track_x
        figure = f"{_fmt(value)}{' ' + unit if unit else ''}"

        parts.append(
            f'<text x="{width if rtl else 0}" y="{text_y:.0f}" font-size="12.5" '
            f'fill="{INK}" text-anchor="{"end" if rtl else "start"}">'
            f'{escape(_clip(str(label), max_chars))}</text>'
            f'<rect x="{track_x}" y="{bar_y:.1f}" width="{track_width}" '
            f'height="{bar_height}" rx="3" fill="{RULE}" opacity="0.5"/>'
            f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{length:.1f}" '
            f'height="{bar_height}" rx="3" fill="{_step(value, highest)}"/>'
            f'<text x="{0 if rtl else width}" y="{text_y:.0f}" font-size="12.5" '
            f'text-anchor="{"start" if rtl else "end"}" fill="{INK_SOFT}" '
            f'style="font-variant-numeric:tabular-nums">{escape(figure)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


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
            f'y2="{y:.1f}" stroke="{RULE}" stroke-width="1"/>'
        )
    parts.append(f'<polygon points="{area}" fill="{RAMP[0]}" opacity="0.75"/>')
    parts.append(
        f'<polyline points="{line}" fill="none" stroke="{RAMP[4]}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    last_x, last_y = x_at(len(points) - 1), y_at(values[-1])
    parts.append(
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="{RAMP[4]}" '
        f'stroke="{SURFACE}" stroke-width="2"/>'
        f'<text x="{last_x + 9:.1f}" y="{last_y + 4:.1f}" font-size="12.5" '
        f'fill="{INK}" style="font-variant-numeric:tabular-nums">'
        f'{escape(_fmt(values[-1]))}{escape(" " + unit if unit else "")}</text>'
    )

    # First and last period only. Every label would collide at this width.
    parts.append(
        f'<text x="{pad_left}" y="{height - 6}" font-size="11.5" fill="{INK_FAINT}">'
        f'{escape(points[0][0])}</text>'
        f'<text x="{pad_left + plot_w}" y="{height - 6}" font-size="11.5" '
        f'fill="{INK_FAINT}" text-anchor="end">{escape(points[-1][0])}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)
