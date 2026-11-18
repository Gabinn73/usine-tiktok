# Usine TikTok — courses de balles « choisis ton camp »

Usine à vidéos verticales *faceless* (TikTok / YouTube Shorts / Reels) générées à 100 % par du code.
Concept : des courses de balles physiques en français. Exemple : « France 🇫🇷 vs Italie 🇮🇹 vs Espagne 🇪🇸
vs Allemagne 🇩🇪 : qui arrive en bas en premier ? Commente ton camp 👇 ». Chaque équipe est une balle
(ou un groupe de balles) aux couleurs de son drapeau, qui traverse un parcours d'obstacles.
Variantes prévues : villes françaises, couleurs, « 1 balle contre 1000 », « course des abonnés ».

## Contraintes non négociables
- Vertical 1080×1920, MP4 H.264 (ffmpeg `-preset veryfast`), 30 fps
- Durée totale de la vidéo : **65 à 90 s** (monétisation TikTok > 1 min)
- 100 % original et généré par code : aucune image ni logo externe (drapeaux = formes simples)
- Pas de musique protégée : sons synthétisés ou musique libre de droits / domaine public
- Rendu déterministe : **un seed = une vidéo reproductible**
- Le suspense jusqu'à la fin prime (rétention)

## Feuille de route
- [x] **SESSION 1** : moteur de course + rendu d'une première vidéo
- [ ] **SESSION 2** : variations automatiques (parcours, obstacles, nb d'équipes) + sons de collision
  synthétisés + musique classique libre de droits
- [ ] **SESSION 3** : habillage (titre d'accroche, n° d'épisode « #47 », classement en direct,
  annonce du gagnant, appel « Commente ton camp »)
- [ ] **SESSION 4** : pipeline (une commande → N vidéos depuis un fichier de config) + génération
  quotidienne planifiée (GitHub Actions)
- [ ] **SESSION 5** : mode « course des abonnés » + petit suivi des stats

## Utilisation
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # ffmpeg requis sur le système
.venv/bin/python generate.py --seed auto --out output/course_001.mp4  # cherche le meilleur seed puis rend
.venv/bin/python generate.py --seed 123456 --out output/x.mp4         # rejoue un seed précis
.venv/bin/python generate.py --seed auto --scan-only                  # pré-calcul seul, pas de rendu
```
Un fichier `.json` est écrit à côté de chaque vidéo (seed, temps d'arrivée, score…).

## Architecture
- `generate.py` — CLI.
- `usine/config.py` — toutes les constantes (format, durées, physique, critères de sélection).
- `usine/teams.py` — équipes et drapeaux dessinés (bandes verticales/horizontales → disque).
- `usine/course.py` — génération du parcours à partir d'un `random.Random(seed)` : sections
  picots / zigzag / barres tournantes / entonnoir / bumpers, puis finale et ligne d'arrivée.
- `usine/simulation.py` — `Race` : monde pymunk (y vers le bas), pas fixe 1/120 s (4 sous-pas par image),
  arrivées, classement, suivi du leader (avec hystérésis), anti-blocage déterministe.
- `usine/selection.py` — pré-calcul sans rendu sur N seeds (multiprocess), filtre + score de suspense.
- `usine/render.py` — rendu pygame headless : parcours statique pré-dessiné sur une grande surface,
  caméra qui suit le duel 1er/2e, HUD (compte à rebours, classement, écran du gagnant).
- `usine/encoder.py` — frames RGB brutes envoyées en pipe à ffmpeg (aucun PNG sur disque).

## Conventions / pièges
- Le déterminisme repose sur : un seul RNG seedé pour le parcours, un RNG dérivé pour les « coups de
  pouce » anti-blocage, et un ordre d'ajout des formes pymunk identique. Ne jamais utiliser `random`
  global, l'horloge ou un `set` dont l'ordre d'itération influence la physique.
- Le rendu re-simule la course et vérifie qu'elle donne le même résultat que le pré-calcul.
- Géométrie : éviter tout écart entre obstacles compris entre ~0 et le diamètre d'une balle
  (84 px) : la balle s'y coincerait. Les écarts sont soit ≥ ~100 px, soit nuls.
- Timeline : compte à rebours 3 s → course → +2 s après le gagnant → écran du gagnant 3 s.
- Zones TikTok à garder lisibles : haut ~140 px, bas ~350 px, colonne droite ~130 px (boutons).
- Interface et textes de la vidéo en français.
