#!/usr/bin/env python3
"""Draw profile/hero.svg and write profile/stars.json from the GitHub GraphQL API.

The scheduled workflow runs this. It uses the standard library only.

    GITHUB_TOKEN=... GH_LOGIN=moon-drakon python scripts/generate_stats.py

hero.svg: contributions in the last year, active days, best week, and a weekly
sparkline. The window is pinned to whole UTC days so two runs on the same day
produce the same file.

stars.json: a shields.io endpoint badge with the number on the profile's Stars
tab (repositories this account has starred).
"""
import base64
import datetime as dt
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "profile")
FONTS = os.path.join(HERE, "fonts")

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    starredRepositories { totalCount }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

W, H = 620, 168
PAD_X = 6
SPARK_TOP, SPARK_BOTTOM = 112, 156


def fetch(login, token):
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)
    variables = {
        "login": login,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    }
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def summarize(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]]
    days = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    return {
        "total": cal["totalContributions"],
        "active": sum(1 for c in days if c > 0),
        "best_week": max(weeks) if weeks else 0,
        "weeks": weeks,
        "starred": user["starredRepositories"]["totalCount"],
    }


def font_face(family, filename, weight):
    path = os.path.join(FONTS, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return (f"@font-face{{font-family:{family};font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


def spark_points(weeks):
    peak = max(weeks) if weeks and max(weeks) > 0 else 1
    n = max(len(weeks) - 1, 1)
    span = W - PAD_X * 2
    pts = []
    for i, v in enumerate(weeks):
        x = PAD_X + span * i / n
        y = SPARK_BOTTOM - (SPARK_BOTTOM - SPARK_TOP) * (v / peak)
        pts.append((round(x, 1), round(y, 1)))
    return pts


def draw(s):
    pts = spark_points(s["weeks"]) or [(PAD_X, SPARK_BOTTOM), (W - PAD_X, SPARK_BOTTOM)]
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"M{pts[0][0]},{SPARK_BOTTOM} L" + " L".join(f"{x},{y}" for x, y in pts) + f" L{pts[-1][0]},{SPARK_BOTTOM} Z"
    length = sum(((pts[i][0] - pts[i - 1][0]) ** 2 + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5
                 for i in range(1, len(pts)))
    length = round(length + 1, 1)
    end_x, end_y = pts[-1]
    mono = "SMono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

    style = (
        font_face("SMono", "mono-label.woff2", 400)
        + font_face("SMono", "mono-number.woff2", 700)
        + f".n{{font-family:{mono};font-weight:700;fill:#1E1B4B}}"
        f".l{{font-family:{mono};font-weight:400;fill:#57606A}}"
        ".ln{stroke:#7C3AED}.ar{fill:url(#g)}.dt{fill:#7C3AED}.bs{stroke:#D0D7DE}"
        "@media (prefers-color-scheme:dark){"
        ".n{fill:#EDE9FE}.l{fill:#8B949E}.ln{stroke:#A78BFA}.dt{fill:#C4B5FD}.bs{stroke:#30363D}}"
    )
    # Every element rests in its final state. The animations start at 0s and hold
    # the start value until their delay passes, so a viewer that skips SMIL still
    # sees the finished card instead of a blank one.
    def fade(delay, dur=0.6):
        k = delay / (delay + dur)
        return (f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{k:.3f};1" '
                f'dur="{delay + dur:.2f}s" fill="freeze"/>')

    k_line = 0.6 / 2.0
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{s['total']:,} contributions in the last year, {s['active']} active days, best week {s['best_week']}">
<style>{style}</style>
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7C3AED" stop-opacity="0.45"/><stop offset="1" stop-color="#7C3AED" stop-opacity="0"/></linearGradient></defs>
<g>{fade(0.1)}
<text class="n" x="{PAD_X}" y="62" font-size="56">{s['total']:,}</text>
<text class="l" x="{PAD_X + 2}" y="88" font-size="13">contributions in the last year</text>
</g>
<g text-anchor="end">{fade(0.4)}
<text class="n" x="{W - PAD_X}" y="30" font-size="22">{s['active']:,}</text>
<text class="l" x="{W - PAD_X}" y="46" font-size="11">active days</text>
<text class="n" x="{W - PAD_X}" y="74" font-size="22">{s['best_week']:,}</text>
<text class="l" x="{W - PAD_X}" y="90" font-size="11">best week</text>
</g>
<line class="bs" x1="{PAD_X}" y1="{SPARK_BOTTOM + 0.5}" x2="{W - PAD_X}" y2="{SPARK_BOTTOM + 0.5}" stroke-width="1"/>
<path class="ar" d="{area}">{fade(1.6)}</path>
<polyline class="ln" points="{line}" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="{length}" stroke-dashoffset="0"><animate attributeName="stroke-dashoffset" values="{length};{length};0" keyTimes="0;{k_line:.3f};1" dur="2s" fill="freeze"/></polyline>
<circle class="dt" cx="{end_x}" cy="{end_y}" r="3.5">{fade(2.0)}</circle>
</svg>
"""


def main():
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN")
    if not token or not login:
        sys.exit("set GITHUB_TOKEN and GH_LOGIN")
    s = summarize(fetch(login, token))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "hero.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(draw(s))
    badge = {"schemaVersion": 1, "label": "STARS", "message": str(s["starred"])}
    with open(os.path.join(OUT, "stars.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(badge, f)
        f.write("\n")
    print(f"total={s['total']} active={s['active']} best_week={s['best_week']} starred={s['starred']}")


if __name__ == "__main__":
    main()
