"""Pré-calcul : simule plusieurs seeds sans rendu et garde les courses à suspense."""
import os
from concurrent.futures import ProcessPoolExecutor

from . import config as C
from .simulation import RaceResult, simulate


def evaluate(res: RaceResult) -> RaceResult:
    reasons = []
    if res.t_win is None:
        res.valid, res.score, res.reasons = False, -99.0, ["aucune arrivée"]
        return res
    if not (C.RACE_MIN_S <= res.t_win <= C.RACE_MAX_S):
        reasons.append(f"durée vidéo {res.video_s:.1f}s hors [{C.VIDEO_MIN_S:.0f},{C.VIDEO_MAX_S:.0f}]")
    close = res.gap12 is not None and res.gap12 <= C.CLOSE_GAP_S
    late = [t for t, _ in res.lead_changes if t >= res.t_win - C.LATE_WINDOW_S]
    if not (close or late):
        reasons.append("arrivée pas assez serrée")

    score = 0.0
    if res.gap12 is not None:
        score += 3.0 * max(0.0, 1.5 - res.gap12)            # photo-finish
    score += 2.0 * min(len(late), 3)                         # retournements tardifs
    score += 0.3 * min(len(res.lead_changes), 10)            # course animée
    score -= abs(res.t_win - C.TARGET_RACE_S) / 10.0         # durée proche de la cible
    score -= 0.5 * res.nudges                                # balles coincées = moche
    res.valid, res.score, res.reasons = not reasons, round(score, 3), reasons
    return res


def _run(seed: int) -> RaceResult:
    return evaluate(simulate(seed))


def scan(seeds, workers: int | None = None, log=print) -> list[RaceResult]:
    workers = workers or os.cpu_count() or 1
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(_run, seeds):
            results.append(res)
            flag = "OK " if res.valid else "-- "
            vid = f"{res.video_s:5.1f}s" if res.video_s else "  ---"
            gap = f"{res.gap12:.2f}s" if res.gap12 is not None else "---"
            log(f"  {flag} seed {res.seed:>8}  vidéo {vid}  écart {gap:>6}  "
                f"leaders {len(res.lead_changes):>2}  coups de pouce {res.nudges}  "
                f"score {res.score:6.2f}  {'; '.join(res.reasons)}")
    return sorted(results, key=lambda r: (r.valid, r.score), reverse=True)
