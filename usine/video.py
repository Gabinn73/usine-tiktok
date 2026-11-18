"""Assemblage d'une vidéo complète : simulation + rendu + bande-son + mux."""
from pathlib import Path

from . import config as C
from .audio import MUSIC, build_soundtrack
from .encoder import Encoder, mux
from .render import Renderer
from .simulation import Race, derived_rng
from .themes import THEMES


def default_look(seed: int) -> tuple[str, str]:
    """Thème et musique dérivés du seed (reproductibles)."""
    rng = derived_rng(seed, "decor")
    return rng.choice(sorted(THEMES)), rng.choice(sorted(MUSIC))


def make_video(seed: int, out_path, set_key=None, n_teams=None, theme_key=None, music_key=None,
               log=print) -> dict:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    d_theme, d_music = default_look(seed)
    theme_key, music_key = theme_key or d_theme, music_key or d_music
    race = Race(seed, set_key, n_teams)
    rd = Renderer(race, THEMES[theme_key])
    tmp_video, tmp_wav = out.with_name(out.stem + ".video.mp4"), out.with_name(out.stem + ".wav")

    with Encoder(tmp_video) as enc:
        rd.draw_race(first=True)                    # 1re image : départ + question d'accroche
        enc.write(rd.screen)
        while not race.finished():
            race.step_frame()
            rd.draw_race()
            enc.write(rd.screen)
            if race.frame % (15 * C.FPS) == 0:
                log(f"    … {race.time:4.0f}s de course rendues")
        if race.winner is None:
            raise RuntimeError("aucune équipe n'a franchi l'arrivée")
        snapshot = rd.screen.copy()
        for f in range(int(C.WINNER_S * C.FPS)):
            rd.draw_winner(snapshot, f)
            rd.cams.append(rd.cam)
            enc.write(rd.screen)
    duration = enc.frames / C.FPS

    res = race.result()
    audio = build_soundtrack(race.events, rd.cams, res.t_win, duration, music_key, tmp_wav)
    mux(tmp_video, tmp_wav, out)
    tmp_video.unlink()
    tmp_wav.unlink()
    return {"result": res, "frames": enc.frames, "theme": theme_key, "music": music_key, "audio": audio}
