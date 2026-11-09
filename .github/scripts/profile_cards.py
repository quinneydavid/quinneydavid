#!/usr/bin/env python3
"""Draw the profile's top-languages card and 30-day activity graph as SVGs (light + dark).

Runs in the profile repo's GitHub Action with the built-in GITHUB_TOKEN; no external services.
Usage: GH_USER=<login> GITHUB_TOKEN=<token> python3 profile_cards.py <out_dir>
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape

USER = os.environ["GH_USER"]
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"

THEMES = {
    "": {"text": "#1f2328", "muted": "#59636e", "grid": "#d1d9e0", "line": "#1a7f37", "area": "#2da44e"},
    "-dark": {"text": "#e6edf3", "muted": "#9198a1", "grid": "#3d444d", "line": "#3fb950", "area": "#2ea043"},
}
LANG_COLORS = {
    "Python": "#3572A5", "Go": "#00ADD8", "PowerShell": "#5391FE", "Shell": "#89e051", "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a", "HTML": "#e34c26", "CSS": "#663399", "Ruby": "#701516", "HCL": "#844FBA",
    "Dockerfile": "#384d54", "Jinja": "#a52a22", "Makefile": "#427819", "Smarty": "#f0c040", "Java": "#b07219",
    "C#": "#178600", "Rust": "#dea584", "Vue": "#41b883", "Batchfile": "#C1F12E", "Jupyter Notebook": "#DA5B0B",
}
FONT = "font-family=\"-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif\""


def api(url, query=None):
    data = json.dumps(query).encode() if query else None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-cards"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def languages():
    totals, page = {}, 1
    while True:
        repos = api(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}")
        for r in repos:
            if r["fork"] or r["archived"] or r["name"].lower() == USER.lower():
                continue
            for lang, size in api(r["languages_url"]).items():
                totals[lang] = totals.get(lang, 0) + size
        if len(repos) < 100:
            break
        page += 1
    total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    return [(lang, size * 100 / total) for lang, size in top]


def contributions(days=30):
    q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
           weeks{contributionDays{date contributionCount}}}}}}"""
    res = api("https://api.github.com/graphql", {"query": q, "variables": {"login": USER}})
    if "errors" in res:
        raise SystemExit(f"GraphQL error: {res['errors']}")
    weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    cal = [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
    return cal[-days:]


def lang_svg(langs, t):
    w, h = 340, 52 + 22 * ((len(langs) + 1) // 2)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>',
           f'<text x="0" y="16" font-size="14" font-weight="600" fill="{t["text"]}">Most used languages</text>',
           '<clipPath id="bar"><rect x="0" y="28" width="340" height="8" rx="4"/></clipPath><g clip-path="url(#bar)">']
    x = 0.0
    for lang, pct in langs:
        bw = 340 * pct / 100
        out.append(f'<rect x="{x:.2f}" y="28" width="{bw + 0.5:.2f}" height="8" fill="{LANG_COLORS.get(lang, "#8b949e")}"/>')
        x += bw
    out.append("</g>")
    for i, (lang, pct) in enumerate(langs):
        cx, cy = (0 if i % 2 == 0 else 175), 58 + 22 * (i // 2)
        out.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{LANG_COLORS.get(lang, "#8b949e")}"/>'
                   f'<text x="{cx + 16}" y="{cy}" font-size="12" fill="{t["text"]}">{escape(lang)} '
                   f'<tspan fill="{t["muted"]}">{pct:.1f}%</tspan></text>')
    out.append("</svg>")
    return "\n".join(out)


def graph_svg(days, t):
    days = days or [(dt.date.today().isoformat(), 0)]
    w, h, l, r, top, bottom = 800, 220, 36, 12, 34, 28
    pw, ph = w - l - r, h - top - bottom
    peak = max([c for _, c in days] + [1])
    step = max(1, -(-peak // 4))           # gridline step, ceil(peak / 4)
    ymax = step * 4
    xs = [l + pw * i / max(1, len(days) - 1) for i in range(len(days))]
    ys = [top + ph - ph * c / ymax for _, c in days]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    total = sum(c for _, c in days)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>',
           f'<text x="{l}" y="18" font-size="14" font-weight="600" fill="{t["text"]}">Contributions, last 30 days'
           f'<tspan font-weight="400" fill="{t["muted"]}">  ·  {total} total</tspan></text>']
    for i in range(5):
        y = top + ph - ph * i / 4
        out.append(f'<line x1="{l}" x2="{w - r}" y1="{y:.1f}" y2="{y:.1f}" stroke="{t["grid"]}" stroke-width="1"/>'
                   f'<text x="{l - 8}" y="{y + 4:.1f}" font-size="10" text-anchor="end" fill="{t["muted"]}">{step * i}</text>')
    out.append(f'<polygon points="{xs[0]:.1f},{top + ph} {pts} {xs[-1]:.1f},{top + ph}" fill="{t["area"]}" fill-opacity="0.18"/>'
               f'<polyline points="{pts}" fill="none" stroke="{t["line"]}" stroke-width="2" stroke-linejoin="round"/>')
    for i, ((date, c), x, y) in enumerate(zip(days, xs, ys)):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{t["line"]}"><title>{date}: {c}</title></circle>')
        if i % 5 == 0 or i == len(days) - 1:
            label = dt.date.fromisoformat(date).strftime("%d %b")
            anchor = "end" if i == len(days) - 1 else "middle"
            out.append(f'<text x="{x:.1f}" y="{h - 8}" font-size="10" text-anchor="{anchor}" fill="{t["muted"]}">{label}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    langs, days = languages(), contributions()
    for suffix, t in THEMES.items():
        with open(f"{OUT}/top-langs{suffix}.svg", "w") as f:
            f.write(lang_svg(langs, t))
        with open(f"{OUT}/activity-graph{suffix}.svg", "w") as f:
            f.write(graph_svg(days, t))
    print(f"{USER}: {len(langs)} languages, {sum(c for _, c in days)} contributions in last {len(days)} days")


if __name__ == "__main__":
    main()
