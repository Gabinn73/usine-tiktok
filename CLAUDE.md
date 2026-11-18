# Usine TikTok — courses de balles « choisis ton camp »

Usine à vidéos verticales *faceless* (TikTok / YouTube Shorts / Reels) générées à 100 % par du code.
Concept : des courses de balles physiques en français. Exemple : « France 🇫🇷 vs Italie 🇮🇹 vs Espagne 🇪🇸
vs Allemagne 🇩🇪 : qui arrive en bas en premier ? Commente ton camp 👇 ». Chaque équipe est une balle
(ou un groupe de balles) aux couleurs de son drapeau, qui traverse un parcours d'obstacles.
Jeux d'équipes : pays, villes françaises, couleurs, « 1 balle contre 100 » ; à venir : « course des abonnés ».

## Contraintes non négociables
- Vertical 1080×1920, MP4 H.264 (ffmpeg `-preset veryfast`), 30 fps, audio AAC
- Durée totale de la vidéo : **65 à 90 s** (monétisation TikTok > 1 min)
- 100 % original et généré par code : aucune image ni logo externe (drapeaux = formes simples)
- Pas de musique protégée : sons synthétisés + œuvres du domaine public (voir `assets/midi/SOURCES.md`)
- Rendu déterministe : **un seed = une vidéo reproductible**
- Le suspense jusqu'à la fin prime (rétention) ; accroche visible dès la 1re image
- **Aucune force invisible ni intervention artificielle** : pas de coup de pouce, pas de limite de
  vitesse, pas de triche sur le classement. Si une balle peut se bloquer, on corrige le parcours.

