#!/usr/bin/env python3
"""Génère plusieurs animations SVG à partir du graphe de contributions GitHub.

Fichiers produits (dans --out-dir) :
  tetris.svg    pièces de Tetris qui tombent (voir tetris.py)
  snake.svg     un serpent qui mange les contributions
  pacman.svg    Pac-Man poursuivi par un fantôme
  breakout.svg  casse-briques : la balle détruit les contributions
  shooter.svg   space shooter : un vaisseau tire sur les contributions
  3d.svg        graphe 3D isométrique qui pousse en vague

Aucune dépendance externe. Usage :
  GITHUB_TOKEN=... python scripts/arcade.py -u anthonin-tech --out-dir assets
  python scripts/arcade.py --sample --out-dir /tmp/arcade      # données factices
"""
import argparse
import math
import os

from tetris import CELL, EMPTY, LEVELS, STEP, build_svg as tetris_svg, fetch, sample

M = 2  # marge autour de la grille


# --- Outils communs -----------------------------------------------------------
def xy(w, d):
    """Coin haut-gauche de la case (semaine, jour)."""
    return M + w * STEP, M + d * STEP


def center(w, d):
    x, y = xy(w, d)
    return x + CELL / 2, y + CELL / 2


def P(t, T):
    return f"{100 * min(max(t, 0), T) / T:.3f}%"


def cells(weeks):
    """(semaine, jour, couleur | None, nombre) pour chaque jour."""
    out = []
    for w, wk in enumerate(weeks):
        for day in wk["contributionDays"]:
            out.append((w, day["weekday"], LEVELS.get(day["contributionLevel"]),
                        day["contributionCount"]))
    return out


def svg_open(width, height, css):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.0f} {height:.0f}">',
            "<style>" + "".join(css) + "</style>"]


def empty_grid(all_cells):
    return "".join(f'<rect x="{xy(w, d)[0]}" y="{xy(w, d)[1]}" width="{CELL}" height="{CELL}" '
                   f'rx="2" fill="{EMPTY}"/>' for w, d, _, _ in all_cells)


def eaten_cells(active, hit, T, back, css, explode=False):
    """Cases actives qui disparaissent à l'instant hit[(w, d)] puis reviennent à `back`."""
    out = []
    for i, ((w, d), color) in enumerate(active.items()):
        t = hit[(w, d)]
        x, y = xy(w, d)
        if explode:
            css.append(f"@keyframes e{i}{{0%,{P(t, T)}{{opacity:1;transform:scale(1)}}"
                       f"{P(t + .15, T)}{{opacity:0;transform:scale(1.9)}}"
                       f"{P(back, T)}{{opacity:0;transform:scale(1)}}100%{{opacity:1;transform:scale(1)}}}}")
        else:
            css.append(f"@keyframes e{i}{{0%,{P(t, T)}{{opacity:1}}{P(t + .08, T)},{P(back, T)}"
                       f"{{opacity:0}}100%{{opacity:1}}}}")
        out.append(f'<rect class="a" style="animation-name:e{i}" x="{x}" y="{y}" width="{CELL}" '
                   f'height="{CELL}" rx="2" fill="{color}"/>')
    return out


