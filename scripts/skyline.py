"""Draw profile/skyline.svg: a year of contributions as an isometric skyline.

This is a static SVG port of the Contribution Skyline React component (its 3D
view). GitHub strips scripts and canvas from READMEs, so the grid, levels,
streaks, camera, and painter's order are computed here, and the bars are drawn
as SVG polygons. Bars rise in a wave from the back corner with SMIL. Every
element rests in its final state, so a viewer without SMIL sees the full chart.

Standard library only. generate_stats.py calls draw().
"""
import datetime as dt
import math

# GitHub palette from the component, lightest activity to heaviest.
LEVELS_LIGHT = ["#c6e48b", "#7bc96f", "#239a3b", "#196127"]
LEVELS_DARK = ["#0e4429", "#006d32", "#26a641", "#39d353"]
EMPTY_LIGHT = "#eeefef"   # GitHub light background mixed 7.5% toward its text color
EMPTY_DARK = "#22262c"    # GitHub dark background mixed 11% toward its text color

YAW = math.pi / 4
ELEV = math.radians(34)
CS, SN = math.cos(YAW), math.sin(YAW)
SE, CE = math.sin(ELEV), math.cos(ELEV)

WIDTH = 900               # viewBox width; the README scales it to fit
PAD = 22                  # card padding
HEADER = 44
FOOTER = 40
CHAR = 0.6                # monospace advance in em


def project(x, y, z):
    return x * CS - y * SN, (x * SN + y * CS) * SE - z * CE


def bar_height(count, peak):
    return 0.4 + (count / peak) ** 0.85 * 7.2 if count > 0 and peak > 0 else 0.2


def level_of(count, busy):
    if count <= 0:
        return 0
    if busy <= 0:
        return 4
    return 1 + min(3, int(count / busy * 4))


