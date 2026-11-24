#!/usr/bin/env python3
"""Tableau de bord « métriques » maison, inspiré de lowlighter/metrics.

Panneaux générés, tous dans un seul SVG statique :
  1. En-tête : avatar, nom, bio, abonnés/abonnements
  2. Statistiques rapides : repos publics, étoiles reçues, contributions, abonnés
  3. Langages les plus utilisés (vraies couleurs GitHub par langage)
  4. Heures d'activité (« habits ») — répartition des évènements publics par heure
  5. Contributions notables — dépôts (y compris externes) les plus contribués
  6. Dépôts les plus étoilés

Aucune dépendance externe, uniquement l'API GitHub (GraphQL + REST) avec le
jeton déjà fourni par le workflow. Usage :
  GITHUB_TOKEN=... python scripts/metrics.py -u anthonin-tech -o assets/metrics.svg
  python scripts/metrics.py --sample -o /tmp/metrics.svg   # données factices
"""
import argparse
import base64
import datetime as dt
import json
import os
import random
import urllib.request

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Paris")
except Exception:
    TZ = dt.timezone(dt.timedelta(hours=1))

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#39d353"
W = 800
PAD = 20

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login bio avatarUrl
    followers { totalCount }
    following { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
      commitContributionsByRepository(maxRepositories: 10) {
        repository { nameWithOwner stargazerCount isFork }
        contributions { totalCount }
      }
    }
  }
}"""


def api_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"bearer {token}",
                                                "User-Agent": "metrics-maison"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "metrics-maison"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"Erreur GraphQL : {body['errors']}")
    user = body["data"]["user"]

    hours = [0] * 24
    for page in (1, 2, 3):
        try:
            events = api_get(f"https://api.github.com/users/{login}/events/public"
                             f"?per_page=100&page={page}", token)
        except Exception:
            break
        if not events:
            break
        for e in events:
            try:
                t = dt.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
                hours[t.astimezone(TZ).hour] += 1
            except Exception:
                pass

    avatar_b64 = None
    try:
        req = urllib.request.Request(user["avatarUrl"], headers={"User-Agent": "metrics-maison"})
        with urllib.request.urlopen(req, timeout=15) as r:
            avatar_b64 = base64.b64encode(r.read()).decode()
    except Exception:
        pass

    return user, hours, avatar_b64


def sample():
    rnd = random.Random(3)
    user = {
        "name": "Anthonin Chesneau", "login": "anthonin-tech",
        "bio": "Étudiant BTS SIO + Bachelor informatique — EPSI Bordeaux",
        "avatarUrl": None,
        "followers": {"totalCount": 12}, "following": {"totalCount": 20},
        "repositories": {"totalCount": 17, "nodes": [
            {"name": "CodeQuest", "stargazerCount": 4,
             "languages": {"edges": [{"size": 8000, "node": {"name": "Vue", "color": "#41b883"}},
                                     {"size": 3000, "node": {"name": "TypeScript", "color": "#3178c6"}}]}},
            {"name": "Notely", "stargazerCount": 2,
             "languages": {"edges": [{"size": 6000, "node": {"name": "PHP", "color": "#4F5D95"}},
                                     {"size": 2000, "node": {"name": "JavaScript", "color": "#f1e05a"}}]}},
            {"name": "veille-bot", "stargazerCount": 1,
             "languages": {"edges": [{"size": 5000, "node": {"name": "Python", "color": "#3572A5"}}]}},
            {"name": "dashboard-perso", "stargazerCount": 0,
             "languages": {"edges": [{"size": 7000, "node": {"name": "Dart", "color": "#00B4AB"}}]}},
        ]},
        "contributionsCollection": {
            "contributionCalendar": {"totalContributions": 372},
            "commitContributionsByRepository": [
                {"repository": {"nameWithOwner": "anthonin-tech/CodeQuest", "stargazerCount": 4, "isFork": False},
                 "contributions": {"totalCount": 140}},
                {"repository": {"nameWithOwner": "anthonin-tech/Notely", "stargazerCount": 2, "isFork": False},
                 "contributions": {"totalCount": 80}},
                {"repository": {"nameWithOwner": "Gladrat/2627-js_ts-epsi-b2", "stargazerCount": 0, "isFork": False},
                 "contributions": {"totalCount": 35}},
            ],
        },
    }
    hours = [max(0, int(rnd.gauss(8, 6))) for _ in range(24)]
    return user, hours, None


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def panel(y, h, title):
    out = [f'<rect x="{PAD}" y="{y}" width="{W - 2 * PAD}" height="{h}" rx="8" '
           f'fill="{PANEL}" stroke="{BORDER}"/>']
    if title:
        out.append(f'<text x="{PAD + 16}" y="{y + 24}" font-size="13" font-weight="700" '
                   f'fill="{TEXT}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">{title}</text>')
    return out


def build_svg(user, hours, avatar_b64):
    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    lang_bytes = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            lang_bytes.setdefault(n, [0, e["node"]["color"] or MUTED])
            lang_bytes[n][0] += e["size"]
    total_bytes = sum(v[0] for v in lang_bytes.values()) or 1
    top_langs = sorted(lang_bytes.items(), key=lambda kv: -kv[1][0])[:6]

    notable = [c for c in user["contributionsCollection"]["commitContributionsByRepository"]]
    top_repos = sorted(repos, key=lambda r: -r["stargazerCount"])[:5]

    font = 'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif"'
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" viewBox="0 0 {W} 1" >']
    body = []
    y = PAD

    # 1. En-tête -----------------------------------------------------------
    h = 90
    body += panel(y, h, None)
    cy = y + h / 2
    if avatar_b64:
        body.append(f'<defs><clipPath id="av"><circle cx="{PAD + 55}" cy="{cy}" r="32"/></clipPath></defs>')
        body.append(f'<image href="data:image/png;base64,{avatar_b64}" x="{PAD + 23}" y="{cy - 32}" '
                   f'width="64" height="64" clip-path="url(#av)"/>')
    else:
        body.append(f'<circle cx="{PAD + 55}" cy="{cy}" r="32" fill="{ACCENT}" opacity=".25"/>')
    tx = PAD + 100
    body.append(f'<text x="{tx}" y="{cy - 10}" font-size="19" font-weight="700" fill="{TEXT}" {font}>'
               f'{esc(user["name"] or user["login"])}</text>')
    body.append(f'<text x="{tx}" y="{cy + 12}" font-size="12" fill="{MUTED}" {font}>'
               f'@{esc(user["login"])} · {esc((user.get("bio") or "")[:70])}</text>')
    body.append(f'<text x="{W - PAD - 16}" y="{cy - 4}" font-size="13" fill="{TEXT}" text-anchor="end" {font}>'
               f'👥 {user["followers"]["totalCount"]} abonnés</text>')
    body.append(f'<text x="{W - PAD - 16}" y="{cy + 16}" font-size="13" fill="{TEXT}" text-anchor="end" {font}>'
               f'➡️ {user["following"]["totalCount"]} abonnements</text>')
    y += h + 16

    # 2. Tuiles de stats -----------------------------------------------------
    h = 70
    tiles = [("📦", user["repositories"]["totalCount"], "Dépôts publics"),
             ("⭐", total_stars, "Étoiles reçues"),
             ("📈", user["contributionsCollection"]["contributionCalendar"]["totalContributions"], "Contributions (1 an)"),
             ("👥", user["followers"]["totalCount"], "Abonnés")]
    tw = (W - 2 * PAD - 3 * 12) / 4
    for i, (icon, val, label) in enumerate(tiles):
        tx0 = PAD + i * (tw + 12)
        body += panel(y, h, None)
        # override x for this tile's panel (re-add correctly sized rect)
        body[-1] = (f'<rect x="{tx0}" y="{y}" width="{tw}" height="{h}" rx="8" '
                   f'fill="{PANEL}" stroke="{BORDER}"/>')
        body.append(f'<text x="{tx0 + tw / 2 - 18}" y="{y + 30}" font-size="18" text-anchor="middle">{icon}</text>')
        body.append(f'<text x="{tx0 + tw / 2 + 14}" y="{y + 32}" font-size="19" font-weight="700" '
                   f'fill="{ACCENT}" text-anchor="middle" {font}>{val}</text>')
        body.append(f'<text x="{tx0 + tw / 2}" y="{y + 50}" font-size="11" fill="{MUTED}" '
                   f'text-anchor="middle" {font}>{label}</text>')
    y += h + 16

    # 3. Langages --------------------------------------------------------
    h = 110
    body += panel(y, h, "🈷️ Langages les plus utilisés")
    bx, by, bw, bh = PAD + 16, y + 40, W - 2 * PAD - 32, 18
    cx = bx
    for name, (size, color) in top_langs:
        frac = size / total_bytes
        seg = bw * frac
        body.append(f'<rect x="{cx:.1f}" y="{by}" width="{max(seg,1):.1f}" height="{bh}" fill="{color}"/>')
        cx += seg
    legend_x, legend_y = bx, by + bh + 20
    for i, (name, (size, color)) in enumerate(top_langs):
        col = i % 3
        row = i // 3
        lx = legend_x + col * (bw / 3)
        ly = legend_y + row * 18
        pct = 100 * size / total_bytes
        body.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>')
        body.append(f'<text x="{lx + 16}" y="{ly}" font-size="11" fill="{TEXT}" {font}>'
                   f'{esc(name)} {pct:.1f}%</text>')
    y += h + 16

    # 4. Heures d'activité -------------------------------------------------
    h = 130
    body += panel(y, h, "⏰ Heures d'activité (Europe/Paris)")
    max_h = max(hours) or 1
    peak = hours.index(max_h)
    cw = (W - 2 * PAD - 32) / 24
    base_y = y + h - 20
    for i, v in enumerate(hours):
        bh2 = 60 * v / max_h
        bx2 = PAD + 16 + i * cw
        color = ACCENT if i == peak else "#2ea043"
        body.append(f'<rect x="{bx2 + 1:.1f}" y="{base_y - bh2:.1f}" width="{cw - 2:.1f}" '
                   f'height="{bh2:.1f}" rx="2" fill="{color}" opacity="{0.45 + 0.55 * v / max_h:.2f}"/>')
        if i % 3 == 0:
            body.append(f'<text x="{bx2 + cw / 2:.1f}" y="{base_y + 14}" font-size="9" fill="{MUTED}" '
                       f'text-anchor="middle" {font}>{i}h</text>')
    body.append(f'<text x="{W - PAD - 16}" y="{y + 24}" font-size="11" fill="{MUTED}" text-anchor="end" {font}>'
               f'pic : {peak}h</text>')
    y += h + 16

    # 5. Contributions notables --------------------------------------------
    h = 30 + 24 * max(len(notable), 1)
    body += panel(y, h, "🎩 Contributions notables")
    ry = y + 44
    if notable:
        for c in notable[:6]:
            repo = c["repository"]
            body.append(f'<text x="{PAD + 16}" y="{ry}" font-size="12" fill="{TEXT}" {font}>'
                       f'{esc(repo["nameWithOwner"])}</text>')
            body.append(f'<text x="{W - PAD - 16}" y="{ry}" font-size="12" fill="{ACCENT}" '
                       f'text-anchor="end" {font}>{c["contributions"]["totalCount"]} commits</text>')
            ry += 24
    else:
        body.append(f'<text x="{PAD + 16}" y="{ry}" font-size="12" fill="{MUTED}" {font}>'
                   f'Pas encore de contribution détectée.</text>')
    y += h + 16

    # 6. Dépôts les plus étoilés --------------------------------------------
    h = 30 + 24 * max(len(top_repos), 1)
    body += panel(y, h, "🌟 Dépôts les plus étoilés")
    ry = y + 44
    if top_repos:
        for r in top_repos:
            body.append(f'<text x="{PAD + 16}" y="{ry}" font-size="12" fill="{TEXT}" {font}>'
                       f'{esc(r["name"])}</text>')
            body.append(f'<text x="{W - PAD - 16}" y="{ry}" font-size="12" fill="{ACCENT}" '
                       f'text-anchor="end" {font}>⭐ {r["stargazerCount"]}</text>')
            ry += 24
    else:
        body.append(f'<text x="{PAD + 16}" y="{ry}" font-size="12" fill="{MUTED}" {font}>'
                   f'Aucun dépôt public pour l\'instant.</text>')
    y += h + PAD

    out[0] = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{y}" '
             f'viewBox="0 0 {W} {y}">')
    out.append(f'<rect width="100%" height="100%" rx="10" fill="{BG}"/>')
    out.extend(body)
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "octocat"))
    ap.add_argument("-o", "--out", default="assets/metrics.svg")
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    if a.sample:
        user, hours, avatar = sample()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN manquant")
        user, hours, avatar = fetch(a.user, token)
    svg = build_svg(user, hours, avatar)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{a.out} : {len(svg) // 1024} Ko")


if __name__ == "__main__":
    main()
