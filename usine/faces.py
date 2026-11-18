"""Yeux expressifs des balles, dessinés en code.

Expressions (par priorité) :
  peur     yeux écarquillés, petites pupilles, bouche en « o »  (chute rapide ou gros choc)
  triste   sourcils tombants, regard vers le bas, moue          (équipe qui vient d'être doublée)
  content  yeux plissés « ^ ^ » et sourire                     (équipe en tête / gagnante)
  normal   regard dans le sens du mouvement, clignements
"""
import math

import pygame
import pygame.gfxdraw

INK = (25, 22, 35)
WHITE = (255, 255, 255)

FALL_FAST = 1500.0        # px/s vers le bas
BIG_HIT = 1100.0          # Δv d'un « gros choc »
HIT_SHOW_S = 0.45
SAD_S = 1.6
MIN_HOLD_S = 0.3


class FaceState:
    __slots__ = ("expr", "since", "gx", "gy")

    def __init__(self):
        self.expr, self.since, self.gx, self.gy = "normal", 0.0, 0.0, 0.0


def choose(state: FaceState, t: float, vx: float, vy: float, hit, leader: bool, sad: bool) -> str:
    speed = math.hypot(vx, vy)
    # regard lissé dans le sens du mouvement
    if speed > 40:
        tx, ty = vx / speed, vy / speed
    else:
        tx, ty = 0.0, 0.25
    k = 0.35
    state.gx += (tx - state.gx) * k
    state.gy += (ty - state.gy) * k
    hit_t, hit_dv = hit
    if vy > FALL_FAST or (t - hit_t < HIT_SHOW_S and hit_dv > BIG_HIT):
        want = "peur"
    elif sad:
        want = "triste"
    elif leader:
        want = "content"
    else:
        want = "normal"
    if want != state.expr and (want == "peur" or t - state.since >= MIN_HOLD_S):
        state.expr, state.since = want, t
    return state.expr


def _disc(s, color, x, y, r):
    x, y, r = round(x), round(y), max(1, round(r))
    pygame.gfxdraw.filled_circle(s, x, y, r, color)
    pygame.gfxdraw.aacircle(s, x, y, r, color)


def _arc(s, color, cx, cy, rx, ry, a0, a1, width):
    """Arc épais (angles en radians, repère écran y vers le bas)."""
    pts = []
    n = 10
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry))
    pygame.draw.lines(s, color, False, pts, max(1, round(width)))
    for p in (pts[0], pts[-1]):
        _disc(s, color, p[0], p[1], width / 2)


def draw_face(s: pygame.Surface, x: float, y: float, r: float, state: FaceState, blink: bool):
    expr = state.expr
    small = r < 20
    ex_off, ey = r * 0.36, y - r * 0.12
    ew = r * (0.34 if expr == "peur" else 0.27)
    pr = r * (0.085 if expr == "peur" else 0.135)
    lw = max(1.5, r * 0.07)
    for side in (-1, 1):
        ex = x + side * ex_off
        if expr == "content" and not small:
            _arc(s, INK, ex, ey + ew * 0.35, ew * 0.85, ew * 0.8, math.pi * 1.1, math.pi * 1.9, lw * 1.3)
            continue
        if blink and expr == "normal" and not small:
            pygame.draw.line(s, INK, (ex - ew * 0.8, ey), (ex + ew * 0.8, ey), max(2, round(lw * 1.2)))
            continue
        _disc(s, INK, ex, ey, ew + max(1.2, lw * 0.6))
        _disc(s, WHITE, ex, ey, ew)
        gy = state.gy + (0.45 if expr == "triste" else 0.0)
        m = ew - pr - 1
        n = math.hypot(state.gx, gy) or 1.0
        f = min(1.0, n)
        _disc(s, INK, ex + state.gx / n * m * f, ey + gy / n * m * f, pr)
        if not small:
            _disc(s, WHITE, ex + state.gx / n * m * f - pr * 0.35, ey + gy / n * m * f - pr * 0.4, pr * 0.32)
        if expr == "triste" and not small:
            # sourcil : extrémité intérieure plus haute
            ox, oy = ex + side * ew * 0.9, ey - ew * 1.05
            ix, iy = ex - side * ew * 0.6, ey - ew * 1.55
            pygame.draw.line(s, INK, (ox, oy), (ix, iy), max(2, round(lw * 1.1)))
    if small:
        return
    my = y + r * 0.42
    if expr == "content":
        _arc(s, INK, x, my - r * 0.12, r * 0.24, r * 0.16, math.pi * 0.15, math.pi * 0.85, lw * 1.2)
    elif expr == "triste":
        _arc(s, INK, x, my + r * 0.08, r * 0.16, r * 0.1, math.pi * 1.2, math.pi * 1.8, lw)
    elif expr == "peur":
        _disc(s, INK, x, my, r * 0.11)