## Feuille de route
- [x] **SESSION 1** : moteur de course + rendu d'une première vidéo
- [x] **SESSION 2** : physique plus vive sans aucune aide artificielle, départ immédiat + accroche,
  yeux expressifs, variations (7 types de sections, 2 à 6 équipes, 4 jeux d'équipes, 7 thèmes),
  `--batch N`, sons de collision synthétisés, musique du domaine public (FluidSynth), tension + victoire
- [ ] **SESSION 3** : habillage (titre d'accroche, n° d'épisode « #47 », classement en direct,
  annonce du gagnant, appel « Commente ton camp »)
- [ ] **SESSION 4** : pipeline (une commande → N vidéos depuis un fichier de config) + génération
  quotidienne planifiée (GitHub Actions)
- [ ] **SESSION 5** : mode « course des abonnés » + petit suivi des stats

## Installation et utilisation
```bash
sudo apt-get install -y ffmpeg fluidsynth fluid-soundfont-gm      # outils système
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python generate.py --seed auto --out output/course_001.mp4   # 1 vidéo, meilleur seed
.venv/bin/python generate.py --batch 5                                 # 5 vidéos différentes + résumé
.venv/bin/python generate.py --seed 123 --set villes --teams 4 --theme ocean --music joplin_entertainer
.venv/bin/python generate.py --batch 3 --scan-only -v                  # pré-calcul seul
```
Chaque vidéo a un `.json` (seed, équipes, temps, changements de leader, thème, musique, stats audio
et la commande `replay` exacte pour la régénérer). Un batch écrit aussi `batch_<date>.json`.

## Architecture
- `generate.py` — CLI (vidéo unique, `--batch`, options `--set/--teams/--theme/--music`).
- `config/equipes.toml` — jeux d'équipes : question d'accroche, min/max d'équipes, équipes (motif
  de drapeau, couleurs, nb de balles, rayon, quota d'arrivée), sections autorisées, longueur.
- `usine/config.py` — constantes (format, timeline, physique, critères de sélection, audio).
- `usine/teams.py` — chargement des jeux + dessin des drapeaux (bandes, croix, nordique, uni, moitié).
- `usine/course.py` — parcours depuis un RNG : picots, zigzag, tapis, barres tournantes, entonnoir,
  portes (trappe en cycle), bumpers ; puis finale et ligne d'arrivée.
- `usine/simulation.py` — `Race` : pymunk (y vers le bas), pas fixe 1/180 s (6 sous-pas par image),
  équipes multi-balles, franchissement interpolé (photo-finish), suivi du leader, détection des
  immobilisations, événements de collision (pour les sons et les yeux).
- `usine/selection.py` — pré-calcul sans rendu (multiprocess), filtres + score de suspense.
- `usine/render.py` — rendu pygame headless : parcours dessiné par tranches de 1024 px à la demande,
  caméra sur le duel 1er/2e, HUD, accroche, écran du gagnant.
- `usine/faces.py` — yeux : regard selon la vitesse, peur (chute/gros choc), triste (doublé), content (en tête).
- `usine/themes.py` — 7 palettes/décors (fonds, motifs, couleurs d'obstacles).
- `usine/audio.py` — synthèse des chocs, rendu MIDI → WAV, tension, fanfare, compresseur + limiteur.
- `usine/video.py` — orchestration : simulation + rendu → H.264, bande-son → mux AAC.
- `usine/encoder.py` — pipe rawvideo → ffmpeg, et mux audio.
- `assets/midi/` — MIDI du domaine public + `SOURCES.md` (source et licence de chaque morceau).

## Sélection d'un seed (pré-calcul)
Rejeté si : durée vidéo hors 65–90 s ; arrivée ni serrée (écart 1er/2e ≤ 1 s) ni retournée (changement
de leader dans les 15 dernières s) ; aucun changement de leader avant 30 s ; une balle reste dans un
rayon de 30 px plus de 1,5 s. Score : photo-finish, retournements tardifs, changements entre 10 et 50 s,
durée proche de 72 s, pénalité pour tout arrêt > 0,8 s.

## Conventions / pièges
- **Déterminisme** : un RNG dérivé par usage (`derived_rng(seed, "parcours" | "equipes" | "depart" | "decor")`),
  jamais de `random` global, d'horloge, ni de `hash()` sur des chaînes (aléatoire par processus).
  Un tirage doit toujours consommer le RNG de la même façon, même quand une option l'écrase
  (ex. `TeamSet.pick` tire toujours le nombre d'équipes) — sinon pré-calcul et rendu divergent.
  Le rendu re-simule et vérifie qu'il retrouve le résultat du pré-calcul.
- Ne pas modifier le code Python pendant un batch : les processus du pré-calcul le rechargent.
- **Blocages** (cause du « l'Espagne s'arrête pour laisser passer la France », session 1) : rampes trop
  plates (7–9°) + frottement fort → la balle qui atterrit à contre-pente s'arrête puis repart lentement.
  Désormais : rampes ≥ 16°, tapis ≥ 12°, frottements faibles, et une **lèvre à 40° contre le mur** au
  début de chaque rampe/tapis (sinon la balle « patine » dans le coin, effet tapis de course).
- Écarts entre obstacles : soit ≥ ~100 px (diamètre max 92 px), soit nuls.
- Une **foule** (« 1 contre 100 ») s'embouteille sur rampes/tapis/entonnoirs/portes → ce jeu n'autorise
  que picots, barres et bumpers (`sections` dans le TOML) et un parcours plus long (`longueur`).
  LES 100 doivent **toutes** arriver (`quota = 100`) ; LA BALLE a un rayon 34 (≈ 50 % de victoires).
- Timeline : course dès l'image 0 (accroche 3 s en surimpression) → +2 s après le gagnant → gagnant 3 s.
- gfxdraw plante au-delà de ±32767 px : toujours découper les segments à la tranche dessinée.
- Python 3.14 lance les processus via forkserver : tout script qui utilise `scan()` doit avoir un
  `if __name__ == "__main__":`.
- Zones TikTok à garder lisibles : haut ~140 px, bas ~350 px, colonne droite ~130 px (boutons).
- Interface et textes de la vidéo en français.