def build_grid(days, end, week_start=0):
    """Columns are weeks, rows are weekdays. Ends on `end`, starts on the week holding end - 364 days."""
    counts = {}
    for d in days:
        if d["count"] > 0:
            counts[d["date"]] = counts.get(d["date"], 0) + d["count"]
    start = end - dt.timedelta(days=364)
    sunday0 = (start.weekday() + 1) % 7
    start -= dt.timedelta(days=(sunday0 - week_start) % 7)
    cells = []
    day = start
    i = 0
    while day <= end:
        key = day.isoformat()
        cells.append({"date": day, "count": counts.get(key, 0), "week": i // 7, "day": i % 7})
        day += dt.timedelta(days=1)
        i += 1
    nz = sorted(c["count"] for c in cells if c["count"] > 0)
    busy = nz[int(0.95 * (len(nz) - 1))] if nz else 0
    for c in cells:
        c["level"] = level_of(c["count"], busy)
    weeks = cells[-1]["week"] + 1 if cells else 0
    return cells, weeks, (nz[-1] if nz else 0)


def compute_stats(cells):
    total = best = run = 0
    best_date = run_start = None
    longest = (0, None, None)
    for c in cells:
        total += c["count"]
        if c["count"] > best:
            best, best_date = c["count"], c["date"]
        if c["count"] > 0:
            if run == 0:
                run_start = c["date"]
            run += 1
            if run > longest[0]:
                longest = (run, run_start, c["date"])
        else:
            run = 0
    j = len(cells) - 1
    if j >= 0 and cells[j]["count"] == 0:
        j -= 1    # today is not over yet
    end_at = j
    while j >= 0 and cells[j]["count"] > 0:
        j -= 1
    days = end_at - j
    current = (days, cells[j + 1]["date"], cells[end_at]["date"]) if days > 0 else (0, None, None)
    return {
        "total": total,
        "first": cells[0]["date"] if cells else None,
        "last": cells[-1]["date"] if cells else None,
        "busiest": (best, best_date),
        "longest": longest,
        "current": current,
    }


def month_labels(cells, weeks):
    out, prev = [], -1
    for w in range(weeks):
        idx = w * 7
        if idx >= len(cells):
            break
        m = cells[idx]["date"].month
        if m != prev:
            out.append((w, cells[idx]["date"].strftime("%b")))
        prev = m
    if len(out) > 1 and out[1][0] - out[0][0] < 3:
        out.pop(0)
    return out


def short(d):
    return f"{d:%b} {d.day}"


def long_date(d):
    return f"{d:%b} {d.day}, {d.year}"


def span(a, b, with_year=False):
    if not a or not b:
        return "none yet"
    f = long_date if with_year else short
    return f(a) if a == b else f"{f(a)} to {f(b)}"


def shade(hex_color, k):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (round(r * k), round(g * k), round(b * k))


def palette_css():
    rules = []
    for scheme, empty, levels in (("light", EMPTY_LIGHT, LEVELS_LIGHT), ("dark", EMPTY_DARK, LEVELS_DARK)):
        cols = [empty] + levels
        body = "".join(
            f".c{i}t{{fill:{c}}}.c{i}l{{fill:{shade(c, 0.84)}}}.c{i}r{{fill:{shade(c, 0.68)}}}"
            for i, c in enumerate(cols)
        )
        rules.append(body if scheme == "light" else "@media (prefers-color-scheme:dark){" + body + "}")
    return "".join(rules)


def text_w(s, size):
    return len(s) * size * CHAR


def draw(days, end, font_css):
    cells, weeks, peak = build_grid(days, end)
    stats = compute_stats(cells)
    months = month_labels(cells, weeks)

    w, off = 0.9, 0.05
    hgt = [bar_height(c["count"], peak) for c in cells]

    # Scene bounds in world units: every bar corner plus room for the month labels.
    xs, ys = [], []
    for c, h in zip(cells, hgt):
        x0, y0 = c["week"] + off, c["day"] + off
        for (x, y, z) in ((x0, y0, h), (x0 + w, y0, h), (x0, y0 + w, h), (x0 + w, y0 + w, 0), (x0, y0 + w, 0), (x0 + w, y0, 0)):
            sx, sy = project(x, y, z)
            xs.append(sx)
            ys.append(sy)
    for x in (0, weeks):
        sx, sy = project(x, 8.5, 0)
        xs.append(sx)
        ys.append(sy)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    stage_w = WIDTH - PAD * 2
    natural = (maxy - miny) / (maxx - minx) * (stage_w - 40) + 40
    stage_h = max(min(natural, stage_w * 0.72, 620), min(natural, 240))
    s = min((stage_w - 40) / (maxx - minx), (stage_h - 40) / (maxy - miny))
    ox = PAD + 20 + ((stage_w - 40) - (maxx - minx) * s) / 2 - minx * s
    oy = PAD + HEADER + 20 + ((stage_h - 40) - (maxy - miny) * s) / 2 - miny * s
    height = round(PAD + HEADER + stage_h + FOOTER + PAD)

    def pt(x, y, z):
        sx, sy = project(x, y, z)
        return f"{ox + sx * s:.1f},{oy + sy * s:.1f}"

    # Painter's order: at a 45 degree yaw, depth is x + y, so each diagonal is one depth layer.
    diagonals = {}
    for c, h in zip(cells, hgt):
        diagonals.setdefault(c["week"] + c["day"], []).append((c, h))
    layers = sorted(diagonals)
    rise = 1.4                # seconds for the wave to cross the grid
    step = 0.45               # seconds for one layer to rise

    out = []
    for k in layers:
        delay = rise * k / max(1, layers[-1])
        dur = delay + step
        key = delay / dur
        polys = []
        for c, h in sorted(diagonals[k], key=lambda t: t[0]["week"]):
            x0, y0 = c["week"] + off, c["day"] + off
            x1, y1 = x0 + w, y0 + w
            lv = c["level"]
            tall = h * CE * s > 0.35
            if tall:
                polys.append(f'<polygon class="c{lv}l" points="{pt(x0, y1, 0)} {pt(x1, y1, 0)} {pt(x1, y1, h)} {pt(x0, y1, h)}"/>')
                polys.append(f'<polygon class="c{lv}r" points="{pt(x1, y0, 0)} {pt(x1, y1, 0)} {pt(x1, y1, h)} {pt(x1, y0, h)}"/>')
            polys.append(f'<polygon class="c{lv}t" points="{pt(x0, y0, h)} {pt(x1, y0, h)} {pt(x1, y1, h)} {pt(x0, y1, h)}"/>')
        out.append(
            f'<g><animate attributeName="opacity" values="0;0;1" keyTimes="0;{key:.3f};1" dur="{dur:.2f}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 14;0 14;0 0" '
            f'keyTimes="0;{key:.3f};1" dur="{dur:.2f}s" fill="freeze"/>{"".join(polys)}</g>'
        )

    # Month labels along the front edge, skipping any that would collide.
    labels, edge = [], -1e9
    for wk, name in months:
        sx, sy = project(wk + 0.5, 7.3, 0)
        x, y = ox + sx * s, oy + sy * s + 14
        if x < edge or x + text_w(name, 11) > WIDTH - PAD:
            continue
        labels.append(f'<text class="m" x="{x:.1f}" y="{y:.1f}" font-size="11">{name}</text>')
        edge = x + text_w(name, 11) + 10

    def unit(n, one="contribution"):
        return one if n == 1 else one + "s"

    def stat(x, y, label, value, unit_text, sub, anchor):
        # anchor "end" right-aligns the block at x; "start" left-aligns it.
        vx = x if anchor == "start" else x - text_w(unit_text, 13) - 8
        ux = vx + text_w(value, 30) + 8 if anchor == "start" else x
        return (
            f'<text class="m" x="{x}" y="{y}" font-size="12" text-anchor="{anchor}">{label}</text>'
            f'<text class="a" x="{vx:.1f}" y="{y + 34}" font-size="30" text-anchor="{anchor}">{value}</text>'
            f'<text class="f" x="{ux:.1f}" y="{y + 34}" font-size="13" text-anchor="{anchor}">{unit_text}</text>'
            f'<text class="m" x="{x}" y="{y + 52}" font-size="11" text-anchor="{anchor}">{sub}</text>'
        )

    total = stats["total"]
    b_count, b_date = stats["busiest"]
    l_days, l_a, l_b = stats["longest"]
    c_days, c_a, c_b = stats["current"]
    right = WIDTH - PAD - 12
    left = PAD + 12
    top = PAD + HEADER + 14
    gap = 84
    bottom = PAD + HEADER + stage_h - 2 * gap + 10
    corners = (
        stat(right, top, "1 year total", f"{total:,}", unit(total), span(stats["first"], stats["last"], True), "end")
        + stat(right, top + gap, "Busiest day", f"{b_count:,}", unit(b_count), short(b_date) if b_date else "none yet", "end")
        + stat(left, bottom, "Longest streak", f"{l_days:,}", "day" if l_days == 1 else "days", span(l_a, l_b), "start")
        + stat(left, bottom + gap, "Current streak", f"{c_days:,}", "day" if c_days == 1 else "days", span(c_a, c_b), "start")
    )

    # Legend: Less [5 swatches] More, bottom right.
    ly = height - PAD - 14
    lx = WIDTH - PAD - 12 - text_w("More", 12)
    legend = [f'<text class="m" x="{lx:.1f}" y="{ly + 10}" font-size="12">More</text>']
    for i in range(4, -1, -1):
        lx -= 15
        legend.append(f'<rect class="c{i}t" x="{lx:.1f}" y="{ly}" width="11" height="11" rx="2"/>')
    lx -= 6 + text_w("Less", 12)
    legend.append(f'<text class="m" x="{lx:.1f}" y="{ly + 10}" font-size="12">Less</text>')

    fade = ('<animate attributeName="opacity" values="0;0;1" keyTimes="0;0.6;1" dur="2.4s" fill="freeze"/>')
    mono = "SMono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
    css = (
        font_css
        + f"text{{font-family:{mono}}}"
        + ".f{fill:#1f2328}.m{fill:#57606a}.a{fill:#196127;font-weight:700}.bd{fill:none;stroke:#d0d7de}"
        + "@media (prefers-color-scheme:dark){.f{fill:#e6edf3}.m{fill:#8b949e}.a{fill:#39d353}.bd{stroke:#30363d}}"
        + palette_css()
    )
    title = (f'<text class="f" x="{PAD + 12}" y="{PAD + 26}" font-size="15">'
             f'<tspan class="a" font-size="15">{total:,}</tspan> {unit(total)} in the last year</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'role="img" aria-label="{total:,} contributions in the last year, shown as a 3D skyline">'
        f"<style>{css}</style>"
        f'<rect class="bd" x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="12"/>'
        f"{title}{''.join(out)}<g>{fade}{''.join(labels)}{corners}</g>"
        f'<text class="m" x="{PAD + 12}" y="{ly + 10}" font-size="12">Updated daily from the GitHub API</text>'
        f"{''.join(legend)}</svg>\n"
    )
