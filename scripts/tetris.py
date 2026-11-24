#!/usr/bin/env python3
"""Génère un SVG animé façon Tetris à partir du graphe de contributions GitHub.

- Données : API GraphQL GitHub (12 derniers mois, comme le graphe du profil).
- Les cases actives sont découpées en pièces de 4 cases max (tétrominos),
  qui tombent case par case avec des couleurs Tetris, puis prennent
  leur couleur verte GitHub en se posant.
- Aucune dépendance externe (bibliothèque standard uniquement).

Usage :
  GITHUB_TOKEN=... python scripts/tetris.py -u anthonin-tech -o assets/tetris.svg
  python scripts/tetris.py --sample -o /tmp/test.svg   # données factices
"""
import argparse
import datetime as dt
import json
import os
import random
import urllib.request

# --- Apparence ---------------------------------------------------------------
CELL, GAP = 11, 3
STEP = CELL + GAP
LEFT, TOP = 34, 26          # place pour les jours et les mois
BOTTOM, RIGHT = 22, 10
BG = "#0d1117"
EMPTY = "#161b22"
TEXT = "#8b949e"
LEVELS = {  # couleurs GitHub (thème sombre)
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}
TETRIS = ["#00f0f0", "#f0f000", "#a000f0", "#00f000", "#f00000", "#0000f0", "#f0a000"]

# --- Timing (secondes) -------------------------------------------------------
FALL = 0.55       # durée de chute d'une pièce
HOLD = 4.0        # pause sur le graphe complet
FLASH = 0.9       # "ligne complète" : clignote puis disparaît
PAUSE = 0.6       # vide avant de recommencer

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "tetris-contrib"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"Erreur GraphQL : {body['errors']}")
    cal = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["weeks"], cal["totalContributions"]


def sample():
    """Données factices sur 53 semaines, alignées comme celles de GitHub."""
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # dimanche
    weeks, total, d = [], 0, start
    levels = [None, *LEVELS]
    while d <= today:
        week = []
        for _ in range(7):
            if d > today:
                break
            lvl = rnd.choices(levels, [55, 20, 12, 8, 5])[0]
            n = 0 if lvl is None else levels.index(lvl) * 2
            total += n
            week.append({"date": d.isoformat(), "weekday": (d.weekday() + 1) % 7,
                         "contributionCount": n, "contributionLevel": lvl or "NONE"})
            d += dt.timedelta(days=1)
        weeks.append({"contributionDays": week})
    return weeks, total


def make_pieces(active):
    """Découpe les cases actives {(semaine, jour): couleur} en pièces connexes de ≤ 4 cases."""
    left = set(active)
    pieces = []
    # parcours colonne par colonne, de bas en haut, comme un empilement Tetris
    for start in sorted(active, key=lambda c: (c[0], -c[1])):
        if start not in left:
            continue
        piece, frontier = [start], [start]
        left.discard(start)
        while frontier and len(piece) < 4:
            w, d = frontier.pop(0)
            for nb in ((w, d - 1), (w + 1, d), (w, d + 1), (w - 1, d)):
                if nb in left and len(piece) < 4:
                    left.discard(nb)
                    piece.append(nb)
                    frontier.append(nb)
        pieces.append(piece)
    return pieces


