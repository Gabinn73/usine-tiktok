"""Équipes et drapeaux dessinés en formes simples (aucune image externe)."""
from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class Team:
    key: str
    name: str                 # affiché au-dessus de la balle
    orientation: str          # "v" = bandes verticales, "h" = horizontales
    stripes: tuple            # ((couleur, poids), ...)
    accent: tuple             # couleur de traînée / mise en avant


TEAMS = {
    "france": Team("france", "FRANCE", "v",
                   (((0, 85, 164), 1), ((255, 255, 255), 1), ((239, 65, 53), 1)), (60, 120, 255)),
    "italie": Team("italie", "ITALIE", "v",
                   (((0, 146, 70), 1), ((255, 255, 255), 1), ((206, 43, 55), 1)), (40, 200, 110)),
    "espagne": Team("espagne", "ESPAGNE", "h",
                    (((170, 21, 27), 1), ((241, 191, 0), 2), ((170, 21, 27), 1)), (250, 200, 30)),
    "allemagne": Team("allemagne", "ALLEMAGNE", "h",
                      (((0, 0, 0), 1), ((221, 0, 0), 1), ((255, 206, 0), 1)), (240, 60, 40)),
}
DEFAULT_TEAMS = ("france", "italie", "espagne", "allemagne")


def flag_surface(team: Team, size: int) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    total = sum(w for _, w in team.stripes)
    acc = 0
    for color, w in team.stripes:
        a = round(acc / total * size)
        acc += w
        b = round(acc / total * size)
        rect = (a, 0, b - a, size) if team.orientation == "v" else (0, a, size, b - a)
        surf.fill((*color, 255), rect)
    return surf


def flag_disc(team: Team, radius: int, ring: int = 4, ring_color=(255, 255, 255), ss: int = 4) -> pygame.Surface:
    """Disque aux couleurs du drapeau, anticrénelé par sur-échantillonnage."""
    big = radius * 2 * ss
    surf = flag_surface(team, big)
    c = big // 2
    if ring:
        pygame.draw.circle(surf, (*ring_color, 255), (c, c), c, ring * ss)
    mask = pygame.Surface((big, big), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), c)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return pygame.transform.smoothscale(surf, (radius * 2, radius * 2))
