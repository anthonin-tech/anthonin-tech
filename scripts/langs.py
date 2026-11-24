#!/usr/bin/env python3
"""Carte « Top langages & frameworks » : nombre de dépôts par langage et par framework.

- Langages : langage principal de chaque dépôt public (API GraphQL).
- Frameworks : détectés dans les fichiers de dépendances (package.json,
  requirements.txt, pyproject.toml, composer.json, pom.xml, build.gradle,
  pubspec.yaml) et dans les imports Python de chaque dépôt (API REST).
Deux anneaux : langages à l'extérieur, frameworks à l'intérieur.
Version maison, aucun service externe. Usage :
  GITHUB_TOKEN=... python scripts/langs.py -u anthonin-tech -o assets/langs.svg
  python scripts/langs.py --sample -o /tmp/langs.svg
"""
import argparse
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request

BG, TITLE, TEXT, MUTED = "#1a1025", "#e879f9", "#ffffff", "#a99bbd"
MAX_ITEMS = 5

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes { name primaryLanguage { name color } defaultBranchRef { name } }
    }
  }
}"""

MANIFESTS = {"package.json", "requirements.txt", "pyproject.toml", "Pipfile", "composer.json",
             "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml"}
SKIP_DIRS = re.compile(r"(^|/)(node_modules|vendor|venv|\.venv|env|site-packages|dist|build)/")
MAX_PY_FILES = 40

# nom affiché -> (couleur, motifs recherchés dans les dépendances / imports)
FRAMEWORKS = {
    "Vue":        ("#41b883", [r'"vue"\s*:']),
    "Nuxt":       ("#00dc82", [r'"nuxt"\s*:']),
    "React":      ("#61dafb", [r'"react"\s*:']),
    "Next.js":    ("#f5f5f5", [r'"next"\s*:']),
    "Angular":    ("#dd0031", [r'"@angular/core"\s*:']),
    "Svelte":     ("#ff3e00", [r'"svelte"\s*:']),
    "Express":    ("#cbd5e1", [r'"express"\s*:']),
    "NestJS":     ("#e0234e", [r'"@nestjs/core"\s*:']),
    "Tailwind":   ("#38bdf8", [r'"tailwindcss"\s*:']),
    "Bootstrap":  ("#7952b3", [r'"bootstrap"\s*:']),
    "FastAPI":    ("#009688", [r"(?im)^\s*fastapi\b", r'(?i)"fastapi', r"(?m)^\s*(from|import) fastapi\b"]),
    "Flask":      ("#e5e7eb", [r"(?im)^\s*flask\b", r"(?m)^\s*(from|import) flask\b"]),
    "Django":     ("#44b78b", [r"(?im)^\s*django\b", r"(?m)^\s*(from|import) django\b"]),
    "Pygame":     ("#facc15", [r"(?im)^\s*pygame\b", r"(?m)^\s*(from|import) pygame\b"]),
    "discord.py": ("#5865f2", [r"(?im)^\s*discord(\.py)?\b", r"(?m)^\s*(from|import) discord\b"]),
    "Laravel":    ("#ff2d20", [r'"laravel/framework"']),
    "Symfony":    ("#f5f5f5", [r'"symfony/framework-bundle"']),
    "Spring":     ("#6db33f", [r"spring-boot"]),
    "Flutter":    ("#02569b", [r"(?m)^\s*flutter:"]),
}


def http_json(url, token, data=None):
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"bearer {token}", "User-Agent": "langs-maison",
        "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def http_text(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"bearer {token}",
                                               "User-Agent": "langs-maison"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(300_000).decode("utf-8", "replace")


def detect(texts):
    found = set()
    blob = "\n".join(texts)
    for name, (_, patterns) in FRAMEWORKS.items():
        if any(re.search(p, blob) for p in patterns):
            found.add(name)
    return found


def repo_frameworks(login, repo, branch, token):
    try:
        tree = http_json(f"https://api.github.com/repos/{login}/{urllib.parse.quote(repo)}/git/trees/"
                         f"{urllib.parse.quote(branch)}?recursive=1", token)
    except urllib.error.HTTPError:
        return set()
    paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"
             and not SKIP_DIRS.search(t["path"])]
    wanted = [p for p in paths if p.rsplit("/", 1)[-1] in MANIFESTS]
    wanted += [p for p in paths if p.endswith(".py")][:MAX_PY_FILES]
    texts = []
    for p in wanted:
        url = (f"https://raw.githubusercontent.com/{login}/{urllib.parse.quote(repo)}/"
               f"{urllib.parse.quote(branch)}/{urllib.parse.quote(p)}")
        try:
            text = http_text(url, token)
        except Exception:
            continue
        if p.endswith(".py"):  # seulement les lignes d'import
            text = "\n".join(l for l in text.splitlines() if re.match(r"\s*(from|import)\s", l))
        texts.append(text)
    return detect(texts)


def fetch(login, token):
    body = http_json("https://api.github.com/graphql", token,
                     json.dumps({"query": QUERY, "variables": {"login": login}}).encode())
    if "errors" in body:
        raise SystemExit(f"Erreur GraphQL : {body['errors']}")
    langs, fws = {}, {}
    for n in body["data"]["user"]["repositories"]["nodes"]:
        lang = n["primaryLanguage"]
        if lang:
            langs.setdefault(lang["name"], [0, lang["color"] or "#8b949e"])[0] += 1
        if n["defaultBranchRef"]:
            for fw in repo_frameworks(login, n["name"], n["defaultBranchRef"]["name"], token):
                fws.setdefault(fw, [0, FRAMEWORKS[fw][0]])[0] += 1
    return langs, fws


def top(counts):
    items = sorted(counts.items(), key=lambda kv: (-kv[1][0], kv[0]))
    if len(items) > MAX_ITEMS:
        rest = sum(v[0] for _, v in items[MAX_ITEMS - 1:])
        items = items[:MAX_ITEMS - 1] + [("Autres", [rest, "#6b5a80"])]
    return items


def ring(items, cx, cy, r, sw):
    total = sum(v[0] for _, v in items) or 1
    circ = 2 * math.pi * r
    out, offset = [], 0.0
    if not items:
        return [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#2e2140" stroke-width="{sw}"/>']
    for _, (n, color) in items:
        seg = circ * n / total
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
                   f'stroke-width="{sw}" stroke-dasharray="{seg:.2f} {circ - seg:.2f}" '
                   f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += seg
    return out


def legend(items, x, font, empty):
    out = []
    y = 82
    if not items:
        out.append(f'<text x="{x}" y="{y}" font-size="12" fill="{MUTED}" {font}>{empty}</text>')
    for name, (n, color) in items:
        out.append(f'<rect x="{x}" y="{y - 10}" width="11" height="11" rx="2" fill="{color}"/>')
        out.append(f'<text x="{x + 18}" y="{y}" font-size="12.5" fill="{TEXT}" {font}>{name}'
                   f'<tspan fill="{MUTED}"> {n}</tspan></text>')
        y += 21
    return out


def build_svg(langs, fws):
    L, F = top(langs), top(fws)
    W, H = 460, 195
    font = 'font-family="Segoe UI,Ubuntu,-apple-system,Helvetica,Arial,sans-serif"'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="4.5" fill="{BG}"/>',
           f'<text x="25" y="35" font-size="18" font-weight="600" fill="{TITLE}" {font}>'
           f'Top langages &amp; frameworks</text>',
           f'<text x="25" y="60" font-size="11" font-weight="700" fill="{MUTED}" letter-spacing="1" {font}>'
           f'LANGAGES</text>',
           f'<text x="160" y="60" font-size="11" font-weight="700" fill="{MUTED}" letter-spacing="1" {font}>'
           f'FRAMEWORKS</text>']
    out += legend(L, 25, font, "—")
    out += legend(F, 160, font, "Aucun détecté")
    cx, cy = 375, 112
    out += ring(L, cx, cy, 52, 16)   # extérieur : langages
    out += ring(F, cx, cy, 33, 12)   # intérieur : frameworks
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "octocat"))
    ap.add_argument("-o", "--out", default="assets/langs.svg")
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    if a.sample:
        langs = {"Python": [4, "#3572A5"], "HTML": [1, "#e34c26"], "JavaScript": [1, "#f1e05a"],
                 "TypeScript": [1, "#3178c6"]}
        fws = {k: [n, FRAMEWORKS[k][0]] for k, n in
               [("Vue", 1), ("React", 1), ("FastAPI", 1), ("Pygame", 1), ("discord.py", 1)]}
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN manquant")
        langs, fws = fetch(a.user, token)
    svg = build_svg(langs, fws)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(a.out, {k: v[0] for k, v in langs.items()}, {k: v[0] for k, v in fws.items()})


if __name__ == "__main__":
    main()
