"""Génération déterministe du parcours à partir d'un RNG seedé.

Repère : x de 0 à WIDTH, y vers le bas. Bords intérieurs des murs : x=WALL et x=WIDTH-WALL.

Règles de géométrie (aucune intervention artificielle n'existe : c'est le parcours qui doit
garantir qu'aucune balle ne se bloque) :
- aucune surface plate : rampes et tapis inclinés d'au moins 10°, entonnoirs ≥ 30° ;
- aucun écart « piège » entre ~0 et le diamètre de la plus grosse balle (on vise ≥ 100 px) ;
- les seuls arrêts possibles sont visibles et brefs (porte fermée < 1 s).
"""
import math
import random
from dataclasses import dataclass, field

from . import config as C

W = C.WIDTH
XL, XR = C.WALL, C.WIDTH - C.WALL


@dataclass
class Course:
    segments: list = field(default_factory=list)   # ((ax, ay), (bx, by), rayon)
    pegs: list = field(default_factory=list)       # (x, y, r)
    bumpers: list = field(default_factory=list)    # (x, y, r)
    spinners: list = field(default_factory=list)   # (cx, cy, demi_longueur, épaisseur, omega, angle0)
    belts: list = field(default_factory=list)      # ((ax, ay), (bx, by), rayon, vitesse)  a=haut b=bas
    doors: list = field(default_factory=list)      # dict : charnière, longueur, cycle…
    sections: list = field(default_factory=list)   # (type, y0, y1)
    start_y: float = C.START_Y
    finish_y: float = 0.0
    height: float = 0.0


def add_pegs(c: Course, rng: random.Random, y0: float, rows: int | None = None) -> float:
    """Planche de Galton. Rangées paires : 6 picots dont 2 collés aux murs ; impaires : 5 au milieu."""
    rows = rows or rng.randint(6, 9)
    r = 13
    left, right = XL + r, XR - r
    step = (right - left) / 5            # ≈ 205 px : écart mur/picot ≈ 100 px
    sy = 112
    y = y0 + 70
    for row in range(rows):
        if row % 2 == 0:
            xs = [left + i * step for i in range(6)]
            jit = [0] + [rng.uniform(-10, 10) for _ in range(4)] + [0]
        else:
            xs = [left + step / 2 + i * step for i in range(5)]
            jit = [rng.uniform(-6, 6) for _ in range(5)]
        for x, j in zip(xs, jit):
            c.pegs.append((x + j, y + rng.uniform(-6, 6), r))
        y += sy
    c.sections.append(("picots", y0, y))
    return y + 40


def _ramps(rng, y0, n, slope_deg, gap=250, between=125, rad=8):
    """Rampes alternées d'un mur à l'autre ; le trou (gap) est contre le mur côté bas."""
    out, lips = [], []
    y = y0 + 60
    to_right = rng.random() < 0.5
    length = (XR - XL) - gap - 70
    drop = math.tan(math.radians(slope_deg)) * length
    lip_w, lip_h = 70, 60
    for _ in range(n):
        # lèvre à ~40° contre le mur : une balle qui tombe le long du mur est relancée
        # immédiatement dans la pente au lieu de patiner dans le coin
        if to_right:
            a, b = (XL + lip_w, y), (XR - gap, y + drop)
            lips.append(((XL - rad, y - lip_h), a, rad))
        else:
            a, b = (XR - lip_w, y), (XL + gap, y + drop)
            lips.append(((XR + rad, y - lip_h), a, rad))
        out.append((a, b, rad))
        y += drop + between
        to_right = not to_right
    return out, lips, y


def add_zigzag(c: Course, rng: random.Random, y0: float) -> float:
    """Rampes inclinées (16–22°) : les balles filent d'un mur à l'autre."""
    ramps, lips, y = _ramps(rng, y0, rng.randint(2, 4), rng.uniform(16, 22))
    c.segments.extend(lips + ramps)
    c.sections.append(("zigzag", y0, y))
    return y + 10


def add_belts(c: Course, rng: random.Random, y0: float) -> float:
    """Tapis roulants inclinés qui accélèrent les balles vers le bas de la pente."""
    ramps, lips, y = _ramps(rng, y0, rng.randint(2, 3), rng.uniform(12, 16), between=135)
    c.segments.extend(lips)
    speed = rng.uniform(450, 700)
    for a, b, rad in ramps:
        c.belts.append((a, b, rad, speed))
    c.sections.append(("tapis", y0, y))
    return y + 10


def add_spinners(c: Course, rng: random.Random, y0: float) -> float:
    """Rangées de barres tournantes (corps cinématiques)."""
    rows = rng.randint(2, 3)
    y = y0 + 200
    single = rng.random() < 0.5
    for _ in range(rows):
        w = rng.uniform(1.8, 2.8) * rng.choice((-1, 1))
        if single:
            c.spinners.append((W / 2 + rng.uniform(-20, 20), y, 205, 11, w, rng.uniform(0, math.pi)))
        else:
            for k, cx in enumerate((W * 0.28, W * 0.72)):
                c.spinners.append((cx, y, 145, 11, w * (1 if k == 0 else -1), rng.uniform(0, math.pi)))
        single = not single
        y += 360
    c.sections.append(("barres", y0, y))
    return y - 120


