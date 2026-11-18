#!/usr/bin/env python3
"""Génère des vidéos de course de balles « choisis ton camp ».

    python generate.py --seed auto --out output/course_001.mp4     # une vidéo, meilleur seed trouvé
    python generate.py --batch 5                                   # 5 vidéos différentes dans output/
    python generate.py --seed 123 --set villes --teams 4 --theme ocean --music joplin_entertainer
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import usine  # noqa: F401  (variables d'environnement SDL)
from usine import config as C
from usine.audio import MUSIC
from usine.selection import evaluate, fmt, scan
from usine.simulation import pick_set_key, simulate
from usine.teams import SETS
from usine.themes import THEMES
from usine.video import default_look, make_video


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    return {"duration": float(d["format"]["duration"]),
            "streams": [f"{s['codec_type']}:{s['codec_name']}" for s in d["streams"]]}


def find_seed(set_key, n_teams, start, args, exclude=()):
    for _ in range(args.max_batches):
        seeds = [s for s in range(start, start + args.candidates) if s not in exclude]
        print(f"  pré-calcul de {len(seeds)} seeds ({seeds[0]}…{seeds[-1]}), jeu « {set_key} » :")
        results = scan(seeds, set_key=set_key, n_teams=n_teams, workers=args.workers,
                       log=print if args.verbose else (lambda *_: None))
        valid = [r for r in results if r.valid]
        print(f"  → {len(valid)}/{len(results)} courses retenues")
        if valid:
            return valid[0], start + args.candidates
        start += args.candidates
    sys.exit("Aucun seed satisfaisant trouvé : augmente --candidates ou --max-batches.")


def next_free(out_dir: Path) -> Path:
    k = 1
    while (out_dir / f"course_{k:03d}.mp4").exists():
        k += 1
    return out_dir / f"course_{k:03d}.mp4"


def produce(best, out: Path, theme, music, t0) -> dict:
    print(f"  seed {best.seed} | {best.set_key} | {', '.join(best.teams)} | thème {theme} | musique {music}")
    print(f"  rendu → {out}")
    made = make_video(best.seed, out, best.set_key, len(best.teams), theme, music)
    final = evaluate(made["result"])
    if (final.winner, final.t_win, final.gap12) != (best.winner, best.t_win, best.gap12):
        sys.exit(f"Non-déterminisme détecté : {final} != {best}")
    info = probe(out)
    meta = final.to_dict() | {
        "theme": made["theme"], "music": made["music"], "music_info": MUSIC[made["music"]],
        "audio": made["audio"], "frames": made["frames"], "duration_probe_s": info["duration"],
        "streams": info["streams"], "file": str(out),
        "replay": (f"python generate.py --seed {best.seed} --set {best.set_key} --teams {len(best.teams)} "
                   f"--theme {made['theme']} --music {made['music']} --out {out}"),
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    ok = C.VIDEO_MIN_S <= info["duration"] <= C.VIDEO_MAX_S
    print(f"  ✓ {info['duration']:.2f}s {'(OK)' if ok else '✗ HORS LIMITES'} | {' + '.join(info['streams'])} | "
          f"crête audio {made['audio']['peak_dbfs']} dBFS, {made['audio']['clipped_samples']} échantillons saturés | "
          f"{time.time() - t0:.0f}s")
    return meta


def summary_line(m):
    gap = f"{m['gap12']:.2f}s" if m["gap12"] is not None else "—"
    return (f"{Path(m['file']).name:<16} seed {m['seed']:<8} {m['set_key']:<14} {len(m['teams'])} éq.  "
            f"gagnant {m['winner']:<11} écart {gap:>6}  leaders {len(m['lead_changes']):>2}  "
            f"{m['duration_probe_s']:5.1f}s  {m['theme']:<14} {m['music']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default="auto", help="'auto' (recherche) ou un entier")
    ap.add_argument("--out", default=None, help="fichier de sortie (vidéo unique)")
    ap.add_argument("--out-dir", default="output", help="dossier de sortie (batch)")
    ap.add_argument("--batch", type=int, default=0, help="nombre de vidéos différentes à générer")
    ap.add_argument("--set", choices=sorted(SETS), default=None, help="jeu d'équipes (défaut : varié)")
    ap.add_argument("--teams", type=int, default=None, help="nombre d'équipes (défaut : tiré au sort)")
    ap.add_argument("--theme", choices=sorted(THEMES), default=None)
    ap.add_argument("--music", choices=sorted(MUSIC), default=None)
    ap.add_argument("--candidates", type=int, default=40, help="seeds simulés par lot")
    ap.add_argument("--search-from", type=int, default=None, help="premier seed (défaut : aléatoire)")
    ap.add_argument("--max-batches", type=int, default=5)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--scan-only", action="store_true", help="pré-calcul uniquement, pas de rendu")
    ap.add_argument("-v", "--verbose", action="store_true", help="affiche chaque seed simulé")
    args = ap.parse_args()
    t0 = time.time()

    # ------------------------------------------------ une seule vidéo, seed imposé
    if args.seed != "auto":
        seed = int(args.seed)
        set_key = args.set or pick_set_key(seed)
        best = evaluate(simulate(seed, set_key, args.teams))
        print(fmt(best))
        if not best.valid:
            print(f"⚠ seed {seed} hors critères : {'; '.join(best.reasons)}")
        if args.scan_only:
            return
        theme, music = default_look(seed)
        produce(best, Path(args.out or next_free(Path(args.out_dir))), args.theme or theme, args.music or music, t0)
        return

    # ------------------------------------------------ recherche automatique (1 ou N vidéos)
    n = max(1, args.batch)
    start = args.search_from if args.search_from is not None else int.from_bytes(os.urandom(3), "big")
    plan_rng = random.Random(start)
    set_cycle = [args.set] if args.set else plan_rng.sample(sorted(SETS), len(SETS))
    theme_pool = plan_rng.sample(sorted(THEMES), len(THEMES))
    music_pool = plan_rng.sample(sorted(MUSIC), len(MUSIC))
    out_dir = Path(args.out_dir)
    done, used = [], set()
    for k in range(n):
        set_key = set_cycle[k % len(set_cycle)]
        print(f"\n[{k + 1}/{n}] jeu « {set_key} »")
        best, start = find_seed(set_key, args.teams, start, args, exclude=used)
        used.add(best.seed)
        theme = args.theme or theme_pool[k % len(theme_pool)]      # thèmes tous différents
        music = args.music or music_pool[k % len(music_pool)]
        if args.scan_only:
            print(fmt(best))
            continue
        out = Path(args.out) if (args.out and n == 1) else next_free(out_dir)
        done.append(produce(best, out, theme, music, t0))

    if len(done) > 1:
        print("\nRésumé du batch :")
        for m in done:
            print("  " + summary_line(m))
        summ = out_dir / f"batch_{time.strftime('%Y%m%d_%H%M%S')}.json"
        summ.write_text(json.dumps([{k: m[k] for k in ("file", "seed", "set_key", "teams", "winner", "order",
                                                         "gap12", "lead_changes", "duration_probe_s", "theme",
                                                         "music", "audio", "replay")} for m in done],
                                   ensure_ascii=False, indent=2))
        print(f"  → {summ}")
    print(f"Terminé en {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
