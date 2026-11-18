"""Équipes, jeux d'équipes (config/equipes.toml) et drapeaux dessinés en formes simples."""
import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pygame

from . import config as C

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "equipes.toml"


def hex2rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@dataclass(frozen=True)
class Team:
    name: str
    pattern: str
    colors: tuple
    weights: tuple
    balls: int = 1
    radius: int = C.BALL_RADIUS
    quota: int = 1                # balles à faire arriver pour que l'équipe soit arrivée

    @property
    def accent(self):
        """Couleur la plus « vive » du drapeau (traînée, rayons, CTA)."""
        def vivid(c):
            mx, mn = max(c), min(c)
            return (mx - mn) * 2 + mx
        return max(self.colors, key=vivid)


@dataclass(frozen=True)
class TeamSet:
    key: str
    question: tuple
    min: int
    max: int
    teams: tuple
    sections: tuple | None = None  # sections de parcours autorisées (None = toutes)
    length: float = 1.0            # multiplicateur de longueur du parcours

    def pick(self, rng: random.Random, n: int | None = None) -> list[Team]:
        drawn = rng.randint(self.min, min(self.max, len(self.teams)))   # toujours tiré : même suite aléatoire
        n = max(self.min, min(n or drawn, self.max, len(self.teams)))
        if self.min == self.max == len(self.teams):
            return list(self.teams)
        return rng.sample(list(self.teams), n)


def load_sets(path=CONFIG_PATH) -> dict[str, TeamSet]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    sets = {}
    for key, js in data["jeux"].items():
        teams = []
        for e in js["equipes"]:
            cols = tuple(hex2rgb(c) for c in e["couleurs"])
            teams.append(Team(
                name=e["nom"], pattern=e.get("motif", "v"), colors=cols,
                weights=tuple(e.get("poids", [1] * len(cols))),
                balls=int(e.get("balles", 1)), radius=int(e.get("rayon", C.BALL_RADIUS)),
                quota=int(e.get("quota", 1)),
            ))
        secs = tuple(js["sections"]) if "sections" in js else None
        sets[key] = TeamSet(key, tuple(js["question"]), int(js["min"]), int(js["max"]), tuple(teams), secs, float(js.get("longueur", 1.0)))
    return sets


SETS = load_sets()


# ------------------------------------------------------------------ dessin
def flag_surface(team: Team, size: int) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cols = team.colors
    p = team.pattern
    if p in ("v", "h"):
        total = sum(team.weights)
        acc = 0
        for color, w in zip(cols, team.weights):
            a = round(acc / total * size)
            acc += w
            b = round(acc / total * size)
            s.fill((*color, 255), (a, 0, b - a, size) if p == "v" else (0, a, size, b - a))
    elif p == "croix":
        s.fill((*cols[0], 255))
        arm, th = size * 0.62, size * 0.2
        c = size / 2
        s.fill((*cols[1], 255), (c - th / 2, c - arm / 2, th, arm))
        s.fill((*cols[1], 255), (c - arm / 2, c - th / 2, arm, th))
    elif p == "nordique":
        s.fill((*cols[0], 255))
        cx, cy = size * 0.4, size / 2
        th = size * 0.22
        s.fill((*cols[1], 255), (cx - th / 2, 0, th, size))
        s.fill((*cols[1], 255), (0, cy - th / 2, size, th))
        if len(cols) > 2:
            th2 = th * 0.5
            s.fill((*cols[2], 255), (cx - th2 / 2, 0, th2, size))
            s.fill((*cols[2], 255), (0, cy - th2 / 2, size, th2))
    elif p == "moitie":
        s.fill((*cols[0], 255))
        pygame.draw.polygon(s, (*cols[1], 255), [(size, 0), (size, size), (0, size)])
    else:  # uni : léger reflet pour qu'on voie la balle rouler
        s.fill((*cols[0], 255))
        light = tuple(min(255, v + 70) for v in cols[0])
        pygame.draw.circle(s, (*light, 255), (size * 0.5, size * 0.18), size * 0.16)
    return s


def flag_disc(team: Team, radius: int, ring: int | None = None, ring_color=(255, 255, 255), ss: int = 4) -> pygame.Surface:
    """Disque aux couleurs du drapeau, anticrénelé par sur-échantillonnage."""
    ring = max(1, round(radius / 11)) if ring is None else ring
    big = radius * 2 * ss
    surf = flag_surface(team, big)
    c = big // 2
    if ring:
        pygame.draw.circle(surf, (*ring_color, 255), (c, c), c, ring * ss)
    mask = pygame.Surface((big, big), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return pygame.transform.smoothscale(surf, (radius * 2, radius * 2))
