"""NEON VANGUARD - globale Einstellungen, Farben und Spielwerte.

Externe Imports: keine (nur Konstanten).
"""

# --- Fenster / Loop ---
W = 1280
H = 720
FPS = 60
TITLE = "NEON VANGUARD"

# --- Neon-Palette ---
BLACK = (4, 5, 12)
BG_TOP = (8, 8, 26)
BG_BOT = (22, 6, 44)
CYAN = (0, 255, 255)
MAGENTA = (255, 40, 170)
YELLOW = (255, 225, 70)
GREEN = (80, 255, 150)
ORANGE = (255, 150, 40)
RED = (255, 70, 90)
PURPLE = (170, 100, 255)
BLUE = (90, 150, 255)
WHITE = (245, 250, 255)
GREY = (150, 165, 190)

# --- Spieler ---
PLAYER_MAX_HP = 100
PLAYER_SPEED = 470
PLAYER_FRICTION = 0.86          # gedämpft pro Frame
PLAYER_RADIUS = 15
PLAYER_FIRE_RATE = 0.135        # Sekunden zwischen Schüssen
PLAYER_BULLET_SPEED = 920
PLAYER_BULLET_DMG = 2.0
PLAYER_INVULN = 0.9

# --- Waffen-Powerups ---
RAPID_TIME = 9.0
SPREAD_TIME = 9.0
SHIELD_TIME = 7.0

# --- Gegner-Bullets ---
ENEMY_BULLET_SPEED = 300
ENEMY_BULLET_DMG = 9

# --- Combos / Score ---
COMBO_TIMEOUT = 3.2
COMBO_STEP = 0.12
COMBO_MAX = 4.0

# --- Waves ---
WAVE_BREAK = 2.4
SPAWN_INTERVAL = 0.5
MAX_ALIVE = 14

HS_FILE = "neon_vanguard_highscore.txt"