def _v_funnel(c, rng, y0, g, h, rad=9):
    cx = W / 2 + rng.uniform(-60, 60)
    yb = y0 + 40 + h
    c.segments.append(((XL - rad, y0 + 40), (cx - g / 2 - rad, yb), rad))
    c.segments.append(((XR + rad, y0 + 40), (cx + g / 2 + rad, yb), rad))
    return cx, yb


def add_funnel(c: Course, rng: random.Random, y0: float) -> float:
    """Entonnoir (≈ 2 balles de large) puis un déflecteur central."""
    cx, yb = _v_funnel(c, rng, y0, rng.randint(205, 235), 340)
    y = yb + 150
    c.pegs.append((cx + rng.uniform(-14, 14), y, 26))
    c.sections.append(("entonnoir", y0, y + 60))
    return y + 120


def add_doors(c: Course, rng: random.Random, y0: float) -> float:
    """Entonnoir fermé par une trappe qui s'ouvre et se ferme en cycle (fermée < 1 s)."""
    g = rng.randint(220, 250)
    cx, yb = _v_funnel(c, rng, y0, g, 320)
    left_hinge = rng.random() < 0.5
    hx = cx - g / 2 - 6 if left_hinge else cx + g / 2 + 6
    c.doors.append({
        "hinge": (hx, yb + 6), "length": g + 12, "thick": 9,
        "dir": 1 if left_hinge else -1,          # sens d'ouverture (vers le bas)
        "closed": rng.uniform(0.55, 0.85), "open": rng.uniform(1.0, 1.5), "move": 0.18,
        "phase": rng.uniform(0, 2.0),
    })
    y = yb + 260
    c.sections.append(("portes", y0, y))
    return y


def door_angle(d: dict, t: float) -> float:
    """Angle d'ouverture (0 = fermée, ~80° = ouverte) en fonction du temps : cycle déterministe."""
    m, cl, op = d["move"], d["closed"], d["open"]
    period = cl + op + 2 * m
    u = (t + d["phase"]) % period
    full = math.radians(82)
    if u < cl:
        k = 0.0
    elif u < cl + m:
        k = (u - cl) / m
    elif u < cl + m + op:
        k = 1.0
    else:
        k = 1.0 - (u - cl - m - op) / m
    k = k * k * (3 - 2 * k)                       # douceur
    return k * full


def add_bumpers(c: Course, rng: random.Random, y0: float) -> float:
    """Gros champignons rebondissants en quinconce."""
    rows = rng.randint(3, 4)
    r = 46
    y = y0 + 110
    for row in range(rows):
        xs = (W * 0.25, W * 0.5, W * 0.75) if row % 2 == 0 else (W * 0.375, W * 0.625)
        for x in xs:
            c.bumpers.append((x + rng.uniform(-14, 14), y + rng.uniform(-10, 10), r))
        y += 200
    c.sections.append(("bumpers", y0, y))
    return y - 40


SECTIONS = {
    "picots": add_pegs,
    "zigzag": add_zigzag,
    "tapis": add_belts,
    "barres": add_spinners,
    "entonnoir": add_funnel,
    "portes": add_doors,
    "bumpers": add_bumpers,
}
# poids de tirage : les sections « chaotiques » (retournements) un peu plus fréquentes
WEIGHTS = {"picots": 3, "zigzag": 2, "tapis": 2, "barres": 3, "entonnoir": 2, "portes": 2, "bumpers": 3}


def build_course(rng: random.Random, target_height: float = C.TARGET_HEIGHT, allowed=None) -> Course:
    allowed = [k for k in SECTIONS if allowed is None or k in allowed]
    c = Course()
    c.sections.append(("depart", 0, C.START_Y + 120))
    y = add_pegs(c, rng, C.START_Y + 120, rows=rng.randint(4, 6))
    last = "picots"
    while y < target_height:
        kinds = [k for k in allowed if k != last] or allowed
        kind = rng.choices(kinds, weights=[WEIGHTS[k] for k in kinds])[0]
        y = SECTIONS[kind](c, rng, y)
        last = kind
    # Finale chaotique : retournements possibles jusqu'au bout
    if "entonnoir" in allowed:
        y = add_funnel(c, rng, y)
    y = add_spinners(c, rng, y)
    y = add_pegs(c, rng, y, rows=4)
    c.finish_y = y + 60
    c.height = c.finish_y + 420
    # bac de réception (sous la ligne d'arrivée, légèrement en V) + murs latéraux
    c.segments.append(((XL, c.height - 70), (W / 2, c.height - 40), 10))
    c.segments.append(((W / 2, c.height - 40), (XR, c.height - 70), 10))
    c.segments.append(((0, -600), (0, c.height), C.WALL))
    c.segments.append(((W, -600), (W, c.height), C.WALL))
    return c
