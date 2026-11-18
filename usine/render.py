"""Rendu image par image (pygame headless)."""
import math
from pathlib import Path

import pygame
import pygame.gfxdraw

from . import config as C
from .faces import FaceState, choose, draw_face, SAD_S
from .simulation import Race
from .teams import flag_disc
from .themes import Theme

W, H = C.WIDTH, C.HEIGHT
CHUNK = 1024                       # le parcours est dessiné par tranches, à la demande


# ---------------------------------------------------------------- utilitaires
_fonts: dict[int, pygame.font.Font] = {}
_text_cache: dict = {}


def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        path = next((p for p in C.FONT_CANDIDATES if Path(p).exists()), None)
        _fonts[size] = pygame.font.Font(path, size)
    return _fonts[size]


def text(s: str, size: int, color=(255, 255, 255), outline: int = 0, ocolor=(0, 0, 0)) -> pygame.Surface:
    key = (s, size, color, outline, ocolor)
    if key not in _text_cache:
        f = font(size)
        base = f.render(s, True, color)
        if not outline:
            _text_cache[key] = base
        else:
            o = f.render(s, True, ocolor)
            surf = pygame.Surface((base.get_width() + 2 * outline, base.get_height() + 2 * outline), pygame.SRCALPHA)
            for k in range(16):
                a = 2 * math.pi * k / 16
                surf.blit(o, (outline + round(math.cos(a) * outline), outline + round(math.sin(a) * outline)))
            surf.blit(base, (outline, outline))
            _text_cache[key] = surf
    return _text_cache[key]


def fit_text(s, size, max_w, **kw):
    while size > 20:
        t = text(s, size, **kw)
        if t.get_width() <= max_w:
            return t
        size -= 4
    return text(s, size, **kw)


def blit_center(dst, src, cx, cy):
    dst.blit(src, (round(cx - src.get_width() / 2), round(cy - src.get_height() / 2)))


def aa_disc(surf, color, x, y, r):
    x, y, r = round(x), round(y), max(1, round(r))
    pygame.gfxdraw.filled_circle(surf, x, y, r, color)
    pygame.gfxdraw.aacircle(surf, x, y, r, color)


def thick_line(surf, color, a, b, r):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * r, dx / length * r
    pts = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
    pygame.gfxdraw.filled_polygon(surf, pts, color)
    pygame.gfxdraw.aapolygon(surf, pts, color)
    aa_disc(surf, color, ax, ay, r)
    aa_disc(surf, color, bx, by, r)


def clip_segment(a, b, ymin, ymax):
    """Découpe le segment [a, b] à la bande ymin..ymax (None s'il est hors bande)."""
    (ax, ay), (bx, by) = a, b
    if max(ay, by) < ymin or min(ay, by) > ymax:
        return None
    if ay == by:
        return a, b
    def at(y):
        t = (y - ay) / (by - ay)
        return (ax + (bx - ax) * t, y)
    lo, hi = (a, b) if ay < by else (b, a)
    if lo[1] < ymin:
        lo = at(ymin)
    if hi[1] > ymax:
        hi = at(ymax)
    return lo, hi


