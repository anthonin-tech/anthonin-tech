#!/usr/bin/env python3
"""Tableau de trophées GitHub en pixel-art, version maison (remplace github-profile-trophy.vercel.app).

Chaque trophée reçoit un rang (SSS, SS, S, AAA, AA, A, B, C) selon des seuils
inspirés du projet ryo-ma/github-profile-trophy. Données : API GraphQL GitHub
avec le jeton fourni par le workflow. Usage :
  GITHUB_TOKEN=... python scripts/trophies.py -u anthonin-tech -o assets/trophies.svg
  python scripts/trophies.py --sample -o /tmp/trophies.svg
"""
import argparse
import datetime as dt
import json
import os
import urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection { totalCommitContributions restrictedContributionsCount }
  }
}"""

RANKS = ["SSS", "SS", "S", "AAA", "AA", "A", "B", "C"]
# seuils minimaux pour chaque rang, du plus haut au plus bas
THRESHOLDS = {
    "Commits":    [4000, 2000, 1000, 500, 200, 100, 10, 1],
    "Étoiles":    [2000, 700, 200, 100, 50, 30, 10, 1],
    "Abonnés":    [1000, 400, 200, 100, 50, 20, 10, 1],
    "Dépôts":     [50, 45, 40, 35, 30, 20, 10, 1],
    "Pull requests": [1000, 500, 200, 100, 50, 20, 10, 1],
    "Issues":     [1000, 500, 200, 100, 50, 20, 10, 1],
    "Ancienneté": [20, 15, 10, 7, 5, 3, 1, 0],
}
_OLD_COLORS = {  # (ancien rendu, conservé pour référence)
    "S": ("#ffd84d", "#c9a227"),
    "A": ("#e3e8ef", "#9aa4b2"),
    "B": ("#e0975b", "#a8643a"),
    "?": ("#484f58", "#30363d"),
}


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "trophees-maison"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"Erreur GraphQL : {body['errors']}")
    u = body["data"]["user"]
    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    years = (dt.datetime.now(dt.timezone.utc) - created).days // 365
    cc = u["contributionsCollection"]
    return {
        "Commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "Étoiles": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "Abonnés": u["followers"]["totalCount"],
        "Dépôts": u["repositories"]["totalCount"],
        "Pull requests": u["pullRequests"]["totalCount"],
        "Issues": u["issues"]["totalCount"],
        "Ancienneté": years,
    }


def rank(name, value):
    for r, t in zip(RANKS, THRESHOLDS[name]):
        if value >= t and not (name == "Ancienneté" and t == 0 and value < 0):
            return r
    return "?"


def unit(name, value):
    if name == "Ancienneté":
        return f"{value} an" + ("s" if value > 1 else "")
    return str(value)


# --- Rendu « tableau de badges » en pixel-art ---------------------------------
ICONS = {  # 12x12, "#" = pixel plein, "o" = ombre
    "Commits": [
        "............",
        ".##########.",
        "##.######.##",
        "#..######..#",
        "##.######.##",
        ".##########.",
        "...######...",
        "....####....",
        ".....##.....",
        ".....##.....",
        "...######...",
        "..oooooooo..",
    ],
    "Étoiles": [
        ".....##.....",
        ".....##.....",
        "....####....",
        "############",
        ".##########.",
        "..########..",
        "...######...",
        "..########..",
        "..###..###..",
        ".###....###.",
        ".##......##.",
        "............",
    ],
    "Abonnés": [
        "...##..##...",
        "..####.###..",
        "..####.###..",
        "...##..##...",
        "............",
        ".######.###.",
        "########.###",
        "########.###",
        "########.###",
        "########....",
        "............",
        "............",
    ],
    "Dépôts": [
        "............",
        ".####.......",
        "#####.......",
        "############",
        "#..........#",
        "#.########.#",
        "#..........#",
        "#.######...#",
        "#..........#",
        "############",
        ".oooooooooo.",
        "............",
    ],
    "Pull requests": [
        ".##......##.",
        "#..#....#..#",
        "#..#....#..#",
        ".##...#..##.",
        ".#...###..#.",
        ".#..#.#...#.",
        ".#....#...#.",
        ".#...#....#.",
        ".#..#.....#.",
        ".##......##.",
        "#..#....#..#",
        ".##......##.",
    ],
    "Issues": [
        "...######...",
        "..#......#..",
        ".#...##...#.",
        "#....##....#",
        "#....##....#",
        "#....##....#",
        "#....##....#",
        "#..........#",
        "#....##....#",
        ".#...##...#.",
        "..#......#..",
        "...######...",
    ],
    "Ancienneté": [
        "############",
        ".#........#.",
        ".#.######.#.",
        "..#.####.#..",
        "...#.##.#...",
        "....#..#....",
        "....#..#....",
        "...#....#...",
        "..#..##..#..",
        ".#.######.#.",
        ".#........#.",
        "############",
    ],
}
FRAMES = {  # (cadre clair, cadre sombre, fond de carte, couleur de l'icône)
    "S": ("#f9a8d4", "#be185d", "#2a0f22", "#fbcfe8"),
    "A": ("#d8b4fe", "#7e22ce", "#1e1030", "#f3e8ff"),
    "B": ("#f0abfc", "#a21caf", "#250d26", "#f5d0fe"),
    "?": ("#6e7681", "#30363d", "#161b22", "#8b949e"),
}


def pixel_icon(name, x, y, px, color):
    out = []
    for r, row in enumerate(ICONS[name]):
        for c, ch in enumerate(row):
            if ch in "#o":
                fill = color if ch == "#" else "#000000"
                op = "" if ch == "#" else ' opacity=".35"'
                out.append(f'<rect x="{x + c * px}" y="{y + r * px}" width="{px}" height="{px}" '
                           f'fill="{fill}"{op}/>')
    return "".join(out)


def card(name, value, r, x, y, angle):
    fam = "S" if r.startswith("S") else "A" if r.startswith("A") else "B" if r in ("B", "C") else "?"
    light, dark, body, icon = FRAMES[fam]
    w, h = 96, 124
    font = 'font-family="Courier New,Consolas,monospace"'
    g = [f'<g transform="translate({x},{y}) rotate({angle} {w / 2} {h / 2})">',
         # ombre portée en escalier
         f'<rect x="5" y="5" width="{w}" height="{h}" fill="#000" opacity=".55"/>',
         # cadre double pixelisé
         f'<rect width="{w}" height="{h}" fill="{dark}"/>',
         f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" fill="{light}"/>',
         f'<rect x="6" y="6" width="{w - 12}" height="{h - 12}" fill="{body}"/>',
         # bandeau du haut avec le rang
         f'<rect x="6" y="6" width="{w - 12}" height="16" fill="{dark}"/>',
         f'<text x="{w / 2}" y="18" font-size="11" font-weight="700" fill="{light}" '
         f'text-anchor="middle" {font}>RANG {r}</text>',
         pixel_icon(name, w / 2 - 24, 30, 4, icon),
         # bandeau du bas : nom + valeur
         f'<rect x="6" y="{h - 34}" width="{w - 12}" height="28" fill="{dark}" opacity=".85"/>',
         f'<text x="{w / 2}" y="{h - 22}" font-size="9.5" font-weight="700" fill="#ffffff" '
         f'text-anchor="middle" {font}>{name.upper()}</text>',
         f'<text x="{w / 2}" y="{h - 10}" font-size="9.5" fill="{light}" '
         f'text-anchor="middle" {font}>{unit(name, value)}</text>',
         "</g>"]
    return "".join(g)


def build_svg(stats):
    W, H = 760, 200
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'shape-rendering="crispEdges">',
           '<defs><pattern id="bg" width="40" height="40" patternUnits="userSpaceOnUse">'
           '<rect width="40" height="40" fill="#120d18"/>'
           '<rect x="6" y="8" width="2" height="2" fill="#2e2140"/>'
           '<rect x="26" y="4" width="4" height="2" fill="#261a35"/>'
           '<rect x="30" y="24" width="2" height="2" fill="#2e2140"/>'
           '<rect x="12" y="28" width="6" height="2" fill="#22182e"/>'
           '<rect x="14" y="26" width="2" height="6" fill="#22182e"/>'
           '</pattern></defs>',
           f'<rect width="{W}" height="{H}" fill="url(#bg)"/>']
    items = list(stats.items())
    ranked = [(n, v, rank(n, v)) for n, v in items]
    # les 3 plus faibles empilés à gauche comme une pile de cartes, les autres en éventail
    order = sorted(ranked, key=lambda t: RANKS.index(t[2]) if t[2] in RANKS else 99, reverse=True)
    stack, spread = order[:3], order[3:]
    for i, (n, v, r) in enumerate(stack):
        out.append(card(n, v, r, 18 + i * 22, 22 + i * 14, 0))
    angles = [-3, 2, -2, 3, -1, 2]
    for i, (n, v, r) in enumerate(spread):
        out.append(card(n, v, r, 200 + i * 132, 30 + (i % 2) * 10, angles[i % len(angles)]))
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "octocat"))
    ap.add_argument("-o", "--out", default="assets/trophies.svg")
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    if a.sample:
        stats = {"Commits": 372, "Étoiles": 3, "Abonnés": 3, "Dépôts": 10,
                 "Pull requests": 12, "Issues": 2, "Ancienneté": 2}
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN manquant")
        stats = fetch(a.user, token)
    svg = build_svg(stats)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(a.out, stats)


if __name__ == "__main__":
    main()
