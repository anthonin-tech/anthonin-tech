#!/usr/bin/env python3
"""Carte « Top langages par dépôt » : anneau du nombre de dépôts par langage principal.

Version maison (aucun service externe), dans le même style que la carte de stats.
Usage :
  GITHUB_TOKEN=... python scripts/langs.py -u anthonin-tech -o assets/langs.svg
  python scripts/langs.py --sample -o /tmp/langs.svg
"""
import argparse
import json
import math
import os
import urllib.request

BG, TITLE, TEXT = "#0f1a16", "#2f9e83", "#ffffff"
MAX_LANGS = 5

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes { primaryLanguage { name color } }
    }
  }
}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "langs-maison"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"Erreur GraphQL : {body['errors']}")
    counts = {}
    for n in body["data"]["user"]["repositories"]["nodes"]:
        lang = n["primaryLanguage"]
        if lang:
            counts.setdefault(lang["name"], [0, lang["color"] or "#8b949e"])[0] += 1
    return counts


def build_svg(counts):
    items = sorted(counts.items(), key=lambda kv: (-kv[1][0], kv[0]))
    if len(items) > MAX_LANGS:
        rest = sum(v[0] for _, v in items[MAX_LANGS - 1:])
        items = items[:MAX_LANGS - 1] + [("Autres", [rest, "#8b949e"])]
    total = sum(v[0] for _, v in items) or 1
    W, H = 340, 195
    font = 'font-family="Segoe UI,Ubuntu,-apple-system,Helvetica,Arial,sans-serif"'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="4.5" fill="{BG}"/>',
           f'<text x="25" y="35" font-size="18" font-weight="600" fill="{TITLE}" {font}>'
           f'Top langages par dépôt</text>']
    y = 70
    for name, (n, color) in items:
        out.append(f'<rect x="25" y="{y - 10}" width="12" height="12" rx="2" fill="{color}"/>')
        out.append(f'<text x="45" y="{y}" font-size="13" fill="{TEXT}" {font}>{name}'
                   f'<tspan fill="#8b949e"> {n}</tspan></text>')
        y += 23
    cx, cy, r, sw = 255, 112, 46, 22
    circ = 2 * math.pi * r
    offset = 0.0
    for name, (n, color) in items:
        seg = circ * n / total
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
                   f'stroke-width="{sw}" stroke-dasharray="{seg:.2f} {circ - seg:.2f}" '
                   f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += seg
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "octocat"))
    ap.add_argument("-o", "--out", default="assets/langs.svg")
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    if a.sample:
        counts = {"JavaScript": [4, "#f1e05a"], "HTML": [2, "#e34c26"], "Java": [1, "#b07219"],
                  "TypeScript": [2, "#3178c6"], "Jupyter Notebook": [1, "#DA5B0B"]}
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN manquant")
        counts = fetch(a.user, token)
    svg = build_svg(counts)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(a.out, {k: v[0] for k, v in counts.items()})


if __name__ == "__main__":
    main()