def build_svg(weeks, total, login):
    n_weeks = len(weeks)
    width = LEFT + n_weeks * STEP + RIGHT
    height = TOP + 7 * STEP + BOTTOM
    grid_h = 7 * STEP

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
           f'<rect width="100%" height="100%" rx="6" fill="{BG}"/>']

    # libellés des mois (au premier dimanche du mois)
    last_month = None
    for i, wk in enumerate(weeks):
        first = dt.date.fromisoformat(wk["contributionDays"][0]["date"])
        if first.month != last_month and first.day <= 7 and i < n_weeks - 2:
            out.append(f'<text x="{LEFT + i * STEP}" y="{TOP - 9}" font-size="10" fill="{TEXT}">'
                       f'{first.strftime("%b")}</text>')
        last_month = first.month if first.day <= 7 else last_month
    for d, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="4" y="{TOP + d * STEP + 9}" font-size="10" fill="{TEXT}">{name}</text>')
    out.append(f'<text x="{width - RIGHT}" y="{height - 7}" font-size="10" fill="{TEXT}" '
               f'text-anchor="end">{total} contributions · @{login}</text>')

    # grille vide + cases actives
    active = {}
    for w, wk in enumerate(weeks):
        for day in wk["contributionDays"]:
            x, y = LEFT + w * STEP, TOP + day["weekday"] * STEP
            out.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{EMPTY}"/>')
            if day["contributionLevel"] in LEVELS:
                active[(w, day["weekday"])] = LEVELS[day["contributionLevel"]]

    pieces = make_pieces(active)
    n = max(len(pieces), 1)
    build = min(max(n * 0.11, 8.0), 22.0)       # durée de construction totale
    interval = (build - FALL) / max(n - 1, 1)
    total_t = build + HOLD + FLASH + PAUSE
    pct = lambda t: f"{100 * t / total_t:.3f}%"
    t_flash = build + HOLD

    css = [
        "@media (prefers-reduced-motion: reduce){.p{animation:none!important}}",
        f".p{{animation-duration:{total_t:.2f}s;animation-iteration-count:infinite;animation-fill-mode:both}}",
    ]
    # clignotement final ("ligne complète") commun à toutes les pièces
    css.append(f"@keyframes flash{{0%,{pct(t_flash)}{{opacity:1}}"
               f"{pct(t_flash + FLASH * .25)}{{opacity:.2}}{pct(t_flash + FLASH * .5)}{{opacity:1}}"
               f"{pct(t_flash + FLASH)},100%{{opacity:0}}}}")

    out.append(f'<clipPath id="g"><rect x="{LEFT - 2}" y="{TOP - 2}" '
               f'width="{n_weeks * STEP + 2}" height="{grid_h + 2}"/></clipPath>')
    body = ['<g clip-path="url(#g)"><g style="animation:flash ' f'{total_t:.2f}s infinite both">']

    for i, piece in enumerate(pieces):
        t0 = i * interval
        t1 = t0 + FALL
        top_row = min(d for _, d in piece)
        drop_cells = top_row + 4                      # part du dessus de la grille
        dist = drop_cells * STEP
        k = f"k{i}", f"o{i}"
        css.append(
            f"@keyframes {k[0]}{{0%,{pct(t0)}{{transform:translateY(-{dist}px);opacity:0}}"
            f"{pct(t0 + 0.001)}{{transform:translateY(-{dist}px);opacity:1;"
            f"animation-timing-function:steps({drop_cells},end)}}"
            f"{pct(t1)},100%{{transform:translateY(0);opacity:1}}}}")
        css.append(f"@keyframes {k[1]}{{0%,{pct(t1)}{{opacity:1}}{pct(t1 + 0.25)},100%{{opacity:0}}}}")
        tet = TETRIS[i % len(TETRIS)]
        green = "".join(f'<rect x="{LEFT + w * STEP}" y="{TOP + d * STEP}" width="{CELL}" '
                        f'height="{CELL}" rx="2" fill="{active[(w, d)]}"/>' for w, d in piece)
        color = "".join(f'<rect x="{LEFT + w * STEP}" y="{TOP + d * STEP}" width="{CELL}" '
                        f'height="{CELL}" rx="2" fill="{tet}"/>' for w, d in piece)
        body.append(f'<g class="p" style="animation-name:{k[0]}">{green}'
                    f'<g class="p" style="animation-name:{k[1]}">{color}</g></g>')
    body.append("</g></g>")

    out.insert(2, "<style>" + "".join(css) + "</style>")
    out.extend(body)
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "octocat"))
    ap.add_argument("-o", "--out", default="assets/tetris.svg")
    ap.add_argument("--sample", action="store_true", help="données factices (test local)")
    a = ap.parse_args()
    if a.sample:
        weeks, total = sample()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN manquant")
        weeks, total = fetch(a.user, token)
    svg = build_svg(weeks, total, a.user)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{a.out} : {len(svg) // 1024} Ko, {total} contributions")


if __name__ == "__main__":
    main()
