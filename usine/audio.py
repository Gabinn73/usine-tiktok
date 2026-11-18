"""Bande-son 100 % libre de droits, générée par code.

- Sons de collision synthétisés (numpy) : timbre selon le matériau touché, hauteur et volume
  selon la vitesse d'impact, panoramique selon la position, atténuation hors champ.
- Musique : œuvres du domaine public (MIDI Mutopia, voir assets/midi/SOURCES.md) rendues avec
  FluidSynth + la soundfont FluidR3_GM (licence MIT).
- Montée de tension sur les 10 dernières secondes, fanfare de victoire à l'arrivée.
- Mixage : compresseur sur le bus d'effets puis limiteur maître (aucune saturation).
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import config as C

SR = C.SAMPLE_RATE
ROOT = Path(__file__).resolve().parent.parent
MIDI_DIR = ROOT / "assets" / "midi"
CACHE_DIR = ROOT / "output" / ".cache" / "musique"

MUSIC = {
    "grieg_roi_montagne": {
        "titre": "Dans l'antre du roi de la montagne (Peer Gynt, op. 46 n° 4)", "auteur": "Edvard Grieg",
        "fichier": "Dans_l_antre_du_roi_de_la_montagne.mid",
        "source": "https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=1888", "licence": "Public Domain"},
    "mozart_alla_turca": {
        "titre": "Rondo alla turca (Sonate KV 331, 3e mvt)", "auteur": "W. A. Mozart",
        "fichier": "KV331_3_RondoAllaTurca.mid",
        "source": "https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=108", "licence": "Public Domain"},
    "joplin_entertainer": {
        "titre": "The Entertainer", "auteur": "Scott Joplin",
        "fichier": "entertainer.mid",
        "source": "https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=263", "licence": "Public Domain"},
    "joplin_maple_leaf": {
        "titre": "Maple Leaf Rag", "auteur": "Scott Joplin",
        "fichier": "maple.mid",
        "source": "https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=23", "licence": "Public Domain"},
}


# ---------------------------------------------------------------- briques de synthèse
def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _partials(f, parts, dur, decay, attack=0.002):
    t = _t(dur)
    env = np.exp(-t / decay) * np.minimum(1.0, t / attack)
    sig = sum(a * np.sin(2 * np.pi * f * m * t) for m, a in parts)
    return sig * env


def _noise(dur, decay, seed, smooth=1):
    t = _t(dur)
    n = np.random.default_rng(seed).standard_normal(len(t))
    if smooth > 1:
        n = np.convolve(n, np.ones(smooth) / smooth, mode="same")
    return n * np.exp(-t / decay)


def _norm(x, peak=1.0):
    m = np.abs(x).max() or 1.0
    return (x / m * peak).astype(np.float32)


def _synth(material: str, level: float, seed: int) -> np.ndarray:
    """Un son de choc ; level 0..1 = intensité (hauteur un peu plus aiguë si choc fort)."""
    k = 0.85 + 0.35 * level
    if material == "picot":
        s = _partials(1500 * k, [(1, 1), (2.76, 0.35), (5.4, 0.12)], 0.2, 0.045)
    elif material == "bumper":
        t = _t(0.28)
        f0 = 720 * k
        f = f0 * (0.45 + 0.55 * np.exp(-t / 0.05)) * (1 + 0.06 * np.sin(2 * np.pi * 28 * t))
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.11) * np.minimum(1, t / 0.003)
    elif material == "mur":
        s = _partials(190 * k, [(1, 1), (1.5, 0.3), (2.7, 0.1)], 0.14, 0.04) + 0.5 * _noise(0.14, 0.012, seed, 6)
    elif material == "tapis":
        s = _partials(330 * k, [(1, 1), (2.1, 0.25)], 0.1, 0.03) + 0.3 * _noise(0.1, 0.01, seed, 4)
    elif material == "barre":
        s = _partials(760 * k, [(1, 1), (2.32, 0.5), (4.25, 0.3), (6.1, 0.15)], 0.5, 0.15)
    elif material == "porte":
        s = _partials(520 * k, [(1, 1), (2.1, 0.4)], 0.09, 0.022) + 0.6 * _noise(0.09, 0.006, seed, 2)
    else:  # balle contre balle : « clac » de bille
        s = _partials(2000 * k, [(1, 1), (1.6, 0.6), (3.3, 0.3)], 0.07, 0.013) + 0.4 * _noise(0.07, 0.003, seed)
    return _norm(s)


MATERIAL_GAIN = {"picot": 0.45, "bumper": 0.6, "mur": 0.6, "tapis": 0.35, "barre": 0.4,
                 "porte": 0.5, "balle": 0.4}
N_LEVELS = 8


def _bank():
    return {m: [_synth(m, k / (N_LEVELS - 1), sum(map(ord, m)) * 10 + k) for k in range(N_LEVELS)] for m in MATERIAL_GAIN}


def _add(buf, start, mono, gl, gr):
    i0 = int(start * SR)
    if i0 >= len(buf) or i0 < 0:
        return
    n = min(len(mono), len(buf) - i0)
    buf[i0:i0 + n, 0] += mono[:n] * gl
    buf[i0:i0 + n, 1] += mono[:n] * gr


def _pan(x):
    p = np.clip((x / C.WIDTH - 0.5) * 1.2, -1, 1)
    a = (p + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


# ---------------------------------------------------------------- dynamique
def _envelope(x, block=128):
    a = np.abs(x).max(axis=1)
    nb = -(-len(a) // block)
    a = np.pad(a, (0, nb * block - len(a)))
    peaks = a.reshape(nb, block).max(axis=1)
    return np.maximum(peaks, np.r_[peaks[1:], 0.0])        # anticipation d'un bloc


def _smooth_gain(g, block, release_s):
    step = block / SR / release_s
    out = np.empty_like(g)
    cur = 1.0
    for k, v in enumerate(g):                               # attaque immédiate, relâchement lent
        cur = v if v < cur else min(v, cur + step)
        out[k] = cur
    return out


def _apply_gain(x, g, block):
    idx = np.arange(len(x)) / block
    gs = np.interp(idx, np.arange(len(g)), g)
    return x * gs[:, None]


def compress(x, thr=0.35, ratio=4.0, block=128, release_s=0.08):
    env = _envelope(x, block)
    g = np.ones_like(env)
    over = env > thr
    g[over] = (thr + (env[over] - thr) / ratio) / env[over]
    return _apply_gain(x, _smooth_gain(g, block, release_s), block)


def limit(x, ceiling=0.89, block=64, release_s=0.06):
    env = _envelope(x, block)
    g = np.minimum(1.0, ceiling / np.maximum(env, 1e-9))
    y = _apply_gain(x, _smooth_gain(g, block, release_s), block)
    # garde-fou doux : rien ne peut dépasser 0,98 (≈ -0,2 dBFS)
    a = np.abs(y)
    knee = 0.9
    over = a > knee
    y[over] = np.sign(y[over]) * (knee + (0.98 - knee) * np.tanh((a[over] - knee) / (0.98 - knee)))
    return y


# ---------------------------------------------------------------- musique
def render_music(key: str) -> np.ndarray:
    """Rend (une fois, avec cache) le MIDI en WAV via FluidSynth ; renvoie un tableau stéréo float."""
    info = MUSIC[key]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wav = CACHE_DIR / f"{key}.wav"
    if not wav.exists():
        subprocess.run(["fluidsynth", "-ni", "-g", "0.6", "-r", str(SR), "-F", str(wav),
                        C.SOUNDFONT, str(MIDI_DIR / info["fichier"])],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(str(wav)) as w:
        ch = w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    data = data.reshape(-1, ch)
    if ch == 1:
        data = np.repeat(data, 2, axis=1)
    start = int(np.argmax(np.abs(data).max(axis=1) > 0.01))
    data = data[start:]
    rms = np.sqrt(np.mean(data[: SR * 90] ** 2)) or 1.0
    return data * (0.1 / rms)                               # ≈ -20 dBFS RMS


# ---------------------------------------------------------------- événements spéciaux
def _tension(dur):
    """Battements de cœur qui accélèrent + montée (sinus glissant + souffle)."""
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    t = 0.0
    while t < dur - 0.05:
        u = t / dur
        kt = _t(0.18)
        f = 45 + 70 * np.exp(-kt / 0.03)
        kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-kt / 0.09)
        i0 = int(t * SR)
        m = min(len(kick), n - i0)
        out[i0:i0 + m] += kick[:m] * (0.45 + 0.5 * u)
        t += 0.55 - 0.37 * u
    tt = _t(dur)
    u = tt / dur
    f = 180 * (4.5 ** u)
    riser = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)) * 0.16 * u ** 2
    hiss = np.convolve(np.random.default_rng(7).standard_normal(n), np.ones(5) / 5, mode="same") * 0.12 * u ** 3
    return out + riser + hiss


def _fanfare():
    """Arpège de cuivres synthétiques (do majeur) + cymbale."""
    def brass(f, dur, amp):
        t = _t(dur)
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t)
        sig = sum(np.sin(2 * np.pi * f * k * np.cumsum(vib) / SR) / k for k in range(1, 9))
        env = np.minimum(1, t / 0.02) * np.exp(-t / (dur * 0.6))
        return sig * env * amp
    total = np.zeros(int(2.2 * SR), dtype=np.float32)
    notes = [(392.0, 0.0), (523.25, 0.11), (659.25, 0.22), (783.99, 0.33)]
    for f, st in notes:
        s = brass(f, 0.16, 0.5)
        i0 = int(st * SR)
        total[i0:i0 + len(s)] += s
    for f in (523.25, 659.25, 783.99, 1046.5):
        s = brass(f, 1.6, 0.35)
        i0 = int(0.44 * SR)
        total[i0:i0 + len(s)] += s[: len(total) - i0]
    crash = np.diff(np.random.default_rng(3).standard_normal(int(1.8 * SR)), prepend=0) * np.exp(-_t(1.8) / 0.5)
    total[: len(crash)] += crash * 0.35
    return _norm(total, 0.9)


def _chime():
    s = _partials(1046.5, [(1, 1), (2.0, 0.3), (3.01, 0.15)], 1.5, 0.5) + \
        _partials(1567.98, [(1, 0.7), (2.0, 0.2)], 1.5, 0.45)
    return _norm(s, 0.5)


# ---------------------------------------------------------------- mixage
def build_soundtrack(events, cams, t_win: float, duration: float, music_key: str, out_wav) -> dict:
    """Assemble et écrit la bande-son ; renvoie des statistiques (crête, saturation…)."""
    n = int(round(duration * SR))
    sfx = np.zeros((n, 2), dtype=np.float32)
    bank = _bank()

    # --- chocs : on garde au plus 2 sons par matériau toutes les 12 ms (les plus forts)
    events = sorted(events, key=lambda e: (round(e[0] / 0.012), e[1], -e[2]))
    kept, last_key, count = [], None, 0
    for e in events:
        key = (round(e[0] / 0.012), e[1])
        count = count + 1 if key == last_key else 1
        last_key = key
        if count <= 2:
            kept.append(e)
    lo, hi = np.log(80.0), np.log(3000.0)
    for t, mat, dv, x, y in kept:
        level = float(np.clip((np.log(max(dv, 1.0)) - lo) / (hi - lo), 0, 1))
        fi = min(len(cams) - 1, max(0, int(round(t * C.FPS))))
        cy = cams[fi] + C.HEIGHT / 2
        d = max(0.0, abs(y - cy) - C.HEIGHT / 2)
        g_dist = float(np.exp(-d / 450))
        if g_dist < 0.05:
            continue
        vol = MATERIAL_GAIN[mat] * (0.12 + 0.88 * level ** 1.3) * g_dist
        gl, gr = _pan(x)
        _add(sfx, t, bank[mat][int(round(level * (N_LEVELS - 1)))], gl * vol, gr * vol)
    sfx = compress(sfx)

    # --- musique (gain automatisé : montée pendant la tension, retrait à la victoire)
    music = render_music(music_key)
    if len(music) < n:
        music = np.tile(music, (n // len(music) + 1, 1))
    music = music[:n].copy()
    tt = np.arange(n) / SR
    t0 = max(0.0, t_win - C.TENSION_S)
    g = np.full(n, 0.85)
    g = np.where((tt >= t0) & (tt < t_win), 0.85 + 0.25 * (tt - t0) / max(1e-6, t_win - t0), g)
    g = np.where(tt >= t_win, 1.1 - 0.5 * np.clip((tt - t_win) / 0.3, 0, 1), g)
    g *= np.clip((duration - tt) / 0.8, 0, 1)                                  # fondu final
    music *= g[:, None]

    # --- tension, fanfare, carillon de l'écran du gagnant
    fx = np.zeros((n, 2), dtype=np.float32)
    ten = _tension(t_win - t0)
    _add(fx, t0, ten, 0.6, 0.6)
    _add(fx, t_win, _fanfare(), 0.75, 0.75)
    _add(fx, t_win + C.AFTER_FINISH_S, _chime(), 0.5, 0.5)

    mix = limit(music + sfx * 0.9 + fx)
    peak = float(np.abs(mix).max())
    clipped = int((np.abs(mix) >= 0.999).sum())
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {"peak": round(peak, 4), "peak_dbfs": round(20 * np.log10(max(peak, 1e-9)), 2),
            "clipped_samples": clipped, "sfx_events": len(events), "sfx_kept": len(kept),
            "music": music_key}
