#!/usr/bin/env python3
"""Ligne de trophées GitHub, version maison (remplace github-profile-trophy.vercel.app).

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
COLORS = {  # couleur de la coupe par famille de rang
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


def build_svg(stats):
    w, h, gap = 110, 120, 8
    n = len(stats)
    W = n * w + (n - 1) * gap
    font = 'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif"'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">']
    for i, (name, value) in enumerate(stats.items()):
        r = rank(name, value)
        fam = "S" if r.startswith("S") else "A" if r.startswith("A") else "B" if r in ("B", "C") else "?"
        light, dark = COLORS[fam]
        x = i * (w + gap)
        cx = x + w / 2
        out.append(f'<rect x="{x + .5}" y=".5" width="{w - 1}" height="{h - 1}" rx="8" '
                   f'fill="#0d1117" stroke="#30363d"/>')
        # coupe
        out.append(f'<g transform="translate({cx - 16},14)">'
                   f'<path d="M4 0h24v10a12 12 0 0 1-24 0Z" fill="{light}"/>'
                   f'<path d="M4 3H0v4a6 6 0 0 0 6 6M28 3h4v4a6 6 0 0 1-6 6" fill="none" '
                   f'stroke="{dark}" stroke-width="2.2"/>'
                   f'<rect x="13" y="21" width="6" height="7" fill="{dark}"/>'
                   f'<rect x="7" y="28" width="18" height="5" rx="1.5" fill="{dark}"/></g>')
        out.append(f'<text x="{cx}" y="70" font-size="16" font-weight="800" fill="{light}" '
                   f'text-anchor="middle" {font}>{r}</text>')
        out.append(f'<text x="{cx}" y="90" font-size="11" font-weight="600" fill="#c9d1d9" '
                   f'text-anchor="middle" {font}>{name}</text>')
        out.append(f'<text x="{cx}" y="106" font-size="11" fill="#8b949e" '
                   f'text-anchor="middle" {font}>{unit(name, value)}</text>')
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
