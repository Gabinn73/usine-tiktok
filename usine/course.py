"""Génération déterministe du parcours à partir d'un RNG seedé.

Repère : x de 0 à WIDTH, y vers le bas. Les murs latéraux ont leur bord intérieur à x=WALL
et x=WIDTH-WALL. Règle d'or : aucun écart « piège » entre ~0 et le diamètre d'une balle.
"""
import math
import random
from dataclasses import dataclass, field

from . import config as C

W = C.WIDTH
XL, XR = C.WALL, C.WIDTH - C.WALL        # bords intérieurs des murs
D = 2 * C.BALL_RADIUS


@dataclass
class Course:
    segments: list = field(default_factory=list)   # ((ax, ay), (bx, by), rayon)
    pegs: list = field(default_factory=list)       # (x, y, r)
    bumpers: list = field(default_factory=list)    # (x, y, r)
    spinners: list = field(default_factory=list)   # (cx, cy, demi_longueur, épaisseur, omega, angle0)
    sections: list = field(default_factory=list)   # (type, y0, y1)
    start_y: float = C.START_Y
    finish_y: float = 0.0
    height: float = 0.0


def add_pegs(c: Course, rng: random.Random, y0: float, rows: int | None = None) -> float:
    """Planche de Galton. Rangées paires : 6 picots dont 2 collés aux murs ; impaires : 5 au milieu."""
    rows = rows or rng.randint(6, 9)
    r = 13
    left, right = XL + r, XR - r
    step = (right - left) / 5            # ≈ 205 px : écart mur/picot ≈ 100 px > diamètre
    sy = 112
    y = y0 + 70
    for row in range(rows):
        if row % 2 == 0:
            xs = [left + i * step for i in range(6)]
            jit = [0] + [rng.uniform(-12, 12) for _ in range(4)] + [0]
        else:
            xs = [left + step / 2 + i * step for i in range(5)]
            jit = [rng.uniform(-12, 12) for _ in range(5)]
        for x, j in zip(xs, jit):
            c.pegs.append((x + j, y + rng.uniform(-6, 6), r))
        y += sy
    c.sections.append(("picots", y0, y))
    return y + 40


def add_zigzag(c: Course, rng: random.Random, y0: float) -> float:
    """Rampes inclinées alternées : les balles roulent d'un mur à l'autre."""
    n = rng.randint(2, 4)
    gap = 250                     # trou en bout de rampe (≈ 3 diamètres : pas de voûte)
    drop = rng.randint(95, 135)   # dénivelé d'une rampe
    between = 200                 # chute verticale vers la rampe suivante
    rad = 8
    y = y0 + 60
    to_right = rng.random() < 0.5
    for _ in range(n):
        if to_right:   # haut à gauche, bas à droite, trou contre le mur droit
            a, b = (XL - rad, y), (XR - gap, y + drop)
        else:
            a, b = (XR + rad, y), (XL + gap, y + drop)
        c.segments.append((a, b, rad))
        y += drop + between
        to_right = not to_right
    c.sections.append(("zigzag", y0, y))
    return y + 20


def add_spinners(c: Course, rng: random.Random, y0: float) -> float:
    """Rangées de barres tournantes (corps cinématiques)."""
    rows = rng.randint(2, 3)
    y = y0 + 200
    single = rng.random() < 0.5
    for _ in range(rows):
        w = rng.uniform(1.6, 2.6) * rng.choice((-1, 1))
        if single:
            c.spinners.append((W / 2 + rng.uniform(-20, 20), y, 205, 11, w, rng.uniform(0, math.pi)))
        else:
            for k, cx in enumerate((W * 0.28, W * 0.72)):
                c.spinners.append((cx, y, 145, 11, w * (1 if k == 0 else -1), rng.uniform(0, math.pi)))
        single = not single
        y += 360
    c.sections.append(("barres", y0, y))
    return y - 120


def add_funnel(c: Course, rng: random.Random, y0: float) -> float:
    """Entonnoir étroit (≈ 2 balles de large) puis un déflecteur central."""
    g = rng.randint(172, 190)
    h = 340
    rad = 9
    cx = W / 2 + rng.uniform(-60, 60)
    c.segments.append(((XL - rad, y0 + 40), (cx - g / 2 - rad, y0 + 40 + h), rad))
    c.segments.append(((XR + rad, y0 + 40), (cx + g / 2 + rad, y0 + 40 + h), rad))
    y = y0 + 40 + h + 150
    c.pegs.append((cx + rng.uniform(-14, 14), y, 26))
    c.sections.append(("entonnoir", y0, y + 60))
    return y + 120


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
    "barres": add_spinners,
    "entonnoir": add_funnel,
    "bumpers": add_bumpers,
}


def build_course(rng: random.Random, target_height: float = C.TARGET_HEIGHT) -> Course:
    c = Course()
    c.sections.append(("depart", 0, C.START_Y + 120))
    y = add_pegs(c, rng, C.START_Y + 120, rows=rng.randint(5, 7))
    last = "picots"
    while y < target_height:
        kind = rng.choice([k for k in SECTIONS if k != last])
        y = SECTIONS[kind](c, rng, y)
        last = kind
    # Finale chaotique : entonnoir, barres, picots -> retournements possibles jusqu'au bout
    y = add_funnel(c, rng, y)
    y = add_spinners(c, rng, y)
    y = add_pegs(c, rng, y, rows=4)
    c.finish_y = y + 60
    c.height = c.finish_y + 420
    # bac de réception sous l'arrivée + murs latéraux
    c.segments.append(((XL, c.height - 40), (XR, c.height - 40), 10))
    c.segments.append(((0, -400), (0, c.height), C.WALL))
    c.segments.append(((W, -400), (W, c.height), C.WALL))
    return c
