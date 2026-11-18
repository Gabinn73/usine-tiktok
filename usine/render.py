"""Rendu image par image (pygame headless) et assemblage de la vidéo."""
import math
from pathlib import Path

import pygame
import pygame.gfxdraw

from . import config as C
from .encoder import Encoder
from .simulation import Race
from .teams import flag_disc

W, H = C.WIDTH, C.HEIGHT


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


def blit_center(dst, src, cx, cy):
    dst.blit(src, (round(cx - src.get_width() / 2), round(cy - src.get_height() / 2)))


def aa_disc(surf, color, x, y, r):
    x, y, r = round(x), round(y), round(r)
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


def rounded_panel(w, h, color=(0, 0, 0, 150), radius=22):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (0, 0, w, h), border_radius=radius)
    return s


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


# ---------------------------------------------------------------- renderer
class Renderer:
    ROW_H = 64
    PANEL_X, PANEL_Y, PANEL_W = 26, 150, 470

    def __init__(self, race: Race):
        pygame.font.init()
        self.race = race
        self.course = race.course
        self.screen = pygame.Surface((W, H))
        self.course_surf = self._draw_course()
        n = len(race.teams)
        self.discs = [flag_disc(t, C.BALL_RADIUS) for t in race.teams]
        self.mini = [flag_disc(t, 21, ring=2) for t in race.teams]
        self.labels = [text(t.name, 32, outline=4) for t in race.teams]
        self.trails = [[] for _ in range(n)]
        self.rank_pos = [float(i) for i in range(n)]
        self.cam = 0.0
        self._label_rects = {}
        self.panel = rounded_panel(self.PANEL_W, 24 + n * self.ROW_H)

    # -- parcours statique (dessiné une seule fois)
    def _draw_course(self) -> pygame.Surface:
        c = self.course
        hh = int(math.ceil(c.height))
        surf = pygame.Surface((W, hh))
        surf.fill(C.SECTION_BG[0])
        for k, (_, y0, y1) in enumerate(c.sections):
            surf.fill(C.SECTION_BG[k % len(C.SECTION_BG)], (0, int(y0), W, int(y1 - y0) + 1))
        if c.sections:
            surf.fill(C.SECTION_BG[len(c.sections) % len(C.SECTION_BG)], (0, int(c.sections[-1][2]), W, hh))
        # grille discrète : donne la sensation de vitesse quand la caméra défile
        for y in range(0, hh, 120):
            pygame.draw.line(surf, (40, 48, 80), (0, y), (W, y), 1)
        for x in range(0, W, 120):
            pygame.draw.line(surf, (32, 38, 66), (x, 0), (x, hh), 1)
        for a, b, r in c.segments:
            thick_line(surf, C.COL_WALL, a, b, r)
        for x, y, r in c.bumpers:
            aa_disc(surf, C.COL_BUMPER, x, y, r)
            aa_disc(surf, C.COL_BUMPER_IN, x, y, r * 0.55)
        for x, y, r in c.pegs:
            aa_disc(surf, C.COL_PEG_RING, x, y, r + 3)
            aa_disc(surf, C.COL_PEG, x, y, r)
        # ligne d'arrivée en damier
        sq = 30
        fy = int(c.finish_y)
        for i in range(W // sq + 1):
            for j in range(2):
                col = (245, 245, 245) if (i + j) % 2 == 0 else (20, 20, 20)
                surf.fill(col, (i * sq, fy - sq + j * sq, sq, sq))
        blit_center(surf, text("ARRIVÉE", 64, C.COL_GOLD, outline=5), W / 2, fy - 90)
        return surf

    # -- caméra : suit le duel pour la 1re place
    def update_camera(self, snap=False):
        r = self.race
        rk = r.ranking()
        if r.winner is not None:
            focus = r.course.finish_y - 200
        else:
            y1 = r.balls[rk[0]].position.y
            y2 = r.balls[rk[1]].position.y if len(rk) > 1 else y1
            focus = (y1 + y2) / 2 if y1 - y2 < H * 0.55 else y1 - H * 0.18
        target = min(max(focus - H * 0.5, 0), r.course.height - H)
        self.cam = target if snap else self.cam + (target - self.cam) * 0.1

    # -- dessin du monde
    def draw_world(self):
        cam = round(self.cam)
        s = self.screen
        s.blit(self.course_surf, (0, 0), pygame.Rect(0, cam, W, H))
        for body, half, thick in self.race.spinner_bodies:
            cx, cy = body.position
            if -300 < cy - cam < H + 300:
                dx, dy = math.cos(body.angle) * half, math.sin(body.angle) * half
                thick_line(s, C.COL_SPINNER, (cx - dx, cy - dy - cam), (cx + dx, cy + dy - cam), thick)
                aa_disc(s, (120, 80, 0), cx, cy - cam, 8)
        order = list(reversed(self.race.ranking()))     # le leader dessiné par-dessus
        for i in order:
            team = self.race.teams[i]
            for k, (tx, ty) in enumerate(self.trails[i]):
                rr = C.BALL_RADIUS * (0.25 + 0.5 * k / max(1, len(self.trails[i])))
                if -50 < ty - cam < H + 50:
                    aa_disc(s, team.accent, tx, ty - cam, rr)
        placed = []                                       # étiquettes déjà posées (anti-chevauchement)
        for i in reversed(order):                          # le leader garde la meilleure place
            b = self.race.balls[i]
            x, y = b.position.x, b.position.y - cam
            if not (-120 < y < H + 120):
                continue
            lab = self.labels[i]
            lx = min(max(x, lab.get_width() / 2 + 8), W - lab.get_width() / 2 - 8)
            rect = lab.get_rect(center=(round(lx), round(y - C.BALL_RADIUS - 26)))
            while any(rect.colliderect(o) for o in placed):
                rect.move_ip(0, -(rect.height - 6))
            placed.append(rect)
            self._label_rects[i] = rect
        for i in order:
            b = self.race.balls[i]
            x, y = b.position.x, b.position.y - cam
            if not (-120 < y < H + 120):
                continue
            img = pygame.transform.rotozoom(self.discs[i], -math.degrees(b.angle), 1.0)
            blit_center(s, img, x, y)
        for i in order:
            if i in self._label_rects and -120 < self.race.balls[i].position.y - cam < H + 120:
                s.blit(self.labels[i], self._label_rects[i])
        self._label_rects.clear()

    def update_trails(self):
        for i, b in enumerate(self.race.balls):
            t = self.trails[i]
            t.append((b.position.x, b.position.y))
            if len(t) > 7:
                t.pop(0)

    # -- classement en direct
    def draw_ranking(self, snap=False):
        s = self.screen
        r = self.race
        rk = r.ranking()
        s.blit(self.panel, (self.PANEL_X, self.PANEL_Y))
        for place, i in enumerate(rk):
            self.rank_pos[i] = place if snap else self.rank_pos[i] + (place - self.rank_pos[i]) * 0.25
        for place, i in sorted(enumerate(rk), key=lambda p: -p[0]):
            y = self.PANEL_Y + 12 + self.rank_pos[i] * self.ROW_H
            x = self.PANEL_X + 14
            if place == 0:
                pygame.draw.rect(s, C.COL_GOLD, (x - 4, y, self.PANEL_W - 20, self.ROW_H - 6), 3, border_radius=14)
            num_col = C.COL_GOLD if place == 0 else (255, 255, 255)
            blit_center(s, text(f"{place + 1}", 36, num_col), x + 24, y + 29)
            blit_center(s, self.mini[i], x + 78, y + 29)
            name = text(r.teams[i].name, 32)
            s.blit(name, (x + 112, y + 29 - name.get_height() / 2))
            if i in r.finish_times:
                tt = text(f"✓ {r.finish_times[i]:.2f}s", 26, (140, 255, 160))
                s.blit(tt, (self.PANEL_X + self.PANEL_W - tt.get_width() - 18, y + 29 - tt.get_height() / 2))

    # -- écrans
    def draw_countdown(self, f: int):
        n_cd = int(C.COUNTDOWN_S * C.FPS)
        self.update_camera(snap=True)
        self.draw_world()
        self.draw_ranking(snap=True)
        blit_center(self.screen, text("QUI ARRIVE EN BAS", 66, (255, 255, 255), outline=6), W / 2, 820)
        blit_center(self.screen, text("EN PREMIER ?", 66, C.COL_GOLD, outline=6), W / 2, 900)
        remaining = (n_cd - f) / C.FPS
        num = math.ceil(remaining)
        phase = 1 - (remaining - (num - 1))           # 0 -> 1 pendant chaque seconde
        big = text(str(num), 260, (255, 255, 255), outline=10)
        img = pygame.transform.rotozoom(big, 0, 1.35 - 0.35 * min(1, phase * 3))
        blit_center(self.screen, img, W / 2, 1180)

    def draw_race(self):
        self.update_trails()
        self.update_camera()
        self.draw_world()
        self.draw_ranking()
        if self.race.time < 0.9:
            go = text("GO !", 200, (120, 255, 140), outline=10).copy()
            go.set_alpha(round(255 * (1 - self.race.time / 0.9)))
            blit_center(self.screen, go, W / 2, 1100)

    def draw_winner(self, snapshot: pygame.Surface, f: int):
        r = self.race
        s = self.screen
        w = r.winner
        team = r.teams[w]
        t = f / C.FPS
        s.blit(snapshot, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, min(190, round(190 * t / 0.3))))
        s.blit(dim, (0, 0))
        cx, cy = W / 2, 880
        # rayons tournants aux couleurs du gagnant
        rays = pygame.Surface((W, H), pygame.SRCALPHA)
        for k in range(14):
            a0 = t * 0.6 + k * 2 * math.pi / 14
            pts = [(cx, cy),
                   (cx + math.cos(a0) * 1400, cy + math.sin(a0) * 1400),
                   (cx + math.cos(a0 + 0.17) * 1400, cy + math.sin(a0 + 0.17) * 1400)]
            pygame.draw.polygon(rays, (*team.accent, 55), pts)
        s.blit(rays, (0, 0))
        blit_center(s, text("VAINQUEUR !", 110, C.COL_GOLD, outline=8), W / 2, 520)
        scale = ease_out_back(min(1.0, t / 0.4))
        disc = flag_disc(team, 190, ring=8) if not hasattr(self, "_big") else self._big
        self._big = disc
        blit_center(s, pygame.transform.rotozoom(disc, 0, max(0.05, scale)), cx, cy)
        blit_center(s, text(team.name, 120, (255, 255, 255), outline=8), W / 2, 1170)
        for k, i in enumerate(r.ranking()[1:], start=2):
            if i in r.finish_times:
                line = f"{k}. {r.teams[i].name}   +{r.finish_times[i] - r.finish_times[w]:.2f}s"
            else:
                line = f"{k}. {r.teams[i].name}"
            blit_center(s, text(line, 40, (230, 230, 230), outline=3), W / 2, 1270 + (k - 2) * 58)
        cta = text("COMMENTE TON CAMP ↓", 54, (255, 255, 255), outline=6)
        pill = rounded_panel(cta.get_width() + 60, cta.get_height() + 30, (*team.accent, 230), radius=40)
        blit_center(s, pill, W / 2, 1500)
        blit_center(s, cta, W / 2, 1500)


def render_video(race: Race, out_path, log=print) -> int:
    """Rend la vidéo complète. Renvoie le nombre d'images."""
    rd = Renderer(race)
    with Encoder(out_path) as enc:
        n_cd = int(C.COUNTDOWN_S * C.FPS)
        for f in range(n_cd):
            rd.draw_countdown(f)
            enc.write(rd.screen)
        while not race.finished():
            race.step_frame()
            rd.draw_race()
            enc.write(rd.screen)
            if race.frame % (10 * C.FPS) == 0:
                log(f"  … course {race.time:5.1f}s rendue")
        if race.winner is None:
            raise RuntimeError("aucune balle n'a franchi l'arrivée")
        snapshot = rd.screen.copy()
        for f in range(int(C.WINNER_S * C.FPS)):
            rd.draw_winner(snapshot, f)
            enc.write(rd.screen)
    return enc.frames
