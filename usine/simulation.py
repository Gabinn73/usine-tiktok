"""Simulation physique de la course (pymunk), sans aucun rendu.

Règle absolue : aucune force invisible, aucune limite de vitesse, aucun « coup de pouce ».
Seules la gravité, les collisions et les obstacles visibles (barres, tapis, portes) agissent.
"""
import math
import random
from dataclasses import dataclass, field, asdict

import pymunk

from . import config as C
from .course import build_course, door_angle
from .teams import SETS, Team

# types de collision (aussi utilisés pour choisir le son)
BALL, PEG, BUMPER, WALL, SPINNER, BELT, DOOR = range(1, 8)
MATERIAL = {PEG: "picot", BUMPER: "bumper", WALL: "mur", SPINNER: "barre", BELT: "tapis",
            DOOR: "porte", BALL: "balle"}


def derived_rng(seed: int, purpose: str) -> random.Random:
    """Un RNG indépendant par usage : changer le jeu d'équipes ne change pas le parcours."""
    return random.Random(f"{purpose}-{seed}")


def pick_set_key(seed: int) -> str:
    return derived_rng(seed, "jeu").choice(sorted(SETS))


@dataclass
class RaceResult:
    seed: int
    set_key: str
    teams: list
    finish_times: dict                      # nom d'équipe -> temps (s)
    order: list                             # noms dans l'ordre d'arrivée
    winner: str | None
    t_win: float | None
    gap12: float | None                     # écart 1er/2e (None si le 2e n'arrive pas à temps)
    lead_changes: list = field(default_factory=list)   # [(t, nom)]
    max_stall: float = 0.0                  # plus longue immobilisation d'une balle (s)
    stall_where: list | None = None         # (t, x, y) de cette immobilisation
    course_height: float = 0.0
    sections: list = field(default_factory=list)
    valid: bool = False
    score: float = 0.0
    reasons: list = field(default_factory=list)

    @property
    def video_s(self):
        return None if self.t_win is None else self.t_win + C.OVERHEAD_S

    def to_dict(self):
        d = asdict(self)
        d["video_s"] = self.video_s
        return d