def base_css(T):
    return [f".a{{animation-duration:{T:.2f}s;animation-iteration-count:infinite;"
            "animation-timing-function:linear;animation-fill-mode:both;"
            "transform-box:fill-box;transform-origin:center}",
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"]


def grid_path(start, targets):
    """Chemin case par case allant toujours vers la cible la plus proche."""
    pos, left = start, set(targets)
    steps, hit = [pos], {}
    if pos in left:
        left.discard(pos)
        hit[pos] = 0
    while left:
        goal = min(left, key=lambda c: (abs(c[0] - pos[0]) + abs(c[1] - pos[1]), c))
        while pos != goal:
            if pos[0] != goal[0]:
                pos = (pos[0] + (1 if goal[0] > pos[0] else -1), pos[1])
            else:
                pos = (pos[0], pos[1] + (1 if goal[1] > pos[1] else -1))
            steps.append(pos)
            if pos in left:
                left.discard(pos)
                hit[pos] = len(steps) - 1
    return steps, hit


def move_keyframes(name, points, times, T, extra=""):
    """@keyframes de translation passant par `points` (px) aux instants `times`."""
    parts = [f"{P(t, T)}{{transform:translate({x:.1f}px,{y:.1f}px){extra}}}"
             for (x, y), t in zip(points, times)]
    x, y = points[-1]
    parts.append(f"100%{{transform:translate({x:.1f}px,{y:.1f}px){extra}}}")
    return f"@keyframes {name}{{{''.join(parts)}}}"


def visibility(name, t_in, t_out, T):
    return (f"@keyframes {name}{{0%{{opacity:0}}{P(t_in, T)},{P(t_out, T)}{{opacity:1}}"
            f"{P(t_out + .3, T)},100%{{opacity:0}}}}")


# --- Snake --------------------------------------------------------------------
def snake(weeks):
    all_c = cells(weeks)
    n_weeks = len(weeks)
    active = {(w, d): c for w, d, c, _ in all_c if c}
    steps, idx = grid_path((0, 0), active)
    dt = 0.045
    end = len(steps) * dt
    T = end + 1.6
    back = T - 0.5
    hit = {c: i * dt for c, i in idx.items()}
    css = base_css(T)
    pts = [xy(*s) for s in steps]
    css.append(move_keyframes("sn", pts, [i * dt for i in range(len(steps))], T))
    css.append(visibility("sv", 0.15, end + 0.1, T))
    body = eaten_cells(active, hit, T, back, css)
    snake_parts = []
    for k, (size, color) in enumerate([(CELL, "#c084fc"), (CELL - 1, "#a855f7"),
                                       (CELL - 2, "#9333ea"), (CELL - 3, "#7e22ce"),
                                       (CELL - 4, "#6b21a8")]):
        off = (CELL - size) / 2
        snake_parts.insert(0, f'<g class="a" style="animation-name:sn;animation-delay:{k * dt:.3f}s">'
                              f'<rect x="{off}" y="{off}" width="{size}" height="{size}" rx="3" '
                              f'fill="{color}"/></g>')
    width = M * 2 + n_weeks * STEP - (STEP - CELL)
    height = M * 2 + 7 * STEP - (STEP - CELL)
    out = svg_open(width, height, css)
    out.append(empty_grid(all_c))
    out.extend(body)
    out.append(f'<g class="a" style="animation-name:sv">{"".join(snake_parts)}</g></svg>')
    return "\n".join(out)


# --- Pac-Man ------------------------------------------------------------------
def pacman(weeks):
    all_c = cells(weeks)
    n_weeks = len(weeks)
    active = {(w, d): c for w, d, c, _ in all_c if c}
    steps, idx = grid_path((0, 0), active)
    dt = 0.06
    end = len(steps) * dt
    T = end + 1.6
    back = T - 0.5
    hit = {c: i * dt for c, i in idx.items()}
    css = base_css(T)
    times = [i * dt for i in range(len(steps))]
    css.append(move_keyframes("pm", [xy(*s) for s in steps], times, T))
    # orientation : instantanée à chaque virage
    rot, last = [], 0
    for i, s in enumerate(steps):
        if i:
            dx, dy = s[0] - steps[i - 1][0], s[1] - steps[i - 1][1]
            last = 0 if dx > 0 else 180 if dx < 0 else 90 if dy > 0 else 270
        rot.append(f"{P(times[i], T)}{{transform:rotate({last}deg)}}")
    css.append(f"@keyframes pr{{{''.join(rot)}100%{{transform:rotate({last}deg)}}}}")
    css.append(".r{animation:pr " f"{T:.2f}s step-end infinite both" "}")
    css.append("@keyframes ch{0%,49%{opacity:1}50%,100%{opacity:0}}")
    css.append(".o{animation:ch .24s infinite}.c{animation:ch .24s -.12s infinite}")
    css.append(visibility("pv", 0.15, end + 0.1, T))
    body = eaten_cells(active, hit, T, back, css)

    r = CELL * 0.72
    a = math.radians(38)
    mx, my = r * math.cos(a), r * math.sin(a)
    open_ = f'<path class="o" d="M0,0 L{mx:.2f},{-my:.2f} A{r:.2f},{r:.2f} 0 1 0 {mx:.2f},{my:.2f} Z" fill="#facc15"/>'
    closed = f'<circle class="c" r="{r:.2f}" fill="#facc15"/>'
    h = CELL / 2
    pac = (f'<g class="a" style="animation-name:pm"><g transform="translate({h},{h})">'
           f'<g class="r">{open_}{closed}</g></g></g>')
    s = CELL + 1
    ghost_shape = (f'<path d="M0,{s} V{s / 2} A{s / 2},{s / 2} 0 0 1 {s},{s / 2} V{s} '
                   f'L{5 * s / 6:.1f},{.82 * s:.1f} L{2 * s / 3:.1f},{s} L{s / 2:.1f},{.82 * s:.1f} '
                   f'L{s / 3:.1f},{s} L{s / 6:.1f},{.82 * s:.1f} Z" fill="#f87171"/>'
                   f'<circle cx="{.32 * s:.1f}" cy="{.45 * s:.1f}" r="1.9" fill="#fff"/>'
                   f'<circle cx="{.68 * s:.1f}" cy="{.45 * s:.1f}" r="1.9" fill="#fff"/>'
                   f'<circle cx="{.36 * s:.1f}" cy="{.47 * s:.1f}" r=".9" fill="#1e3a8a"/>'
                   f'<circle cx="{.72 * s:.1f}" cy="{.47 * s:.1f}" r=".9" fill="#1e3a8a"/>')
    ghost = (f'<g class="a" style="animation-name:pm;animation-delay:{7 * dt:.2f}s">'
             f'<g transform="translate(-.5,-.5)">{ghost_shape}</g></g>')
    width = M * 2 + n_weeks * STEP - (STEP - CELL) + 2
    height = M * 2 + 7 * STEP - (STEP - CELL) + 2
    out = svg_open(width, height, css)
    out.append(empty_grid(all_c))
    out.extend(body)
    out.append(f'<g class="a" style="animation-name:pv">{ghost}{pac}</g></svg>')
    return "\n".join(out)


# --- Casse-briques ------------------------------------------------------------
def breakout(weeks):
    all_c = cells(weeks)
    n_weeks = len(weeks)
    active = {(w, d): c for w, d, c, _ in all_c if c}
    width = M * 2 + n_weeks * STEP - (STEP - CELL)
    grid_bottom = M + 7 * STEP
    paddle_y = grid_bottom + 46
    height = paddle_y + 8
    br, speed, pw = 3.2, 650.0, 40

    pos = (width / 2, paddle_y - br)
    t = 0.4
    ball_pts, ball_t = [pos], [0.0]
    pad_pts, pad_t = [(width / 2, 0)], [0.0]
    hit, left = {}, set(active)
    while left:
        for _ in range(3):  # la balle enchaîne jusqu'à 3 briques par montée
            if not left:
                break
            goal = min(left, key=lambda c: (math.dist(pos, center(*c)), c))
            c = center(*goal)
            t += max(math.dist(pos, c) / speed, 0.04)
            ball_pts.append(c)
            ball_t.append(t)
            hit[goal] = t
            left.discard(goal)
            pos = c
        land = (min(max(pos[0] + 25 * math.sin(t * 7), pw / 2), width - pw / 2), paddle_y - br)
        t += math.dist(pos, land) / speed
        ball_pts.append(land)
        ball_t.append(t)
        pad_pts.append((land[0], 0))
        pad_t.append(t)
        pos = land
    end = t
    T = end + 1.6
    back = T - 0.5
    css = base_css(T)
    css.append(move_keyframes("bb", ball_pts, ball_t, T))
    css.append(move_keyframes("bp", [(x - pw / 2, paddle_y) for x, _ in pad_pts], pad_t, T))
    body = eaten_cells(active, hit, T, back, css, explode=True)
    out = svg_open(width, height, css)
    out.append(empty_grid(all_c))
    out.extend(body)
    out.append(f'<g class="a" style="animation-name:bp"><rect width="{pw}" height="5" rx="2.5" '
               f'fill="#58a6ff"/></g>')
    out.append(f'<g class="a" style="animation-name:bb"><circle r="{br}" fill="#f0f6fc"/></g></svg>')
    return "\n".join(out)


# --- Space shooter ------------------------------------------------------------
def shooter(weeks):
    all_c = cells(weeks)
    n_weeks = len(weeks)
    active = {(w, d): c for w, d, c, _ in all_c if c}
    width = M * 2 + n_weeks * STEP - (STEP - CELL)
    ship_y = M + 7 * STEP + 40
    height = ship_y + 14
    order = sorted(active, key=lambda c: (c[0], -c[1]))
    t, col = 0.4, None
    ship_pts, ship_t, shots = [(width / 2, ship_y)], [0.0], []
    hit = {}
    for c in order:
        if c[0] != col:
            x = center(*c)[0]
            t += 0.05 + 0.012 * (abs(c[0] - col) if col is not None else 8)
            ship_pts.append((x, ship_y))
            ship_t.append(t)
            col = c[0]
        shots.append((c, t))
        hit[c] = t + 0.07
        t += 0.075
        ship_pts.append(ship_pts[-1])
        ship_t.append(t)
    end = t
    T = end + 1.6
    back = T - 0.5
    css = base_css(T)
    css.append(move_keyframes("sh", ship_pts, ship_t, T))
    out_shots = []
    for i, (c, ts) in enumerate(shots):
        cx, _ = center(*c)
        top = xy(*c)[1] + CELL
        css.append(f"@keyframes l{i}{{0%,{P(ts, T)}{{opacity:0}}{P(ts + .005, T)},{P(ts + .07, T)}"
                   f"{{opacity:1}}{P(ts + .09, T)},100%{{opacity:0}}}}")
        out_shots.append(f'<rect class="a" style="animation-name:l{i}" x="{cx - 1:.1f}" y="{top:.1f}" '
                         f'width="2" height="{ship_y - top - 6:.1f}" rx="1" fill="#ff4d6d"/>')
    body = eaten_cells(active, hit, T, back, css, explode=True)
    ship = ('<path d="M0,-7 L7,6 L2,4 L0,7 L-2,4 L-7,6 Z" fill="#58a6ff"/>'
            '<path d="M-1.5,7 L0,11 L1.5,7 Z" fill="#facc15"/>')
    out = svg_open(width, height, css)
    out.append(empty_grid(all_c))
    out.extend(body)
    out.extend(out_shots)
    out.append(f'<g class="a" style="animation-name:sh">{ship}</g></svg>')
    return "\n".join(out)


# --- 3D isométrique -----------------------------------------------------------
def shade(hex_color, f):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(v * f) for v in (r, g, b))


