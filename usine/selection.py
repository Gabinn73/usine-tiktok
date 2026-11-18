"""Pré-calcul : simule plusieurs seeds sans rendu et garde les courses à suspense."""
import os
from concurrent.futures import ProcessPoolExecutor
from functools import partial

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
    changes = [t for t, _ in res.lead_changes]
    late = [t for t in changes if t >= res.t_win - C.LATE_WINDOW_S]
    early = [t for t in changes if t < C.EARLY_CHANGE_S]
    mid = [t for t in changes if C.MID_WINDOW[0] <= t <= C.MID_WINDOW[1]]
    if not (close or late):
        reasons.append("arrivée pas assez serrée")
    if not early:
        reasons.append("aucun changement de leader avant 30 s")
    if res.max_stall > C.STALL_S:
        reasons.append(f"balle immobile {res.max_stall:.1f}s")

    score = 0.0
    if res.gap12 is not None:
        score += 3.0 * max(0.0, 1.5 - res.gap12)            # photo-finish
    score += 2.0 * min(len(late), 3)                         # retournements tardifs
    score += 0.8 * min(len(mid), 5)                          # pas de creux entre 10 et 50 s
    score += 1.0 * min(len(early), 2)
    score += 0.2 * min(len(changes), 15)
    score -= abs(res.t_win - C.TARGET_RACE_S) / 10.0         # durée proche de la cible
    score -= 2.0 * max(0.0, res.max_stall - 0.8)             # même un arrêt court se voit
    res.valid, res.score, res.reasons = not reasons, round(score, 3), reasons
    return res


def _run(seed: int, set_key=None, n_teams=None) -> RaceResult:
    return evaluate(simulate(seed, set_key, n_teams))


def fmt(res: RaceResult) -> str:
    flag = "OK " if res.valid else "-- "
    vid = f"{res.video_s:5.1f}s" if res.video_s else "  ---"
    gap = f"{res.gap12:.2f}s" if res.gap12 is not None else "---"
    return (f"  {flag} seed {res.seed:>8} {res.set_key:<14} {len(res.teams)} éq.  vidéo {vid}  "
            f"écart {gap:>6}  leaders {len(res.lead_changes):>2}  arrêt max {res.max_stall:3.1f}s  "
            f"score {res.score:6.2f}  {'; '.join(res.reasons)}")


def scan(seeds, set_key=None, n_teams=None, workers: int | None = None, log=print) -> list[RaceResult]:
    workers = workers or os.cpu_count() or 1
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(partial(_run, set_key=set_key, n_teams=n_teams), seeds):
            results.append(res)
            log(fmt(res))
    return sorted(results, key=lambda r: (r.valid, r.score), reverse=True)