class Race:
    def __init__(self, seed: int, set_key: str | None = None, n_teams: int | None = None):
        self.seed = seed
        self.set_key = set_key or pick_set_key(seed)
        self.team_set = SETS[self.set_key]
        self.teams: list[Team] = self.team_set.pick(derived_rng(seed, "equipes"), n_teams)
        self.course = build_course(derived_rng(seed, "parcours"), allowed=self.team_set.sections,
                                   target_height=C.TARGET_HEIGHT * self.team_set.length)

        space = pymunk.Space()
        space.gravity = (0, C.GRAVITY)
        space.iterations = 20
        self.space = space
        static = space.static_body

        def add_static(shape, ctype, elasticity, friction):
            shape.elasticity, shape.friction, shape.collision_type = elasticity, friction, ctype
            space.add(shape)
            return shape

        for a, b, r in self.course.segments:
            add_static(pymunk.Segment(static, a, b, r), WALL, 0.55, 0.35)
        for x, y, r in self.course.pegs:
            add_static(pymunk.Circle(static, r, (x, y)), PEG, 0.7, 0.2)
        for x, y, r in self.course.bumpers:
            add_static(pymunk.Circle(static, r, (x, y)), BUMPER, 1.05, 0.1)
        for a, b, r, speed in self.course.belts:
            s = add_static(pymunk.Segment(static, a, b, r), BELT, 0.3, 0.6)
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy)
            s.surface_velocity = (dx / n * speed, dy / n * speed)

        self.spinner_bodies = []
        for cx, cy, half, thick, omega, a0 in self.course.spinners:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position, body.angle, body.angular_velocity = (cx, cy), a0, omega
            s = pymunk.Segment(body, (-half, 0), (half, 0), thick)
            s.elasticity, s.friction, s.collision_type = 0.75, 0.3, SPINNER
            space.add(body, s)
            self.spinner_bodies.append((body, half, thick))

        self.door_bodies = []
        for d in self.course.doors:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = d["hinge"]
            body.angle = self._door_target(d, 0.0)
            s = pymunk.Segment(body, (0, 0), (d["length"] * d["dir"], 0), d["thick"])
            s.elasticity, s.friction, s.collision_type = 0.4, 0.4, DOOR
            space.add(body, s)
            self.door_bodies.append((body, d))

        # --- balles
        self.balls: list[pymunk.Body] = []
        self.ball_team: list[int] = []
        self.ball_radius: list[int] = []
        self._shape_ball: dict = {}
        for ti, (x, y, r) in self._start_positions(derived_rng(seed, "depart")):
            mass = (r / C.BALL_RADIUS) ** 2
            body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
            body.position = (x, y)
            s = pymunk.Circle(body, r)
            s.elasticity, s.friction, s.collision_type = C.BALL_ELASTICITY, C.BALL_FRICTION, BALL
            space.add(body, s)
            self._shape_ball[s] = len(self.balls)
            self.balls.append(body)
            self.ball_team.append(ti)
            self.ball_radius.append(r)
        self.team_balls = [[i for i, t in enumerate(self.ball_team) if t == ti] for ti in range(len(self.teams))]

        # --- collisions -> événements sonores + réactions des yeux
        self.events: list[tuple] = []           # (t, matériau, intensité Δv px/s, x, y)
        self.last_hit = [(-9.0, 0.0)] * len(self.balls)
        for other in (PEG, BUMPER, WALL, SPINNER, BELT, DOOR, BALL):
            space.on_collision(BALL, other, post_solve=self._on_hit, data=other)

        n = len(self.balls)
        self.frame = 0
        self.time = 0.0
        self.crossed = [False] * n
        self.team_crossed = [0] * len(self.teams)
        self.finish_times: dict[int, float] = {}     # équipe -> temps
        self.finish_order: list[int] = []
        self._anchor = [(b.position.x, b.position.y, 0.0) for b in self.balls]
        self.max_stall, self.stall_where = 0.0, None
        self.leader = None
        self._cand, self._cand_frames = None, 0
        self.lead_changes: list[tuple[float, int]] = []

    # ------------------------------------------------------------------
    def _start_positions(self, rng: random.Random):
        """Grosses balles réparties sur une ligne, petites balles en grille autour."""
        order = list(range(len(self.teams)))
        rng.shuffle(order)
        big = [(ti, t.radius) for ti in order for t in [self.teams[ti]] if t.balls == 1]
        small = [(ti, t.radius) for ti in order for t in [self.teams[ti]] if t.balls > 1 for _ in range(t.balls)]
        out, centers = [], []
        nb = len(big)
        for k, (ti, r) in enumerate(big):
            x = C.WIDTH * (k + 1) / (nb + 1) + rng.uniform(-25, 25)
            y = C.START_Y + rng.uniform(-12, 12)
            out.append((ti, x, y, r))
            centers.append((x, y, r))
        rng.shuffle(small)
        row, idx = 0, 0
        while idx < len(small):
            r = small[idx][1]
            y = C.START_Y + 30 - row * (2 * r + 8)
            x = C.WALL + r + 6 + (row % 2) * (r + 4)
            while x < C.WIDTH - C.WALL - r - 4 and idx < len(small):
                if all(math.hypot(x - cx, y - cy) > cr + r + 8 for cx, cy, cr in centers):
                    out.append((small[idx][0], x + rng.uniform(-3, 3), y + rng.uniform(-3, 3), r))
                    idx += 1
                x += 2 * r + 8
            row += 1
        out.sort(key=lambda p: (p[0], p[2], p[1]))      # ordre d'ajout stable
        return [(ti, (x, y, r)) for ti, x, y, r in out]

    @staticmethod
    def _door_target(d, t):
        return door_angle(d, t) * d["dir"]

    def _on_hit(self, arbiter: pymunk.Arbiter, space, other_type):
        if not arbiter.is_first_contact:
            return
        a, b = arbiter.shapes
        i = self._shape_ball.get(a)
        if i is None:
            return
        dv = arbiter.total_impulse.length / self.balls[i].mass
        if dv < 60:
            return
        p = arbiter.contact_point_set.points[0].point_a if arbiter.contact_point_set.points else self.balls[i].position
        self.events.append((self._sim_t, MATERIAL[other_type], dv, p.x, p.y))
        if dv > self.last_hit[i][1] * 0.5 or self._sim_t - self.last_hit[i][0] > 0.4:
            self.last_hit[i] = (self._sim_t, dv)
        if other_type == BALL:
            j = self._shape_ball.get(b)
            if j is not None:
                self.last_hit[j] = (self._sim_t, dv * self.balls[i].mass / self.balls[j].mass)

    # ------------------------------------------------------------------
    @property
    def winner(self):
        return self.finish_order[0] if self.finish_order else None

    def team_lead_ball(self, ti: int) -> int:
        """Balle décisive : la quota-ième plus avancée (la 1re pour une équipe normale,
        la dernière pour « les 100 doivent toutes arriver »)."""
        balls = self.team_balls[ti]
        q = min(self.teams[ti].quota, len(balls))
        if q == 1:
            return max(balls, key=lambda i: self.balls[i].position.y)
        return sorted(balls, key=lambda i: -self.balls[i].position.y)[q - 1]

    def team_progress(self, ti: int) -> float:
        return self.balls[self.team_lead_ball(ti)].position.y

    def ranking(self) -> list[int]:
        """Équipes arrivées (par temps) puis les autres, de la plus avancée à la moins avancée."""
        rest = [ti for ti in range(len(self.teams)) if ti not in self.finish_times]
        rest.sort(key=lambda ti: -self.team_progress(ti))
        return list(self.finish_order) + rest

    def step_frame(self):
        for k in range(C.SUBSTEPS):
            self._sim_t = (self.frame * C.SUBSTEPS + k) / (C.FPS * C.SUBSTEPS)
            t_next = self._sim_t + C.DT
            for body, d in self.door_bodies:
                body.angular_velocity = (self._door_target(d, t_next) - body.angle) / C.DT
            self.space.step(C.DT)
        self.frame += 1
        self.time = self.frame / C.FPS
        crossing = []
        for i, b in enumerate(self.balls):
            if self.crossed[i]:
                continue
            if b.position.y >= self.course.finish_y:
                # instant exact du franchissement (interpolé dans l'image) : départage les photo-finish
                over = b.position.y - self.course.finish_y
                crossing.append((self.time - min(1.0 / C.FPS, over / max(b.velocity.y, 1.0)), i))
                continue
            ax, ay, at = self._anchor[i]
            if math.hypot(b.position.x - ax, b.position.y - ay) > C.STALL_DIST:
                self._anchor[i] = (b.position.x, b.position.y, self.time)
            elif self.time - at > self.max_stall:
                self.max_stall = self.time - at
                self.stall_where = (round(at, 2), round(ax), round(ay))
        for t_cross, i in sorted(crossing):
            self.crossed[i] = True
            ti = self.ball_team[i]
            self.team_crossed[ti] += 1
            if ti not in self.finish_times and self.team_crossed[ti] >= self.teams[ti].quota:
                self.finish_times[ti] = t_cross
                self.finish_order.append(ti)
        self._track_leader()

    def _track_leader(self):
        if self.time < 2.0 or self.winner is not None:
            return
        lead = self.ranking()[0]
        if self.leader is None:
            self.leader = lead
            return
        if lead == self.leader:
            self._cand = None
            return
        if lead == self._cand:
            self._cand_frames += 1
        else:
            self._cand, self._cand_frames = lead, 1
        if self._cand_frames >= C.LEAD_HOLD_FRAMES:
            self.leader = lead
            self.lead_changes.append((self.time, lead))
            self._cand = None

    def finished(self) -> bool:
        """Fin de la phase course (gagnant arrivé + AFTER_FINISH_S) ou temps écoulé."""
        if self.winner is not None:
            return self.time >= self.finish_times[self.winner] + C.AFTER_FINISH_S
        return self.time >= C.RACE_TIMEOUT_S

    def result(self) -> RaceResult:
        names = [t.name for t in self.teams]
        w = self.winner
        t_win = self.finish_times[w] if w is not None else None
        gap = None
        if len(self.finish_order) > 1:
            gap = round(self.finish_times[self.finish_order[1]] - t_win, 3)
        return RaceResult(
            seed=self.seed, set_key=self.set_key, teams=names,
            finish_times={names[i]: round(t, 3) for i, t in self.finish_times.items()},
            order=[names[i] for i in self.finish_order],
            winner=names[w] if w is not None else None,
            t_win=t_win, gap12=gap,
            lead_changes=[(round(t, 2), names[i]) for t, i in self.lead_changes],
            max_stall=round(self.max_stall, 2), stall_where=self.stall_where,
            course_height=self.course.height,
            sections=[s[0] for s in self.course.sections],
        )


def simulate(seed: int, set_key: str | None = None, n_teams: int | None = None) -> RaceResult:
    race = Race(seed, set_key, n_teams)
    while not race.finished():
        race.step_frame()
    return race.result()
