"""Constantes globales du projet."""

# --- Format vidéo ---
WIDTH, HEIGHT = 1080, 1920
FPS = 30
SUBSTEPS = 4                      # sous-pas physiques par image
DT = 1.0 / (FPS * SUBSTEPS)       # pas fixe = 1/120 s

# --- Timeline ---
COUNTDOWN_S = 3.0                 # 3, 2, 1 avant le départ
AFTER_FINISH_S = 2.0              # on montre les arrivées suivantes
WINNER_S = 3.0                    # écran du gagnant
OVERHEAD_S = COUNTDOWN_S + AFTER_FINISH_S + WINNER_S

VIDEO_MIN_S, VIDEO_MAX_S = 65.0, 90.0
# temps du gagnant accepté (marge de 1 s de chaque côté)
RACE_MIN_S = VIDEO_MIN_S - OVERHEAD_S + 1.0
RACE_MAX_S = VIDEO_MAX_S - OVERHEAD_S - 1.0
RACE_TIMEOUT_S = RACE_MAX_S + 20.0

# --- Sélection du seed ---
CLOSE_GAP_S = 1.0                 # écart 1er/2e considéré « serré »
LATE_WINDOW_S = 15.0              # changement de leader dans les 15 dernières secondes
LEAD_HOLD_FRAMES = 10             # un nouveau leader doit tenir 1/3 s pour compter
TARGET_RACE_S = 70.0

# --- Physique (unités = pixels, y vers le bas) ---
GRAVITY = 1400.0
BALL_RADIUS = 42
MAX_SPEED = 1250.0
STUCK_SPEED = 30.0
STUCK_FRAMES = 36                 # 1,2 s quasi immobile -> petit coup de pouce

# --- Parcours ---
WALL = 14                         # demi-épaisseur des murs latéraux
TARGET_HEIGHT = 17000             # hauteur visée du parcours (avant finale)
START_Y = 560

# --- Couleurs ---
COL_WALL = (110, 210, 255)
COL_PEG = (235, 240, 255)
COL_PEG_RING = (80, 100, 160)
COL_BUMPER = (255, 70, 150)
COL_BUMPER_IN = (255, 170, 210)
COL_SPINNER = (255, 190, 40)
COL_GOLD = (255, 210, 60)
SECTION_BG = [
    (16, 20, 44), (22, 16, 46), (12, 28, 46), (26, 18, 38), (14, 24, 40),
]

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]