def rounded_panel(w, h, color=(0, 0, 0, 150), radius=22):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (0, 0, w, h), border_radius=radius)
    return s


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _hash01(*vals) -> float:
    """Pseudo-aléatoire déterministe pour le décor (aucun RNG global)."""
    h = 2166136261
    for v in vals:
        h = ((h ^ (int(v) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


# ---------------------------------------------------------------- renderer
class Renderer:
    ROW_H = 60
    PANEL_X, PANEL_Y, PANEL_W = 26, 150, 480

    def __init__(self, race: Race, theme: Theme):
        pygame.font.init()
        self.race = race
        self.theme = theme
        self.course = race.course
        self.screen = pygame.Surface((W, H))
        self._chunks: dict[int, pygame.Surface] = {}
        nt = len(race.teams)
        self.discs = {(ti, t.radius): flag_disc(t, t.radius, ring_color=theme.ring)
                      for ti, t in enumerate(race.teams)}
        self._rot_cache = {}
        self.mini = [flag_disc(t, 20, ring=2) for t in race.teams]
        self.labels = [text(t.name, 30, outline=4) for t in race.teams]
        self.faces = [FaceState() for _ in race.balls]
        self.trails = [[] for _ in race.balls]
        self.rank_pos = [float(i) for i in range(nt)]
        self.prev_rank = list(race.ranking())
        self.sad_until = [-1.0] * nt
        self.cam = 0.0
        self.cams: list[float] = []            # position caméra par image (pour l'audio)
        self.panel = rounded_panel(self.PANEL_W, 20 + nt * self.ROW_H)

    # ---------------------------------------------------------- parcours (par tranches)
    def _chunk(self, k: int) -> pygame.Surface:
        if k in self._chunks:
            return self._chunks[k]
        while len(self._chunks) > 4:                       # on oublie la tranche la plus lointaine
            self._chunks.pop(max(self._chunks, key=lambda c: abs(c - k)))
        th, c = self.theme, self.course
        y0 = k * CHUNK
        s = pygame.Surface((W, CHUNK))
        s.fill(th.bg[0])
        secs = c.sections + [("fin", c.sections[-1][2], c.height + 2000)]
        for i, (_, a, b) in enumerate(secs):
            if b > y0 and a < y0 + CHUNK:
                s.fill(th.bg[i % len(th.bg)], (0, int(a - y0), W, int(b - a) + 1))
        self._pattern(s, y0)

        def off(p):
            return (p[0], p[1] - y0)

        def vis(ya, yb, m=80):
            return max(ya, yb) + m > y0 and min(ya, yb) - m < y0 + CHUNK

        for a, b, r in c.segments:
            seg = clip_segment(a, b, y0 - 100, y0 + CHUNK + 100)
            if seg:
                thick_line(s, th.wall, off(seg[0]), off(seg[1]), r)
        for a, b, r, _ in c.belts:
            seg = clip_segment(a, b, y0 - 100, y0 + CHUNK + 100)
            if seg:
                thick_line(s, th.belt, off(seg[0]), off(seg[1]), r + 3)
        for x, y, r in c.bumpers:
            if vis(y, y):
                aa_disc(s, th.bumper, x, y - y0, r)
                aa_disc(s, th.bumper_in, x, y - y0, r * 0.55)
        for x, y, r in c.pegs:
            if vis(y, y):
                aa_disc(s, th.peg_ring, x, y - y0, r + 3)
                aa_disc(s, th.peg, x, y - y0, r)
        fy = c.finish_y - y0
        if -200 < fy < CHUNK + 200:
            sq = 30
            for i in range(W // sq + 1):
                for j in range(2):
                    col = (245, 245, 245) if (i + j) % 2 == 0 else (20, 20, 20)
                    s.fill(col, (i * sq, fy - sq + j * sq, sq, sq))
            blit_center(s, text("ARRIVÉE", 64, th.accent, outline=5), W / 2, fy - 90)
        self._chunks[k] = s
        return s

    def _pattern(self, s, y0):
        col, p = self.theme.pattern_col, self.theme.pattern
        if p == "grille":
            for y in range(-(y0 % 120), CHUNK, 120):
                pygame.draw.line(s, col, (0, y), (W, y), 1)
            for x in range(0, W, 120):
                pygame.draw.line(s, col, (x, 0), (x, CHUNK), 1)
        elif p == "points":
            for y in range(-(y0 % 90), CHUNK, 90):
                for x in range(45 if ((y + y0) // 90) % 2 else 0, W, 90):
                    aa_disc(s, col, x, y, 6)
        elif p == "diagonales":
            for x in range(-CHUNK - (y0 % 140), W + CHUNK, 140):
                pygame.draw.line(s, col, (x, 0), (x + CHUNK, CHUNK), 14)
        elif p == "chevrons":
            for y in range(-(y0 % 160), CHUNK + 160, 160):
                for x in range(0, W + 160, 160):
                    pygame.draw.lines(s, col, False, [(x - 60, y), (x, y + 40), (x + 60, y)], 8)
        elif p in ("bulles", "etoiles"):
            k0 = y0 // 200
            for k in range(k0 - 1, k0 + CHUNK // 200 + 2):
                for j in range(4):
                    x = _hash01(k, j, 1) * W
                    y = k * 200 + _hash01(k, j, 2) * 200 - y0
                    if p == "bulles":
                        pygame.draw.circle(s, col, (x, y), 8 + _hash01(k, j, 3) * 26, 3)
                    else:
                        aa_disc(s, col, x, y, 1 + _hash01(k, j, 3) * 2.5)

    def blit_course(self, cam: int):
        k0 = cam // CHUNK
        for k in (k0, k0 + 1, k0 + 2):
            top = k * CHUNK - cam
            if top < H and top + CHUNK > 0:
                self.screen.blit(self._chunk(k), (0, top))

    # ---------------------------------------------------------- caméra
    def update_camera(self, snap=False):
        r = self.race
        rk = r.ranking()
        if r.winner is not None:
            focus = r.course.finish_y - 200
        else:
            y1 = r.team_progress(rk[0])
            y2 = r.team_progress(rk[1]) if len(rk) > 1 else y1
            focus = (y1 + y2) / 2 if y1 - y2 < H * 0.55 else y1 - H * 0.18
        target = min(max(focus - H * 0.5, 0), r.course.height - H)
        self.cam = target if snap else self.cam + (target - self.cam) * 0.12
        self.cams.append(self.cam)

    # ---------------------------------------------------------- monde
    def _ball_img(self, ti, r, angle):
        q = round(-math.degrees(angle) / 7.5) % 48
        key = (ti, r, q)
        if key not in self._rot_cache:
            self._rot_cache[key] = pygame.transform.rotozoom(self.discs[(ti, r)], q * 7.5, 1.0)
        return self._rot_cache[key]

    def draw_world(self):
        race, th, s = self.race, self.theme, self.screen
        cam = round(self.cam)
        self.blit_course(cam)
        t = race.time
        # tapis : chevrons qui défilent dans le sens du tapis
        for a, b, rad, speed in self.course.belts:
            if max(a[1], b[1]) < cam - 50 or min(a[1], b[1]) > cam + H + 50:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            ux, uy = dx / L, dy / L
            nx, ny = -uy, ux
            d = (t * speed * 0.35) % 46
            while d < L:
                px, py = a[0] + ux * d, a[1] + uy * d - cam
                pts = [(px - ux * 6 + nx * 6, py - uy * 6 + ny * 6), (px + ux * 4, py + uy * 4),
                       (px - ux * 6 - nx * 6, py - uy * 6 - ny * 6)]
                pygame.draw.lines(s, th.belt_mark, False, pts, 3)
                d += 46
        for body, half, thick in race.spinner_bodies:
            cx, cy = body.position
            if -300 < cy - cam < H + 300:
                dx, dy = math.cos(body.angle) * half, math.sin(body.angle) * half
                thick_line(s, th.spinner, (cx - dx, cy - dy - cam), (cx + dx, cy + dy - cam), thick)
                aa_disc(s, th.hub, cx, cy - cam, 8)
        for body, d in race.door_bodies:
            hx, hy = body.position
            if -300 < hy - cam < H + 300:
                L = d["length"] * d["dir"]
                ex, ey = hx + math.cos(body.angle) * L, hy + math.sin(body.angle) * L
                col = th.door_closed if abs(body.angle) < math.radians(12) else th.door_open
                thick_line(s, col, (hx, hy - cam), (ex, ey - cam), d["thick"])
                aa_disc(s, th.hub, hx, hy - cam, 11)
                aa_disc(s, col, hx, hy - cam, 6)

        rk = race.ranking()
        rank_of = {ti: k for k, ti in enumerate(rk)}
        order = sorted(range(len(race.balls)), key=lambda i: -rank_of[race.ball_team[i]])
        for i in order:                                   # traînées (équipes d'une balle)
            team = race.teams[race.ball_team[i]]
            if team.balls > 1:
                continue
            tr = self.trails[i]
            for k, (tx, ty) in enumerate(tr):
                if -50 < ty - cam < H + 50:
                    aa_disc(s, team.accent, tx, ty - cam, team.radius * (0.2 + 0.45 * k / max(1, len(tr))))
        leader_team = rk[0] if race.winner is None else race.winner
        for i in order:                                   # balles + yeux
            b = race.balls[i]
            ti, r = race.ball_team[i], race.ball_radius[i]
            x, y = b.position.x, b.position.y - cam
            if not (-r - 10 < y < H + r + 10):
                continue
            blit_center(s, self._ball_img(ti, r, b.angle), x, y)
            st = self.faces[i]
            vx, vy = b.velocity
            choose(st, t, vx, vy, race.last_hit[i], ti == leader_team, t < self.sad_until[ti])
            draw_face(s, x, y, r, st, blink=((race.frame + i * 37) % 113) < 4)
        placed = []                                       # étiquettes sans chevauchement
        for ti in rk:
            i = race.team_lead_ball(ti)
            b = race.balls[i]
            x, y = b.position.x, b.position.y - cam
            if not (-120 < y < H + 120):
                continue
            lab = self.labels[ti]
            lx = min(max(x, lab.get_width() / 2 + 8), W - lab.get_width() / 2 - 8)
            rect = lab.get_rect(center=(round(lx), round(y - race.ball_radius[i] - 24)))
            while any(rect.colliderect(o) for o in placed):
                rect.move_ip(0, -(rect.height - 6))
            placed.append(rect)
            s.blit(lab, rect)

    def update_trails(self):
        for i, b in enumerate(self.race.balls):
            if self.race.teams[self.race.ball_team[i]].balls > 1:
                continue
            t = self.trails[i]
            t.append((b.position.x, b.position.y))
            if len(t) > 7:
                t.pop(0)

    def update_moods(self):
        """Une équipe qui perd une place est triste pendant SAD_S secondes."""
        r = self.race
        rk = r.ranking()
        if r.time > 1.0 and r.winner is None:
            for new_pos, ti in enumerate(rk):
                if new_pos > self.prev_rank.index(ti):
                    self.sad_until[ti] = r.time + SAD_S
        self.prev_rank = list(rk)

    # ---------------------------------------------------------- HUD
    def draw_ranking(self, snap=False):
        s, r, th = self.screen, self.race, self.theme
        rk = r.ranking()
        s.blit(self.panel, (self.PANEL_X, self.PANEL_Y))
        for place, ti in enumerate(rk):
            self.rank_pos[ti] = place if snap else self.rank_pos[ti] + (place - self.rank_pos[ti]) * 0.25
        for place, ti in sorted(enumerate(rk), key=lambda p: -p[0]):
            y = self.PANEL_Y + 10 + self.rank_pos[ti] * self.ROW_H
            x = self.PANEL_X + 14
            if place == 0:
                pygame.draw.rect(s, th.accent, (x - 4, y, self.PANEL_W - 20, self.ROW_H - 6), 3, border_radius=14)
            cy = y + (self.ROW_H - 6) / 2
            blit_center(s, text(f"{place + 1}", 34, th.accent if place == 0 else (255, 255, 255)), x + 22, cy)
            blit_center(s, self.mini[ti], x + 72, cy)
            name = text(r.teams[ti].name, 30)
            s.blit(name, (x + 104, cy - name.get_height() / 2))
            team = r.teams[ti]
            info = None
            if ti in r.finish_times:
                info = text(f"✓ {r.finish_times[ti]:.2f}s", 24, (140, 255, 160))
            elif team.quota > 1:
                info = text(f"{r.team_crossed[ti]}/{team.quota}", 26)
            if info:
                s.blit(info, (self.PANEL_X + self.PANEL_W - info.get_width() - 18, cy - info.get_height() / 2))

    def draw_hook(self):
        """Question d'accroche : visible dès la 1re image, s'efface vers 3 s."""
        t = self.race.time
        if t >= C.HOOK_S:
            return
        alpha = 255 if t < C.HOOK_S - 0.5 else round(255 * (C.HOOK_S - t) / 0.5)
        q = self.race.team_set.question
        l1 = fit_text(q[0], 76, W - 100, color=(255, 255, 255), outline=7)
        l2 = fit_text(q[1], 76, W - 100, color=self.theme.accent, outline=7)
        h = l1.get_height() + l2.get_height() + 50
        layer = pygame.Surface((W, h), pygame.SRCALPHA)
        layer.blit(rounded_panel(W - 40, h, (0, 0, 0, 140), radius=30), (20, 0))
        blit_center(layer, l1, W / 2, 25 + l1.get_height() / 2)
        blit_center(layer, l2, W / 2, 25 + l1.get_height() + l2.get_height() / 2)
        layer.set_alpha(alpha)
        self.screen.blit(layer, (0, 1300))     # sous les balles, au-dessus de l'interface TikTok

    # ---------------------------------------------------------- écrans
    def draw_race(self, first=False):
        self.update_trails()
        self.update_moods()
        self.update_camera(snap=first)
        self.draw_world()
        self.draw_ranking(snap=first)
        self.draw_hook()

    def draw_winner(self, snapshot: pygame.Surface, f: int):
        r, s, th = self.race, self.screen, self.theme
        w = r.winner
        team = r.teams[w]
        t = f / C.FPS
        s.blit(snapshot, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, min(190, round(190 * t / 0.3))))
        s.blit(dim, (0, 0))
        cx, cy = W / 2, 880
        rays = pygame.Surface((W, H), pygame.SRCALPHA)
        for k in range(14):
            a0 = t * 0.6 + k * 2 * math.pi / 14
            pts = [(cx, cy), (cx + math.cos(a0) * 1400, cy + math.sin(a0) * 1400),
                   (cx + math.cos(a0 + 0.17) * 1400, cy + math.sin(a0 + 0.17) * 1400)]
            pygame.draw.polygon(rays, (*team.accent, 55), pts)
        s.blit(rays, (0, 0))
        blit_center(s, text("VAINQUEUR !", 110, th.accent, outline=8), W / 2, 520)
        if not hasattr(self, "_big"):
            self._big = flag_disc(team, 190, ring=8)
            face = FaceState()
            face.expr = "content"
            draw_face(self._big, 190, 190, 190, face, False)
        scale = max(0.05, ease_out_back(min(1.0, t / 0.4)))
        blit_center(s, pygame.transform.rotozoom(self._big, 0, scale), cx, cy)
        blit_center(s, fit_text(team.name, 120, W - 80, color=(255, 255, 255), outline=8), W / 2, 1170)
        rk = r.ranking()
        for k, ti in enumerate(rk[1:6], start=2):
            other = r.teams[ti]
            if ti in r.finish_times:
                line = f"{k}. {other.name}   +{r.finish_times[ti] - r.finish_times[w]:.2f}s"
            elif other.quota > 1:
                line = f"{k}. {other.name}   {r.team_crossed[ti]}/{other.quota} arrivées"
            else:
                line = f"{k}. {other.name}"
            blit_center(s, text(line, 38, (230, 230, 230), outline=3), W / 2, 1265 + (k - 2) * 52)
        cta = text("COMMENTE TON CAMP ↓", 54, (255, 255, 255), outline=6)
        pill = rounded_panel(cta.get_width() + 60, cta.get_height() + 30, (*team.accent, 230), radius=40)
        ycta = 1265 + max(1, len(rk) - 1) * 52 + 60
        blit_center(s, pill, W / 2, ycta)
        blit_center(s, cta, W / 2, ycta)
