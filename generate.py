#!/usr/bin/env python3
"""Génère une vidéo de course de balles « choisis ton camp ».

    python generate.py --seed auto --out output/course_001.mp4
    python generate.py --seed 123456 --out output/rejoue.mp4
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import usine  # noqa: F401  (variables d'environnement SDL)
from usine import config as C
from usine.render import render_video
from usine.selection import evaluate, scan
from usine.simulation import Race, simulate


def probe_duration(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


def pick_seed(args):
    start = args.search_from if args.search_from is not None else int.from_bytes(os.urandom(3), "big")
    for attempt in range(args.max_batches):
        seeds = range(start, start + args.candidates)
        print(f"Pré-calcul de {args.candidates} seeds ({seeds.start}…{seeds.stop - 1}) :")
        results = scan(seeds, workers=args.workers)
        valid = [r for r in results if r.valid]
        print(f"→ {len(valid)}/{len(results)} courses retenues")
        if valid:
            return valid[0]
        start += args.candidates
    sys.exit("Aucun seed satisfaisant trouvé : augmente --candidates.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default="auto", help="'auto' (recherche) ou un entier")
    ap.add_argument("--out", default="output/course.mp4")
    ap.add_argument("--candidates", type=int, default=48, help="seeds simulés par lot en mode auto")
    ap.add_argument("--search-from", type=int, default=None, help="premier seed du lot (défaut : aléatoire)")
    ap.add_argument("--max-batches", type=int, default=5)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--scan-only", action="store_true", help="pré-calcul uniquement, pas de rendu")
    args = ap.parse_args()

    t0 = time.time()
    if args.seed == "auto":
        best = pick_seed(args)
    else:
        best = evaluate(simulate(int(args.seed)))
        if not best.valid:
            print(f"⚠ seed {best.seed} hors critères : {'; '.join(best.reasons)}")
    print(f"\nSeed retenu : {best.seed} | gagnant {best.winner} en {best.t_win:.2f}s | "
          f"écart 1er/2e {best.gap12} | {len(best.lead_changes)} changements de leader | "
          f"vidéo prévue {best.video_s:.1f}s | score {best.score}")
    if args.scan_only:
        return

    out = Path(args.out)
    print(f"Rendu → {out}")
    race = Race(best.seed)
    frames = render_video(race, out)
    final = evaluate(race.result())
    if (final.winner, final.t_win, final.gap12) != (best.winner, best.t_win, best.gap12):
        sys.exit(f"Non-déterminisme détecté : {final} != {best}")

    dur = probe_duration(out)
    meta = final.to_dict() | {"frames": frames, "duration_probe_s": dur, "file": str(out)}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    ok = C.VIDEO_MIN_S <= dur <= C.VIDEO_MAX_S
    print(f"Terminé en {time.time() - t0:.0f}s : {frames} images, durée {dur:.2f}s "
          f"{'✓' if ok else '✗ HORS LIMITES'}")


if __name__ == "__main__":
    main()
