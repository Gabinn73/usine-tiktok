"""Constantes globales du projet."""

# --- Format vidéo ---
WIDTH, HEIGHT = 1080, 1920
FPS = 30
SUBSTEPS = 6                      # sous-pas physiques par image (balles rapides : pas de traversée)
DT = 1.0 / (FPS * SUBSTEPS)       # pas fixe = 1/180 s

# --- Timeline (les balles partent dès la 1re image) ---
HOOK_S = 3.0                      # question d'accroche en surimpression
AFTER_FINISH_S = 2.0              # on montre les arrivées suivantes
WINNER_S = 3.0                    # écran du gagnant
OVERHEAD_S = AFTER_FINISH_S + WINNER_S

VIDEO_MIN_S, VIDEO_MAX_S = 65.0, 90.0
RACE_MIN_S = VIDEO_MIN_S - OVERHEAD_S + 1.0     # temps du gagnant accepté (marge 1 s)
RACE_MAX_S = VIDEO_MAX_S - OVERHEAD_S - 1.0
RACE_TIMEOUT_S = RACE_MAX_S + 20.0
TARGET_RACE_S = 72.0

# --- Sélection du seed ---
CLOSE_GAP_S = 1.0                 # écart 1er/2e considéré « serré »
LATE_WINDOW_S = 15.0              # changement de leader dans les 15 dernières secondes
EARLY_CHANGE_S = 30.0             # au moins un changement de leader avant 30 s
MID_WINDOW = (10.0, 50.0)         # on récompense l'animation en milieu de course
LEAD_HOLD_FRAMES = 10             # un nouveau leader doit tenir 1/3 s pour compter
STALL_S = 1.5                     # balle quasi immobile plus longtemps -> seed rejeté
STALL_DIST = 30.0                 # « quasi immobile » = reste dans un rayon de 30 px

# --- Physique (unités = pixels, y vers le bas). Aucune force artificielle. ---
GRAVITY = 2300.0
BALL_RADIUS = 42
BALL_ELASTICITY = 0.72
BALL_FRICTION = 0.25
MAX_BALL_DIAMETER = 2 * 46        # le parcours est dimensionné pour la plus grosse balle

# --- Parcours ---
WALL = 14                         # demi-épaisseur des murs latéraux
TARGET_HEIGHT = 30000             # hauteur visée du parcours (avant finale)
START_Y = 660

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

# --- Audio ---
SAMPLE_RATE = 44100
SOUNDFONT = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
TENSION_S = 10.0                  # montée de tension avant l'arrivée