def iso3d(weeks):
    all_c = cells(weeks)
    n_weeks = len(weeks)
    u, v = (10.5, 2.6), (-6.5, 3.9)    # axes semaine / jour à l'écran
    k = 0.82                           # taille du cube par rapport à la case
    max_c = max([c for *_, c in all_c] + [1])
    max_h = 42
    ox = 7 * -v[0] + 6
    oy = max_h + 8

    def pt(w, d):
        return ox + w * u[0] + d * v[0], oy + w * u[1] + d * v[1]

    width = pt(n_weeks, 0)[0] + 6
    height = pt(n_weeks, 7)[1] + 6
    T = 7.0
    css = [f"@keyframes gr{{0%{{transform:scaleY(0)}}18%,82%{{transform:scaleY(1)}}100%{{transform:scaleY(0)}}}}",
           f".b{{animation:gr {T}s ease-in-out infinite both;transform-box:fill-box;transform-origin:bottom}}",
           "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"]
    out = svg_open(width, height, css)
    for w, d, color, count in sorted(all_c, key=lambda c: (c[0] + c[1], c[0])):
        h = 2.0 + (math.sqrt(count / max_c) * max_h if color else 0)
        top = color or EMPTY
        a, b = (1 - k) / 2, (1 + k) / 2
        p = [pt(w + a, d + a), pt(w + b, d + a), pt(w + b, d + b), pt(w + a, d + b)]
        lift = [(x, y - h) for x, y in p]
        poly = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        right = [lift[1], lift[2], p[2], p[1]]
        front = [lift[3], lift[2], p[2], p[3]]
        out.append(f'<g class="b" style="animation-delay:{w * 0.035:.2f}s">'
                   f'<polygon points="{poly(right)}" fill="{shade(top, .55)}"/>'
                   f'<polygon points="{poly(front)}" fill="{shade(top, .75)}"/>'
                   f'<polygon points="{poly(lift)}" fill="{top}"/></g>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "octocat"))
    ap.add_argument("--out-dir", default="assets")
    ap.add_argument("--sample", action="store_true", help="données factices (test local)")
    a = ap.parse_args()
    if a.sample:
        weeks, total = sample()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN manquant")
        weeks, total = fetch(a.user, token)
    os.makedirs(a.out_dir, exist_ok=True)
    outputs = {
        "tetris.svg": tetris_svg(weeks, total, a.user),
        "snake.svg": snake(weeks),
        "pacman.svg": pacman(weeks),
        "breakout.svg": breakout(weeks),
        "shooter.svg": shooter(weeks),
        "3d.svg": iso3d(weeks),
    }
    for name, svg in outputs.items():
        with open(os.path.join(a.out_dir, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"{name:13} {len(svg) // 1024:4} Ko")
    print(f"{total} contributions")


if __name__ == "__main__":
    main()
