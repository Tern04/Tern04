"""Generate the profile banner with Wave Function Collapse.

Mirrors the idea of my thesis on a small scale: a backbone path from the left
edge to the right edge is committed as a hard constraint first, then WFC
collapses the rest of the grid around it. The centre is reserved for text.

Usage: python3 wfc_banner.py [--seed N] [--out DIR]
Writes banner-dark.svg and banner-light.svg. Standard library only.
"""

import argparse
import heapq
import random
from pathlib import Path

COLS, ROWS, TILE = 60, 10, 16
TEXT_BOX = (17, 3, 43, 7)  # cols [c0, c1), rows [r0, r1) kept empty for the title

# Sides are indexed N, E, S, W; a tile is the tuple of its four sockets (1 = connected).
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
BLANK = (0, 0, 0, 0)

# Every socket combination except dead ends (exactly one connection), which look broken.
TILES = [t for t in ((n, e, s, w) for n in (0, 1) for e in (0, 1)
                     for s in (0, 1) for w in (0, 1)) if sum(t) != 1]
WEIGHTS = {0: 1.6, 2: 3.0, 3: 0.7, 4: 0.25}  # by number of connections

THEMES = {
    "dark":  {"bg": "#0d1117", "border": "#30363d", "net": "#30363d",
              "path": "#f0883e", "title": "#e6edf3", "sub": "#8b949e"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "net": "#d0d7de",
              "path": "#bc4c00", "title": "#1f2328", "sub": "#59636e"},
}


class Contradiction(Exception):
    pass


def reserved(x, y):
    c0, r0, c1, r1 = TEXT_BOX
    return c0 <= x < c1 and r0 <= y < r1


def backbone(rng):
    """Cheapest path under random step costs, so the route wanders around the text box."""
    start, goal = (0, rng.randrange(1, 4)), (COLS - 1, rng.randrange(ROWS - 4, ROWS - 1))
    cost = {(x, y): rng.uniform(1.0, 9.0) + (12.0 if y in (0, ROWS - 1) else 0.0)
            for x in range(COLS) for y in range(ROWS)}
    best, prev, queue = {start: 0.0}, {}, [(0.0, start)]
    while queue:
        d, cell = heapq.heappop(queue)
        if cell == goal:
            break
        if d > best[cell]:
            continue
        for dx, dy in DIRS:
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt in cost and not reserved(*nxt) and d + cost[nxt] < best.get(nxt, float("inf")):
                best[nxt], prev[nxt] = d + cost[nxt], cell
                heapq.heappush(queue, (best[nxt], nxt))
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    return path[::-1]


def path_tiles(path):
    """Exact tile for each path cell; the ends open outwards through the left and right edges."""
    sockets = {cell: [0, 0, 0, 0] for cell in path}
    sockets[path[0]][3] = 1
    sockets[path[-1]][1] = 1
    for a, b in zip(path, path[1:]):
        d = DIRS.index((b[0] - a[0], b[1] - a[1]))
        sockets[a][d] = sockets[b][(d + 2) % 4] = 1
    return {cell: tuple(s) for cell, s in sockets.items()}


def initial_domains(fixed):
    domains = {}
    for x in range(COLS):
        for y in range(ROWS):
            if (x, y) in fixed:
                domains[(x, y)] = {fixed[(x, y)]}
            elif reserved(x, y):
                domains[(x, y)] = {BLANK}
            else:
                # Nothing may connect past the banner edge.
                domains[(x, y)] = {t for t in TILES if all(
                    t[d] == 0 for d, (dx, dy) in enumerate(DIRS)
                    if not (0 <= x + dx < COLS and 0 <= y + dy < ROWS))}
    return domains


def propagate(domains, stack):
    while stack:
        x, y = stack.pop()
        for d, (dx, dy) in enumerate(DIRS):
            n = (x + dx, y + dy)
            if n not in domains:
                continue
            offered = {t[d] for t in domains[(x, y)]}
            kept = {t for t in domains[n] if t[(d + 2) % 4] in offered}
            if not kept:
                raise Contradiction
            if kept != domains[n]:
                domains[n] = kept
                stack.append(n)


def collapse(domains, rng):
    propagate(domains, list(domains))
    while True:
        open_cells = [c for c, dom in domains.items() if len(dom) > 1]
        if not open_cells:
            return {c: next(iter(dom)) for c, dom in domains.items()}
        fewest = min(len(domains[c]) for c in open_cells)
        cell = rng.choice([c for c in open_cells if len(domains[c]) == fewest])
        options = sorted(domains[cell])
        domains[cell] = {rng.choices(options, [WEIGHTS[sum(t)] for t in options])[0]}
        propagate(domains, [cell])


def generate(seed):
    """Restart with the next seed on contradiction; without dead-end tiles it can happen."""
    for attempt in range(100):
        rng = random.Random(seed + attempt)
        path = backbone(rng)
        try:
            return collapse(initial_domains(path_tiles(path)), rng), path
        except Contradiction:
            continue
    raise RuntimeError("no valid banner after 100 attempts")


def segments(cells):
    out = []
    for (x, y), t in cells:
        cx, cy = x * TILE + TILE / 2, y * TILE + TILE / 2
        for d, (dx, dy) in enumerate(DIRS):
            if t[d]:
                out.append(f"M{cx:g} {cy:g}L{cx + dx * TILE / 2:g} {cy + dy * TILE / 2:g}")
    return "".join(out)


def render(grid, path, theme):
    c = THEMES[theme]
    w, h = COLS * TILE, ROWS * TILE
    on_path = set(path)
    net = [(cell, t) for cell, t in grid.items() if cell not in on_path]
    junctions = "".join(
        f'<circle cx="{x * TILE + TILE / 2:g}" cy="{y * TILE + TILE / 2:g}" r="2.5"/>'
        for (x, y), t in net if sum(t) >= 3)
    (sx, sy), (gx, gy) = path[0], path[-1]
    c0, r0, c1, r1 = TEXT_BOX
    tx, ty = (c0 + c1) / 2 * TILE, (r0 + r1) / 2 * TILE
    font = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" fill="{c['bg']}" stroke="{c['border']}"/>
<path d="{segments(net)}" stroke="{c['net']}" stroke-width="2" stroke-linecap="round" fill="none"/>
<g fill="{c['net']}">{junctions}</g>
<path d="{segments((cell, grid[cell]) for cell in path)}" stroke="{c['path']}" stroke-width="3" stroke-linecap="round" fill="none"/>
<circle cx="{sx * TILE + TILE / 2:g}" cy="{sy * TILE + TILE / 2:g}" r="4" fill="{c['path']}"/>
<circle cx="{gx * TILE + TILE / 2:g}" cy="{gy * TILE + TILE / 2:g}" r="4" fill="{c['path']}"/>
<text x="{tx:g}" y="{ty - 4:g}" text-anchor="middle" font-family="{font}" font-size="30" font-weight="700" fill="{c['title']}">Tomáš Rybák</text>
<text x="{tx:g}" y="{ty + 22:g}" text-anchor="middle" font-family="{font}" font-size="13" fill="{c['sub']}">software · games · procedural generation</text>
</svg>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    grid, path = generate(args.seed)
    for theme in THEMES:
        (args.out / f"banner-{theme}.svg").write_text(render(grid, path, theme), encoding="utf-8")


if __name__ == "__main__":
    main()
