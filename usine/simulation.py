"""Simulation physique de la course (pymunk), sans aucun rendu."""
import math
import random
from dataclasses import dataclass, field, asdict

import pymunk

from . import config as C
from .course import build_course
from .teams import DEFAULT_TEAMS, TEAMS


def _limit_velocity(body, gravity, damping, dt):
    pymunk.Body.update_velocity(body, gravity, damping, dt)
    v = body.velocity.length
    if v > C.MAX_SPEED:
        body.velocity = body.velocity * (C.MAX_SPEED / v)
    if abs(body.angular_velocity) > 25:
        body.angular_velocity = math.copysign(25, body.angular_velocity)


@dataclass
class RaceResult:
    seed: int
    teams: list
    finish_times: dict                      # nom d'équipe -> temps (s)
    order: list                             # noms dans l'ordre d'arrivée
    winner: str | None
    t_win: float | None
    gap12: float | None                     # écart 1er/2e (None si le 2e n'arrive pas à temps)
    lead_changes: list = field(default_factory=list)   # [(t, nom)]
    nudges: int = 0
    course_height: float = 0.0
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
    def __init__(self, seed: int, team_keys=DEFAULT_TEAMS):
        self.seed = seed
        self.teams = [TEAMS[k] for k in team_keys]
        rng = random.Random(seed)
        self.course = build_course(rng)
        self.nudge_rng = random.Random(f"nudge-{seed}")

        space = pymunk.Space()
        space.gravity = (0, C.GRAVITY)
        space.iterations = 15
        self.space = space
        static = space.static_body

        for a, b, r in self.course.segments:
            s = pymunk.Segment(static, a, b, r)
            s.elasticity, s.friction = 0.35, 0.6
            space.add(s)
        for x, y, r in self.course.pegs:
            s = pymunk.Circle(static, r, (x, y))
            s.elasticity, s.friction = 0.5, 0.3
            space.add(s)
        for x, y, r in self.course.bumpers:
            s = pymunk.Circle(static, r, (x, y))
            s.elasticity, s.friction = 1.0, 0.2
            space.add(s)

        self.spinner_bodies = []
        for cx, cy, half, thick, omega, a0 in self.course.spinners:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = (cx, cy)
            body.angle = a0
            body.angular_velocity = omega
            s = pymunk.Segment(body, (-half, 0), (half, 0), thick)
            s.elasticity, s.friction = 0.6, 0.5
            space.add(body, s)
            self.spinner_bodies.append((body, half, thick))

        # positions de départ : une case par équipe, ordre et léger décalage tirés au sort
        n = len(self.teams)
        slots = [C.WIDTH * (i + 1) / (n + 1) for i in range(n)]
        rng.shuffle(slots)
        self.balls = []
        for i in range(n):
            body = pymunk.Body(1.0, pymunk.moment_for_circle(1.0, 0, C.BALL_RADIUS))
            body.position = (slots[i] + rng.uniform(-30, 30), C.START_Y + rng.uniform(-15, 15))
            body.velocity_func = _limit_velocity
            s = pymunk.Circle(body, C.BALL_RADIUS)
            s.elasticity, s.friction = 0.55, 0.6
            space.add(body, s)
            self.balls.append(body)

        self.frame = 0
        self.time = 0.0
        self.finish_times: dict[int, float] = {}
        self.finish_order: list[int] = []
        self.slow = [0] * n
        self.nudges = 0
        self.leader = None
        self._cand, self._cand_frames = None, 0
        self.lead_changes: list[tuple[float, int]] = []

    # ------------------------------------------------------------------
    @property
    def winner(self):
        return self.finish_order[0] if self.finish_order else None

    def ranking(self) -> list[int]:
        """Arrivés (par temps) puis les autres, du plus bas au plus haut."""
        rest = [i for i in range(len(self.balls)) if i not in self.finish_times]
        rest.sort(key=lambda i: -self.balls[i].position.y)
        return list(self.finish_order) + rest

    def step_frame(self):
        for _ in range(C.SUBSTEPS):
            self.space.step(C.DT)
        self.frame += 1
        self.time = self.frame / C.FPS
        for i, b in enumerate(self.balls):
            if i in self.finish_times:
                continue
            if b.position.y >= self.course.finish_y:
                self.finish_times[i] = self.time
                self.finish_order.append(i)
                continue
            if b.velocity.length < C.STUCK_SPEED:
                self.slow[i] += 1
                if self.slow[i] >= C.STUCK_FRAMES:
                    b.apply_impulse_at_local_point((self.nudge_rng.uniform(-420, 420),
                                                    -self.nudge_rng.uniform(300, 500)))
                    self.nudges += 1
                    self.slow[i] = 0
            else:
                self.slow[i] = 0
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
            return self.time >= self.finish_times[self.winner] + C.AFTER_FINISH_S - 1e-9
        return self.time >= C.RACE_TIMEOUT_S

    def result(self) -> RaceResult:
        names = [t.name for t in self.teams]
        w = self.winner
        t_win = self.finish_times[w] if w is not None else None
        gap = None
        if len(self.finish_order) > 1:
            gap = round(self.finish_times[self.finish_order[1]] - t_win, 3)
        return RaceResult(
            seed=self.seed,
            teams=names,
            finish_times={names[i]: round(t, 3) for i, t in self.finish_times.items()},
            order=[names[i] for i in self.finish_order],
            winner=names[w] if w is not None else None,
            t_win=t_win,
            gap12=gap,
            lead_changes=[(round(t, 2), names[i]) for t, i in self.lead_changes],
            nudges=self.nudges,
            course_height=self.course.height,
        )


def simulate(seed: int, team_keys=DEFAULT_TEAMS) -> RaceResult:
    race = Race(seed, team_keys)
    while not race.finished():
        race.step_frame()
    return race.result()
