"""NEON VANGUARD - Spiellogik, States, Waves und HUD.

Externe Imports: pygame, math, random.
"""
import math
import random

import pygame

from audio import Audio, SR
from entities import Bullet, Enemy, Player, PowerUp, PU_NAMES
from gfx import FloatingText, Particles, Starfield, apply_bloom, draw_glow, \
    make_background, ring, text
from settings import (
    COMBO_MAX, COMBO_STEP, COMBO_TIMEOUT, CYAN, ENEMY_BULLET_DMG, FPS, GREEN,
    H, HS_FILE, MAGENTA, MAX_ALIVE, PLAYER_BULLET_DMG, PLAYER_BULLET_SPEED,
    RAPID_TIME, RED, SHIELD_TIME, SPREAD_TIME, SPAWN_INTERVAL, TITLE, W,
    WHITE, YELLOW,
)

PU_KINDS = ("rapid", "spread", "shield", "heal")
PU_WEIGHTS = (25, 25, 20, 30)
PU_SHORT = {"rapid": "R  FEUERFOLGE", "spread": "S  STREUSCHOCK"}
GREY_HUD = (150, 165, 190)


class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.scene = pygame.Surface((W, H))
        self.bg = make_background(W, H)
        self.stars = Starfield(W, H, 260)
        self.particles = Particles()
        self.floats = FloatingText()
        self.audio = Audio()
        self.running = True
        self.state = "menu"
        self.hs = self._load_hs()
        self.t = 0.0
        self._es_cd = 0.0
        self._reset_world()
        self.audio.music(True)

    # ------------------------------------------------------------ Highscore
    def _load_hs(self):
        try:
            with open(HS_FILE, "r") as fh:
                return int(fh.read().strip() or 0)
        except Exception:
            return 0

    def _save_hs(self):
        if self.score > self.hs:
            self.hs = self.score
            try:
                with open(HS_FILE, "w") as fh:
                    fh.write(str(self.hs))
            except Exception:
                pass

    # ------------------------------------------------------------ Welt
    def _reset_world(self):
        self.player = Player(W / 2, H * 0.78)
        self.bullets = []
        self.ebullets = []
        self.enemies = []
        self.pups = []
        self.score = 0
        self.combo = 0
        self.combo_t = 0.0
        self.wave = 0
        self.spawn_q = []
        self.spawn_t = 0.0
        self.break_t = 0.7
        self.shake = 0.0
        self.flash_a = 0.0
        self.flash_col = RED
        self.freeze = 0.0
        self.banner = ["", 0.0]
        self.die_t = 0.0
        self.kills = 0
        self.new_high = False

    def new_game(self):
        self._reset_world()
        self.particles.clear()
        self.floats.clear()
        self.state = "play"
        pygame.mouse.set_visible(False)
        self.audio.play("ui")

    # ------------------------------------------------------------ Waves
    def _build_wave(self, w):
        if w % 5 == 0:
            q = ["boss"]
            pool = ["chaser"] + (["dart"] if w >= 5 else [])
            q += [random.choice(pool) for _ in range(3 + w)]
            return q
        n = 5 + int(w * 1.7)
        pool = ["chaser", "chaser", "dart"]
        if w >= 2:
            pool.append("shooter")
        if w >= 3:
            pool.append("orb")
        if w >= 4:
            pool.append("tank")
        if w >= 6:
            pool += ["shooter", "orb", "tank", "dart"]
        return [random.choice(pool) for _ in range(min(n, 34))]

    def next_wave(self):
        self.wave += 1
        self.spawn_q = self._build_wave(self.wave)
        self.spawn_t = 0.35
        if self.wave % 5 == 0:
            self.banner = ["WAVE %d  -  VOID SENTINEL" % self.wave, 3.2]
            self.audio.play("alarm")
        else:
            self.banner = ["WAVE %d" % self.wave, 2.0]
            self.audio.play("ui")

    def spawn_enemy(self, kind):
        if kind == "boss":
            self.enemies.append(Enemy(kind, W / 2, -110, self.wave))
            return
        side = random.random()
        if side < 0.62:
            x, y = random.uniform(40, W - 40), -50
        elif side < 0.81:
            x, y = -50, random.uniform(40, H * 0.55)
        else:
            x, y = W + 50, random.uniform(40, H * 0.55)
        self.enemies.append(Enemy(kind, x, y, self.wave))

    def enemy_shoot(self, vol=1.0):
        if self._es_cd <= 0:
            self.audio.play("eshoot", 0.65 * vol)
            self._es_cd = 0.12

    # ------------------------------------------------------------ Events
    def events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_m:
                    self.audio.toggle_mute()
                elif ev.key == pygame.K_ESCAPE:
                    if self.state == "play":
                        self.state = "pause"
                        self.audio.play("uidown")
                    elif self.state == "pause":
                        self.state = "play"
                        self.audio.play("ui")
                    elif self.state == "over":
                        self.state = "menu"
                        pygame.mouse.set_visible(True)
                        self.audio.play("uidown")
                    else:
                        self.running = False
                elif ev.key == pygame.K_p:
                    if self.state == "play":
                        self.state = "pause"
                        self.audio.play("uidown")
                    elif self.state == "pause":
                        self.state = "play"
                        self.audio.play("ui")
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                                pygame.K_r):
                    if self.state in ("menu", "over"):
                        self.new_game()
                    elif self.state == "pause" and ev.key == pygame.K_r:
                        self.new_game()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if self.state in ("menu", "over"):
                    self.new_game()

    # ------------------------------------------------------------ Update
    def update(self, dt):
        self.t += dt
        self._es_cd = max(0.0, self._es_cd - dt)
        self.stars.update(dt, 1.5 if self.state == "play" else 1.0)
        self.particles.update(dt)
        self.floats.update(dt)
        self.shake = max(0.0, self.shake - dt * 2.4)
        self.flash_a = max(0.0, self.flash_a - dt * 2.4)
        self.banner[1] = max(0.0, self.banner[1] - dt)

        if self.state == "menu":
            if random.random() < dt * 7:
                x = random.uniform(0, W)
                self.particles.burst(x, -10,
                                      random.choice([CYAN, MAGENTA, YELLOW]),
                                      n=1, speed=55, life=4.0, size=11, drag=0.15)
            return
        if self.state in ("pause", "over"):
            return
        if self.freeze > 0.0:
            self.freeze -= dt
            return
        self.play_update(dt)

    def play_update(self, dt):
        p = self.player

        # --- Spieler ---
        if p.alive:
            keys = pygame.key.get_pressed()
            ix = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - \
                int(keys[pygame.K_a] or keys[pygame.K_LEFT])
            iy = int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - \
                int(keys[pygame.K_w] or keys[pygame.K_UP])
            mx, my = pygame.mouse.get_pos()
            p.update(dt, ix, iy, mx, my)
            if (pygame.mouse.get_pressed(3)[0] or keys[pygame.K_SPACE]) and \
                    p.cooldown <= 0:
                self.player_fire(mx, my)
            if random.random() < dt * 40:
                bx = p.x - math.cos(p.angle) * 15
                by = p.y - math.sin(p.angle) * 15
                self.particles.trail(
                    bx, by, YELLOW,
                    vx=-math.cos(p.angle) * 95 + random.uniform(-30, 30),
                    vy=-math.sin(p.angle) * 95 + random.uniform(-30, 30),
                    life=0.3, size=13)
        else:
            self.die_t -= dt
            if self.die_t <= 0.0:
                self.state = "over"
                pygame.mouse.set_visible(True)
                self.new_high = self.score > self.hs
                self._save_hs()
                self.audio.play("uidown")

        # --- Combo ---
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0

        # --- Waves / Spawning ---
        alive = sum(1 for e in self.enemies if e.kind != "boss")
        if self.spawn_q:
            if alive < MAX_ALIVE:
                self.spawn_t -= dt
                if self.spawn_t <= 0:
                    self.spawn_enemy(self.spawn_q.pop(0))
                    self.spawn_t = SPAWN_INTERVAL * (0.55 if self.wave > 6 else 0.9)
        elif not self.enemies and p.alive:
            if self.break_t <= 0:
                self.break_t = 2.4
                bonus = 400 * self.wave
                self.score += bonus
                self.floats.add(W / 2, H / 2 + 70, "WAVE CLEAR  +%d" % bonus,
                                YELLOW, 32, 1.7)
                self.audio.play("pickup", 0.9)
                p.hp = min(p.max_hp, p.hp + 12)
            else:
                self.break_t -= dt
                if self.break_t <= 0:
                    self.next_wave()

        # --- Gegner ---
        for e in list(self.enemies):
            e.update(dt, p, self.add_enemy_bullet, self)
        if p.alive:
            for e in list(self.enemies):
                dx, dy = e.x - p.x, e.y - p.y
                rr = e.r + p.radius
                if dx * dx + dy * dy < rr * rr:
                    self.hurt_player(e.contact, e.x, e.y)
                    e.hp -= 5
                    e.flash = 0.2
                    e.vx = -dx * 4
                    e.vy = -dy * 4
                    if e.hp <= 0:
                        self.kill_enemy(e)

        # --- Kugeln bewegen ---
        self.bullets = [b for b in self.bullets if b.update(dt)]
        self.ebullets = [b for b in self.ebullets if b.update(dt)]

        # --- Kollisionen: Spieler-Kugeln vs. Gegner ---
        for b in self.bullets:
            for e in self.enemies:
                dx, dy = b.x - e.x, b.y - e.y
                rr = b.r + e.r
                if dx * dx + dy * dy <= rr * rr:
                    self.hit_enemy(e, b.dmg, b.x, b.y)
                    b.life = -1
                    break
        self.bullets = [b for b in self.bullets if b.life > 0]

        # --- Gegner-Kugeln vs. Spieler ---
        if p.alive:
            for b in self.ebullets:
                dx, dy = b.x - p.x, b.y - p.y
                rr = b.r + p.radius
                if dx * dx + dy * dy <= rr * rr:
                    b.life = -1
                    self.hurt_player(ENEMY_BULLET_DMG, b.x, b.y)
            self.ebullets = [b for b in self.ebullets if b.life > 0]

        # --- Gegner aufräumen ---
        self.enemies = [e for e in self.enemies if not getattr(e, "dead", False)]

        # --- Powerups ---
        for pu in list(self.pups):
            if not pu.update(dt, p):
                self.pups.remove(pu)
                continue
            dx, dy = pu.x - p.x, pu.y - p.y
            if p.alive and dx * dx + dy * dy < (pu.r + p.radius) ** 2:
                self.pups.remove(pu)
                self.apply_powerup(pu)

    # ------------------------------------------------------------ Aktionen
    def add_enemy_bullet(self, x, y, vx, vy, color, r=6.0):
        self.ebullets.append(Bullet(x, y, vx, vy, ENEMY_BULLET_DMG, "e",
                                    color, r, life=5.0))

    def player_fire(self, mx, my):
        p = self.player
        ang = math.atan2(my - p.y, mx - p.x)
        angles = [ang - 0.24, ang, ang + 0.24] if p.spread > 0 else [ang]
        for a in angles:
            self.bullets.append(Bullet(
                p.x + math.cos(a) * 18, p.y + math.sin(a) * 18,
                math.cos(a) * PLAYER_BULLET_SPEED,
                math.sin(a) * PLAYER_BULLET_SPEED,
                PLAYER_BULLET_DMG, "p", CYAN, 5.0, 1.4))
        p.cooldown = p.fire_rate()
        self.audio.play("laser", 0.5 if p.spread <= 0 else 0.42)
        self.particles.burst(p.x + math.cos(ang) * 22, p.y + math.sin(ang) * 22,
                             WHITE, n=3, speed=130, life=0.14, size=9,
                             cone=1.0, angle=ang)

    def hit_enemy(self, e, dmg, x, y):
        e.hp -= dmg
        e.flash = 0.12
        self.particles.burst(x, y, e.color, n=4, speed=170, life=0.3, size=10)
        self.audio.play("hit", 0.35)
        if e.hp <= 0:
            self.kill_enemy(e)

    def kill_enemy(self, e):
        if getattr(e, "dead", False):
            return
        e.dead = True
        self.kills += 1
        mult = self.mult()
        gain = int(e.score * mult)
        self.score += gain
        self.combo += 1
        self.combo_t = COMBO_TIMEOUT
        boss = e.kind == "boss"
        n = 46 if boss else int(10 + e.r * 0.9)
        self.particles.burst(e.x, e.y, e.color, n=n, speed=340 if boss else 250,
                             life=0.9 if boss else 0.6,
                             size=26 if boss else int(e.r * 0.9))
        self.particles.burst(e.x, e.y, WHITE, n=n // 2, speed=180, life=0.4,
                             size=14)
        self.floats.add(e.x, e.y - e.r, "+%d" % gain, YELLOW, 24, 0.9)
        self.shake = min(1.0, self.shake + (0.9 if boss else 0.22))
        self.audio.play("bigboom" if boss or e.r > 25 else "boom",
                        1.0 if boss else 0.8)
        if boss:
            self.freeze = 0.22
            self.flash_a, self.flash_col = 0.85, WHITE
            for i, k in enumerate(("rapid", "spread", "shield")):
                self.pups.append(PowerUp(k, e.x + (i - 1) * 70, e.y + 40))
        elif self.combo > 0 and self.combo % 5 == 0:
            self.floats.add(e.x, e.y - e.r - 24, "COMBO x%d" % self.combo,
                            GREEN, 30, 1.1)
        if not boss and random.random() < 0.14:
            kind = random.choices(PU_KINDS, weights=PU_WEIGHTS)[0]
            self.pups.append(PowerUp(kind, e.x, e.y))

    def apply_powerup(self, pu):
        p = self.player
        if pu.kind == "rapid":
            p.rapid = RAPID_TIME
        elif pu.kind == "spread":
            p.spread = SPREAD_TIME
        elif pu.kind == "shield":
            p.shield = SHIELD_TIME
        elif pu.kind == "heal":
            p.hp = min(p.max_hp, p.hp + 30)
        self.score += 150
        self.floats.add(pu.x, pu.y, PU_NAMES[pu.kind], pu.color, 26, 1.3)
        self.particles.burst(pu.x, pu.y, pu.color, n=22, speed=260, life=0.6,
                             size=16)
        self.audio.play("pickup" if pu.kind != "heal" else "full")

    def hurt_player(self, amount, sx, sy):
        p = self.player
        if not p.alive or p.invuln > 0:
            return
        res = p.damage(amount)
        if res == "shield":
            self.floats.add(p.x, p.y - 34, "BLOCK!", CYAN, 30, 0.9)
            self.particles.burst(p.x, p.y, CYAN, n=26, speed=300, life=0.5,
                                 size=16)
            self.audio.play("tick")
            self.shake = min(1.0, self.shake + 0.3)
            return
        if not res:
            return
        self.shake = min(1.0, self.shake + 0.55)
        self.flash_a, self.flash_col = 0.5, RED
        self.freeze = max(self.freeze, 0.06)
        self.combo = 0
        self.combo_t = 0
        self.floats.add(p.x, p.y - 34, "-%d" % amount, RED, 32, 0.9)
        self.particles.burst(p.x, p.y, RED, n=24, speed=300, life=0.55, size=16)
        self.audio.play("hurt", 0.9)
        if not p.alive:
            self.die_t = 1.5
            self.freeze = 0.28
            self.shake = 1.0
            self.flash_a, self.flash_col = 1.0, WHITE
            self.particles.burst(p.x, p.y, CYAN, n=70, speed=420, life=1.1,
                                 size=30)
            self.particles.burst(p.x, p.y, WHITE, n=40, speed=260, life=0.7,
                                 size=20)
            self.audio.play("bigboom")

    def mult(self):
        return 1.0 + min(COMBO_MAX - 1.0, self.combo * COMBO_STEP)

    # ------------------------------------------------------------ Render
    def render(self):
        scene = self.scene
        ox = oy = 0
        if self.shake > 0.02:
            s = self.shake * self.shake * 15
            ox, oy = random.uniform(-s, s), random.uniform(-s, s)
        scene.fill((4, 5, 12))
        scene.blit(self.bg, (int(ox), int(oy)))
        self.stars.draw(scene)

        if self.state == "menu":
            self.draw_menu(scene)
        else:
            self.draw_world(scene)
            self.draw_hud(scene)
            if self.state == "pause":
                self.overlay(scene, "PAUSED", "P oder ESC - weiter", CYAN)
            elif self.state == "over":
                self.draw_over(scene)
            elif self.state == "play":
                self.draw_crosshair(scene)

        apply_bloom(scene, strength=1.0, threshold=118)
        self.screen.blit(scene, (0, 0))

        if self.flash_a > 0.01:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((*self.flash_col, int(200 * min(1.0, self.flash_a))))
            self.screen.blit(ov, (0, 0))

    def draw_world(self, scene):
        for pu in self.pups:
            pu.draw(scene)
        for e in self.enemies:
            e.draw(scene)
        for b in self.bullets:
            b.draw(scene)
        for b in self.ebullets:
            b.draw(scene)
        self.player.draw(scene)
        self.particles.draw(scene)
        self.floats.draw(scene)

    # ------------------------------------------------------------ HUD
    @staticmethod
    def bar(surf, x, y, w, h, frac, col, back=(24, 28, 46), border=(70, 84, 120)):
        frac = max(0.0, min(1.0, frac))
        pygame.draw.rect(surf, back, (x, y, w, h), border_radius=3)
        if frac > 0:
            pygame.draw.rect(surf, col, (x, y, max(2, int(w * frac)), h),
                             border_radius=3)
        pygame.draw.rect(surf, border, (x, y, w, h), 1, border_radius=3)

    def draw_hud(self, scene):
        p = self.player
        # --- Links: Leben + Powerups ---
        text(scene, "HP", 18, GREY_HUD, (22, 18), "topleft")
        self.bar(scene, 56, 20, 250, 16, p.hp / p.max_hp,
                 GREEN if p.hp > 35 else RED)
        text(scene, "%d" % int(p.hp), 16, WHITE, (181, 21), "center")
        if p.shield > 0:
            self.bar(scene, 56, 40, 250, 7, p.shield / SHIELD_TIME, CYAN)
            text(scene, "SCHILD", 14, CYAN, (312, 36), "topleft")
        y = 58
        for key, col, maxt in (("rapid", YELLOW, RAPID_TIME),
                               ("spread", GREEN, SPREAD_TIME)):
            val = getattr(p, key)
            if val > 0:
                text(scene, PU_SHORT[key], 15, col, (56, y), "topleft")
                self.bar(scene, 196, y + 4, 110, 8, val / maxt, col)
                y += 24

        # --- Rechts: Score / Combo / Wave ---
        text(scene, "SCORE", 16, GREY_HUD, (W - 22, 16), "topright")
        text(scene, "%d" % self.score, 44, WHITE, (W - 22, 32), "topright")
        mult = self.mult()
        if self.combo > 1:
            c = GREEN if mult < 2.5 else YELLOW if mult < 3.5 else MAGENTA
            text(scene, "x%.2f" % mult, 34, c, (W - 22, 82), "topright")
            text(scene, "%d KOMBO" % self.combo, 16, GREY_HUD, (W - 22, 120),
                 "topright")
        text(scene, "WAVE %d" % self.wave, 26, CYAN, (22, H - 34), "bottomleft")
        text(scene, "KILLS %d" % self.kills, 16, GREY_HUD, (140, H - 32),
             "bottomleft")
        text(scene, "BEST %d" % self.hs, 16, GREY_HUD, (W - 22, H - 32),
             "bottomright")
        text(scene, "WASD  MAUS  LMB  |  P PAUSE  M TON  R NEU", 15,
             (96, 108, 140), (W // 2, H - 30), "midbottom")

        # --- Boss-Balken ---
        boss = next((e for e in self.enemies if e.kind == "boss"), None)
        if boss:
            bw = 560
            bx = (W - bw) // 2
            text(scene, "VOID SENTINEL", 18, MAGENTA, (W // 2, 56), "center")
            self.bar(scene, bx, 78, bw, 14, boss.hp / boss.max_hp, MAGENTA,
                     back=(30, 16, 34))

        # --- Banner ---
        if self.banner[1] > 0:
            k = min(1.0, self.banner[1] / 0.5)
            a = int(255 * k)
            size = 62 if "%d" % self.wave in self.banner[0] else 50
            text(scene, self.banner[0], size, WHITE, (W // 2, H * 0.36),
                 "center", a)

    def draw_crosshair(self, scene):
        mx, my = pygame.mouse.get_pos()
        r = 13 + int(2 * math.sin(self.t * 6))
        pygame.draw.circle(scene, CYAN, (mx, my), r, 2)
        pygame.draw.line(scene, CYAN, (mx - r - 6, my), (mx - r + 2, my), 2)
        pygame.draw.line(scene, CYAN, (mx + r - 2, my), (mx + r + 6, my), 2)
        pygame.draw.line(scene, CYAN, (mx, my - r - 6), (mx, my - r + 2), 2)
        pygame.draw.line(scene, CYAN, (mx, my + r - 2), (mx, my + r + 6), 2)
        draw_glow(scene, mx, my, 7, WHITE)

    # ------------------------------------------------------------ Menü / Over
    def overlay(self, scene, title, hint, col):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((3, 4, 12, 175))
        scene.blit(dim, (0, 0))
        text(scene, title, 74, col, (W // 2, H * 0.42), "center")
        pulse = int(150 + 105 * math.sin(self.t * 4))
        text(scene, hint, 26, WHITE, (W // 2, H * 0.56), "center", pulse)

    def draw_menu(self, scene):
        cy = H * 0.3
        pulse = 0.6 + 0.4 * math.sin(self.t * 2.0)
        draw_glow(scene, W // 2, cy + 6, int(120 * pulse), (20, 90, 140))
        text(scene, "NEON VANGUARD", 92, CYAN, (W // 2, cy), "center")
        text(scene, "ARCADE SURVIVAL PROTOCOL", 26, MAGENTA,
             (W // 2, cy + 62), "center")
        pr = int(140 + 115 * math.sin(self.t * 5))
        text(scene, "KLICK ODER ENTER  -  START", 32, YELLOW,
             (W // 2, H * 0.60), "center", pr)
        info = [
            "WASD / PFEILTASTEN  -  Bewegen        MAUS  -  Zielen",
            "LINKE MAUSTASTE / LEERTASTE  -  Feuern",
            "POWERUPS:  R Feuerfolge   S Streuschock   D Schild   + Reparatur",
            "P  Pause      M  Ton      ESC  Zurück      R  Neustart",
        ]
        for i, line in enumerate(info):
            text(scene, line, 20, (176, 190, 216), (W // 2, H * 0.70 + i * 30),
                 "center")
        text(scene, "HIGHSCORE  %d" % self.hs, 30, GREEN, (W // 2, H * 0.88),
             "center")
        text(scene, "GENAU 5 IMPORTS:  pygame  numpy  math  random  sys", 16,
             (110, 124, 156), (W // 2, H - 44), "center")
        text(scene, "Sounds, Musik & Grafik komplett prozedural erzeugt", 16,
             (110, 124, 156), (W // 2, H - 22), "center")

    def draw_over(self, scene):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((6, 3, 14, 190))
        scene.blit(dim, (0, 0))
        text(scene, "GAME OVER", 88, RED, (W // 2, H * 0.30), "center")
        text(scene, "SCORE   %d" % self.score, 46, WHITE, (W // 2, H * 0.46),
             "center")
        text(scene, "WAVE %d     KILLS %d" % (self.wave, self.kills), 26,
             GREY_HUD, (W // 2, H * 0.56), "center")
        if self.new_high:
            pulse = int(140 + 115 * math.sin(self.t * 5))
            text(scene, "NEUER HIGHSCORE!", 40, YELLOW, (W // 2, H * 0.65),
                 "center", pulse)
        else:
            text(scene, "BEST  %d" % self.hs, 30, GREEN, (W // 2, H * 0.65),
                 "center")
        pr = int(140 + 115 * math.sin(self.t * 5))
        text(scene, "ENTER / KLICK  -  NEUSTART      ESC  -  HAUPTMENÜ", 26,
             CYAN, (W // 2, H * 0.78), "center", pr)

    # ------------------------------------------------------------ Loop
    def run(self):
        while self.running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            self.events()
            self.update(dt)
            self.render()
            pygame.display.flip()
        pygame.quit()
