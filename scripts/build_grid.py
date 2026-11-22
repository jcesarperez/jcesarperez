"""Build assets/grid.svg: the contribution graph comes alive (Conway's Game of Life),
speeds up, turns into a maze, and a chomper runs through it chased by ghosts.

Usage: python3 scripts/build_grid.py
Input:  assets/contributions.json (fixed snapshot, so the animation is always the same)
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "assets/contributions.json").read_text())
COUNTS = DATA["weeks"]  # COUNTS[x][y], x = week, y = weekday
W, H = len(COUNTS), 7

CELL, GAP = 11, 3
PITCH = CELL + GAP
PAD = 2
VW, VH = W * PITCH - GAP + 2 * PAD, H * PITCH - GAP + 2 * PAD

DELAY = 3.0             # real graph stays still before anything moves
REST = 10.0            # real graph stays still between loops (tail + next DELAY)
LIFE_START, LIFE_END = DELAY + 2.0, DELAY + 8.6
MAZE_IN = DELAY + 8.6           # walls sweep in
CHASE_START = DELAY + 9.3
FADE_OUT, FADE_END = DELAY + 15.2, DELAY + 15.7
T = FADE_END + REST - DELAY     # one loop; repeats forever

EMPTY = "#ebedf0"
LEVELS = ["#9be9a8", "#40c463", "#30a14e", "#216e39"]
WALL = "#216e39"
DOT = "#30a14e"
CHOMPER = "#f2b705"
GHOSTS = ["#cf222e", "#8250df", "#0969da"]
INK = "#1f2328"


def kt(t):
    return f"{t / T:.4f}"


def cx(x):
    return PAD + x * PITCH + CELL / 2


def cell_path(x, y):
    """Rounded square as a compact relative path."""
    r = 2
    s = CELL - 2 * r
    x0, y0 = PAD + x * PITCH + r, PAD + y * PITCH
    return (f"M{x0} {y0}h{s}a{r} {r} 0 0 1 {r} {r}v{s}a{r} {r} 0 0 1 -{r} {r}"
            f"h-{s}a{r} {r} 0 0 1 -{r} -{r}v-{s}a{r} {r} 0 0 1 {r} -{r}z")


def show_between(a, b):
    """Discrete opacity animation: visible from a to b within the loop."""
    if b >= T:
        return (f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
                f'calcMode="discrete" keyTimes="0;{kt(a)}" values="0;1"/>')
    return (f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="0;{kt(a)};{kt(b)}" values="0;1;0"/>')


# ---------- 1. Real graph ----------
def level(c):
    if c == 0:
        return None
    nz = sorted(v for col in COUNTS for v in col if v > 0)
    q = [nz[int(len(nz) * f)] for f in (0.25, 0.5, 0.75)]
    return sum(c > t for t in q)


real = {i: [] for i in range(4)}
for x in range(W):
    for y in range(H):
        lv = level(COUNTS[x][y])
        if lv is not None:
            real[lv].append(cell_path(x, y))

# ---------- 2. Game of Life ----------
grid = [[1 if COUNTS[x][y] > 0 else 0 for y in range(H)] for x in range(W)]
age = [[1 if grid[x][y] else 0 for y in range(H)] for x in range(W)]


def step(g, a):
    ng = [[0] * H for _ in range(W)]
    na = [[0] * H for _ in range(W)]
    for x in range(W):
        for y in range(H):
            n = sum(g[(x + dx) % W][(y + dy) % H]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
            alive = (g[x][y] and n in (2, 3)) or (not g[x][y] and n == 3)
            ng[x][y] = int(alive)
            na[x][y] = a[x][y] + 1 if alive else 0
    return ng, na


GENS = 42
# Geometric durations: each generation a bit faster than the previous one.
first = 0.42
lo, hi = 0.5, 0.999
for _ in range(60):
    r = (lo + hi) / 2
    total = first * (1 - r ** GENS) / (1 - r)
    lo, hi = (lo, r) if total > LIFE_END - LIFE_START else (r, hi)
durations = [first * r ** i for i in range(GENS)]

frames = []
t = LIFE_START
for i in range(GENS):
    grid, age = step(grid, age)
    by_level = {k: [] for k in range(4)}
    for x in range(W):
        for y in range(H):
            if grid[x][y]:
                by_level[min(age[x][y], 4) - 1].append(cell_path(x, y))
    frames.append((t, t + durations[i], by_level))
    t += durations[i]

# ---------- 3. Maze ----------
CONN_ROW2 = {6, 14, 22, 30, 38, 46}
CONN_ROW4 = {10, 18, 30, 42}


def is_wall(x, y):
    if y in (0, 6):
        return True
    if y == 2:
        return x not in CONN_ROW2
    if y == 4:
        return x not in CONN_ROW4
    return False


# Chomper route (cell coordinates), entering and leaving off-screen on row 3.
waypoints = [(-2, 3), (14, 3), (14, 1), (30, 1), (30, 5), (42, 5), (42, 3), (W + 1, 3)]
route_pts = [(cx(x), cx(y)) for x, y in waypoints]
seg = [math.dist(route_pts[i], route_pts[i + 1]) for i in range(len(route_pts) - 1)]
L = sum(seg)
route_d = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in route_pts)

LAGS = [3.2, 5.6, 8.0]          # ghost distance behind the chomper, in cells
speed = (L + LAGS[-1] * PITCH) / (FADE_OUT - 0.15 - CHASE_START)  # px/s


def dist_along(x, y):
    """Distance along the route to the centre of cell (x, y), or None if off-route."""
    p = (cx(x), cx(y))
    acc = 0.0
    for i in range(len(route_pts) - 1):
        (ax, ay), (bx, by) = route_pts[i], route_pts[i + 1]
        if (min(ax, bx) - 0.1 <= p[0] <= max(ax, bx) + 0.1 and
                min(ay, by) - 0.1 <= p[1] <= max(ay, by) + 0.1):
            return acc + math.dist((ax, ay), p)
        acc += seg[i]
    return None


walls, dots = [], []
for x in range(W):
    for y in range(H):
        sweep = MAZE_IN + 0.5 * x / W
        if is_wall(x, y):
            walls.append((sweep, cell_path(x, y)))
        else:
            s = dist_along(x, y)
            gone = CHASE_START + s / speed if s is not None else FADE_OUT
            dots.append((sweep, gone, cx(x), cx(y)))

# ---------- SVG ----------
out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VW} {VH}" width="{VW}" height="{VH}" '
       f'role="img" aria-label="My contribution graph comes alive, speeds up and turns into a maze chase">']
out.append(f'<rect width="{VW}" height="{VH}" fill="#ffffff"/>')

# Static empty grid
out.append(f'<path fill="{EMPTY}" d="' + "".join(cell_path(x, y) for x in range(W) for y in range(H)) + '"/>')

# Real graph: visible at the start, fades back in at the end of the loop
out.append('<g>')
out.append(f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
           f'keyTimes="0;{kt(LIFE_START)};{kt(LIFE_START + 0.001)};{kt(FADE_END)};1" values="1;1;0;0;1"/>')
for lv, paths in real.items():
    if paths:
        out.append(f'<path fill="{LEVELS[lv]}" d="{"".join(paths)}"/>')
out.append('</g>')

# Life frames
for a, b, by_level in frames:
    out.append(f'<g opacity="0">{show_between(a, b)}')
    for lv, paths in by_level.items():
        if paths:
            out.append(f'<path fill="{LEVELS[lv]}" d="{"".join(paths)}"/>')
    out.append('</g>')

# Maze (walls + dots), faded out together at the end
out.append('<g>')
out.append(f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
           f'keyTimes="0;{kt(FADE_OUT)};{kt(FADE_END)};1" values="1;1;0;0"/>')
for sweep, d in walls:
    out.append(f'<path fill="{WALL}" opacity="0" d="{d}">{show_between(sweep, T)}</path>')
for sweep, gone, px, py in dots:
    out.append(f'<circle cx="{px}" cy="{py}" r="1.6" fill="{DOT}" opacity="0">{show_between(sweep, gone)}</circle>')
out.append('</g>')


def motion(lag_cells, rotate):
    start = CHASE_START + lag_cells * PITCH / speed
    end = start + L / speed
    return (f'<animateMotion dur="{T}s" repeatCount="indefinite" path="{route_d}" rotate="{rotate}" '
            f'calcMode="linear" keyPoints="0;0;1;1" keyTimes="0;{kt(start)};{kt(end)};1"/>')


# Ghosts (drawn first so the chomper stays on top)
ghost_d = "M-5.5 5.5V-.5a5.5 5.5 0 0 1 11 0V5.5L3.7 3.6 1.8 5.5 0 3.6-1.8 5.5-3.7 3.6z"
for lag, colour in zip(LAGS, GHOSTS):
    out.append(f'<g>{motion(lag, "0")}'
               f'<path fill="{colour}" d="{ghost_d}"/>'
               f'<circle cx="-2.1" cy="-.8" r="1.7" fill="#fff"/><circle cx="2.1" cy="-.8" r="1.7" fill="#fff"/>'
               f'<circle cx="-1.4" cy="-.8" r=".85" fill="{INK}"/><circle cx="2.8" cy="-.8" r=".85" fill="{INK}"/>'
               f'</g>')


def wedge(deg, r=6.2):
    a = math.radians(deg)
    x, y = r * math.cos(a), r * math.sin(a)
    return f"M0 0L{x:.2f} {-y:.2f}A{r} {r} 0 1 0 {x:.2f} {y:.2f}z"


out.append(f'<g>{motion(0, "auto")}'
           f'<path fill="{CHOMPER}" d="{wedge(40)}">'
           f'<animate attributeName="d" dur=".22s" repeatCount="indefinite" '
           f'values="{wedge(40)};{wedge(4)};{wedge(40)}"/></path></g>')

out.append('</svg>')
svg = "\n".join(out)
(ROOT / "assets/grid.svg").write_text(svg)
print(f"assets/grid.svg: {len(svg) / 1024:.0f} KB, {GENS} generations, chase speed {speed / PITCH:.1f} cells/s")
