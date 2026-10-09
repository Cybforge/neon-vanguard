"""Spiel-Entitäten: Spieler, Kugeln, Gegner, Boss und Powerups.

Externe Imports: pygame, math, random.
"""
import math
import random

import pygame

from gfx import draw_glow, ring, text
from settings import (
    CYAN, GREEN, MAGENTA, ORANGE, PURPLE, RED, WHITE, YELLOW,
    PLAYER_SPEED, PLAYER_FRICTION, PLAYER_RADIUS, PLAYER_MAX_HP,
    PLAYER_INVULN, PLAYER_FIRE_RATE, PLAYER_BULLET_SPEED, ENEMY_BULLET_SPEED,
    W, H,
)

NEUTRAL_FILL = (10, 14, 34)
NEUTRAL_FILL2 = (16, 10, 34)


def _lerp_col(c1, c2, k):
    k = max(0.0, min(1.0, k))
    return (int(c1[0] + (c2[0] - c1[0]) * k),
            int(c1[1] + (c2[1] - c1[1]) * k),
            int(c1[2] + (c2[2] - c1[2]) * k))


def _rot(pts, ang, x, y):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]


# ================================================================= Spieler
class Player:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.angle = -math.pi / 2
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.radius = PLAYER_RADIUS
        self.cooldown = 0.0
        self.invuln = 0.0
        self.shield = 0.0
        self.rapid = 0.0
        self.spread = 0.0
        self.flash = 0.0
        self.alive = True
        self.shots = 0

    def update(self, dt, ix, iy, aim_x, aim_y):
        if not self.alive:
            return
        tx, ty = ix * PLAYER_SPEED, iy * PLAYER_SPEED
        k = 1.0 - PLAYER_FRICTION ** (dt * 60.0)
        self.vx += (tx - self.vx) * k
        self.vy += (ty - self.vy) * k
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = max(20.0, min(W - 20.0, self.x))
        self.y = max(20.0, min(H - 20.0, self.y))
        self.angle = math.atan2(aim_y - self.y, aim_x - self.x)
        self.cooldown = max(0.0, self.cooldown - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shield = max(0.0, self.shield - dt)
        self.rapid = max(0.0, self.rapid - dt)
        self.spread = max(0.0, self.spread - dt)

    def damage(self, amount):
        if self.invuln > 0:
            return False
        if self.shield > 0:
            self.shield = 0.0
            self.invuln = PLAYER_INVULN * 0.7
            self.flash = 0.25
            return "shield"
        self.hp -= amount
        self.invuln = PLAYER_INVULN
        self.flash = 0.35
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return True

    def fire_rate(self):
        return PLAYER_FIRE_RATE * (0.5 if self.rapid > 0 else 1.0)

    def draw(self, surf):
        if not self.alive:
            return
        blink = (self.invuln > 0 and int(self.invuln * 18) % 2 == 0)
        base = [(19, 0), (-7, -13), (-2, -5), (-15, -10),
                (-11, 0), (-15, 10), (-2, 5), (-7, 13)]
        pts = _rot(base, self.angle, self.x, self.y)
        col = WHITE if blink else CYAN
        draw_glow(surf, self.x, self.y, 30, CYAN if not blink else WHITE)
        pygame.draw.polygon(surf, (8, 26, 48), pts)
        pygame.draw.polygon(surf, col, pts, 2)
        # Cockpit
        cx = self.x + math.cos(self.angle) * 4
        cy = self.y + math.sin(self.angle) * 4
        draw_glow(surf, cx, cy, 9, WHITE)
        # Triebwerk
        tx = self.x - math.cos(self.angle) * 14
        ty = self.y - math.sin(self.angle) * 14
        flick = random.randint(6, 13)
        draw_glow(surf, tx - math.cos(self.angle) * flick * 0.5,
                  ty - math.sin(self.angle) * flick * 0.5, 11, YELLOW)
        if self.shield > 0:
            ring(surf, self.x, self.y, 27, CYAN, 3,
                 alpha=int(120 + 110 * abs(math.sin(self.flash * 20 + pygame.time.get_ticks() / 120))))


# ================================================================= Kugeln
class Bullet:
    __slots__ = ("x", "y", "vx", "vy", "r", "dmg", "color", "life", "owner")

    def __init__(self, x, y, vx, vy, dmg, owner, color, r=5.0, life=1.6):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r = r
        self.dmg = dmg
        self.color = color
        self.life = life
        self.owner = owner

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return (0 <= self.x <= W and -40 <= self.y <= H + 40 and self.life > 0)

    def draw(self, surf):
        if self.owner == "p":
            nx = self.x - self.vx * 0.016
            ny = self.y - self.vy * 0.016
            pygame.draw.line(surf, self.color, (nx, ny), (self.x, self.y), 4)
            draw_glow(surf, self.x, self.y, 15, self.color)
            draw_glow(surf, self.x, self.y, 6, WHITE)
        else:
            draw_glow(surf, self.x, self.y, 18, self.color)
            draw_glow(surf, self.x, self.y, 7, WHITE)


# ================================================================= Gegner
KINDS = {
    "chaser": dict(hp=3, speed=130, r=17, score=100, color=ORANGE, contact=14),
    "dart":   dict(hp=2, speed=300, r=13, score=140, color=YELLOW, contact=16),
    "shooter": dict(hp=6, speed=100, r=19, score=230, color=GREEN, contact=12),
    "orb":    dict(hp=7, speed=95, r=22, score=280, color=PURPLE, contact=15),
    "tank":   dict(hp=18, speed=62, r=31, score=420, color=RED, contact=26),
}

SUMMONABLE = ("chaser", "dart")


class Enemy:
    def __init__(self, kind, x, y, wave=1):
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.t = random.uniform(0, 6.28)
        self.flash = 0.0
        self.fire_t = random.uniform(0.7, 1.8)
        self.spin = random.uniform(0, 6.28)
        if kind == "boss":
            self.max_hp = 120 + wave * 38
            self.r = 62
            self.score = 5000
            self.color = MAGENTA
            self.contact = 35
            self.speed = 0
        else:
            cfg = KINDS[kind]
            scale = min(2.4, 1.0 + 0.11 * (wave - 1))
            self.max_hp = cfg["hp"] * scale
            self.hp = self.max_hp
            self.r = cfg["r"]
            self.score = cfg["score"]
            self.color = cfg["color"]
            self.contact = cfg["contact"]
            self.speed = cfg["speed"]
        if kind == "boss":
            self.hp = self.max_hp
        self.hp = float(self.hp)

    # ------------------------------------------------------------- Logik
    def update(self, dt, player, add_bullet, game):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        k = self.kind

        if k == "boss":
            self._boss(dt, player, add_bullet, game)
            return

        if k == "chaser":
            dx, dy = player.x - self.x, player.y - self.y
            d = math.hypot(dx, dy) or 1.0
            wob = math.sin(self.t * 3.0) * 0.5
            tx, ty = dx / d * self.speed, dy / d * self.speed + wob * 40
            self.vx += (tx - self.vx) * min(1.0, 2.6 * dt)
            self.vy += (ty - self.vy) * min(1.0, 2.6 * dt)

        elif k == "dart":
            if self.y < 60:
                self.vy += (self.speed - self.vy) * min(1.0, 3.5 * dt)
                self.vx = math.sin(self.t * 4.0) * 140
            else:
                dx, dy = player.x - self.x, player.y - self.y
                d = math.hypot(dx, dy) or 1.0
                tx, ty = dx / d * self.speed, dy / d * self.speed
                self.vx += (tx - self.vx) * min(1.0, 4.5 * dt)
                self.vy += (ty - self.vy) * min(1.0, 4.5 * dt)

        elif k == "shooter":
            home_y = 120 + 40 * math.sin(self.t * 0.9)
            home_x = W * 0.5 + math.sin(self.t * 0.7 + self.x) * (W * 0.32)
            self.vx += ((home_x - self.x) * 1.4 - self.vx) * min(1.0, 2.0 * dt)
            self.vy += ((home_y - self.y) * 1.4 - self.vy) * min(1.0, 2.0 * dt)
            self.fire_t -= dt
            if self.fire_t <= 0:
                self._aim(player, add_bullet, 345, 0.0, 1)
                self.fire_t = random.uniform(1.3, 1.9)
                game.enemy_shoot()

        elif k == "orb":
            home_x = player.x + math.cos(self.t * 1.1) * 300
            home_y = max(110.0, player.y - 240 + math.sin(self.t * 1.4) * 70)
            self.vx += ((home_x - self.x) * 1.2 - self.vx) * min(1.0, 2.0 * dt)
            self.vy += ((home_y - self.y) * 1.2 - self.vy) * min(1.0, 2.0 * dt)
            self.spin += dt * 1.6
            self.fire_t -= dt
            if self.fire_t <= 0:
                for i in (-1, 0, 1):
                    a = self.spin + i * 0.26
                    add_bullet(self.x, self.y,
                               math.cos(a) * ENEMY_BULLET_SPEED * 0.9,
                               math.sin(a) * ENEMY_BULLET_SPEED * 0.9,
                               MAGENTA, 6.0)
                self.fire_t = random.uniform(1.7, 2.3)
                game.enemy_shoot()

        elif k == "tank":
            dx, dy = player.x - self.x, (player.y - 210) - self.y
            d = math.hypot(dx, dy) or 1.0
            self.vx += (dx / d * self.speed - self.vx) * min(1.0, 1.6 * dt)
            self.vy += (dy / d * self.speed - self.vy) * min(1.0, 1.6 * dt)
            self.spin += dt * 0.8
            self.fire_t -= dt
            if self.fire_t <= 0:
                base = math.atan2(player.y - self.y, player.x - self.x)
                for i in range(5):
                    a = base + (i - 2) * 0.2
                    add_bullet(self.x, self.y, math.cos(a) * ENEMY_BULLET_SPEED,
                               math.sin(a) * ENEMY_BULLET_SPEED, RED, 7.0)
                self.fire_t = random.uniform(2.1, 2.7)
                game.enemy_shoot(0.7)

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = max(-60, min(W + 60, self.x))
        self.y = max(-80, min(H + 60, self.y))

    def _aim(self, player, add_bullet, speed, offset, count):
        base = math.atan2(player.y - self.y, player.x - self.x) + offset
        for i in range(count):
            a = base + (i - (count - 1) / 2) * 0.16
            add_bullet(self.x, self.y, math.cos(a) * speed, math.sin(a) * speed,
                       GREEN, 6.0)

    def _boss(self, dt, player, add_bullet, game):
        self.t += dt * 0  # t wurde bereits inkrementiert
        tx = W * 0.5 + math.sin(self.t * 0.55) * (W * 0.3)
        ty = 145 + math.sin(self.t * 0.85) * 24
        self.vx = (tx - self.x) * 1.6
        self.vy = (ty - self.y) * 1.6
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.spin += dt * 1.2
        frac = self.hp / self.max_hp
        self.fire_t -= dt

        if frac > 0.66:
            if self.fire_t <= 0:
                self._aim(player, add_bullet, 360, 0.0, 3)
                self.fire_t = 0.95
                game.enemy_shoot(0.9)
        elif frac > 0.33:
            if self.fire_t <= 0:
                n = 16
                for i in range(n):
                    a = self.spin + i * (2 * math.pi / n)
                    add_bullet(self.x, self.y, math.cos(a) * 235,
                               math.sin(a) * 235, MAGENTA, 6.5)
                self._aim(player, add_bullet, 330, 0.0, 1)
                self.fire_t = 1.15
                game.enemy_shoot(1.0)
        else:
            if self.fire_t <= 0:
                for i in range(3):
                    a = self.spin * 2.4 + i * (2 * math.pi / 3)
                    add_bullet(self.x, self.y, math.cos(a) * 265,
                               math.sin(a) * 265, RED, 6.5)
                self.spin += 0.32
                self.fire_t = 0.17
                if int(self.t * 4) % 4 == 0:
                    game.enemy_shoot(0.4)

    # ------------------------------------------------------------- Zeichnen
    def draw(self, surf):
        c = _lerp_col(self.color, WHITE, self.flash * 6.0)
        fill = _lerp_col(NEUTRAL_FILL, WHITE, self.flash * 6.0)
        r = self.r
        draw_glow(surf, self.x, self.y, int(r * 1.7), self.color)

        if self.kind == "chaser":
            pts = _rot([(r, 0), (0, r * 0.75), (-r, 0), (0, -r * 0.75)],
                       math.atan2(self.vy, self.vx), self.x, self.y)
            pygame.draw.polygon(surf, fill, pts)
            pygame.draw.polygon(surf, c, pts, 2)
            draw_glow(surf, self.x, self.y, 8, c)
        elif self.kind == "dart":
            pts = _rot([(r * 1.3, 0), (-r * 0.8, -r * 0.8), (-r * 0.3, 0),
                        (-r * 0.8, r * 0.8)],
                       math.atan2(self.vy, self.vx), self.x, self.y)
            pygame.draw.polygon(surf, fill, pts)
            pygame.draw.polygon(surf, c, pts, 2)
            draw_glow(surf, self.x, self.y, 6, c)
        elif self.kind == "shooter":
            pts = _rot([(r * math.cos(i * 1.047), r * math.sin(i * 1.047))
                        for i in range(6)], self.t, self.x, self.y)
            pygame.draw.polygon(surf, fill, pts)
            pygame.draw.polygon(surf, c, pts, 2)
            ring(surf, self.x, self.y, int(r * 0.5), c, 2)
            draw_glow(surf, self.x, self.y, 7, c)
        elif self.kind == "orb":
            pygame.draw.circle(surf, fill, (int(self.x), int(self.y)), int(r))
            pygame.draw.circle(surf, c, (int(self.x), int(self.y)), int(r), 2)
            for i in range(3):
                a = self.spin * 1.5 + i * 2.094
                dx = self.x + math.cos(a) * (r - 5)
                dy = self.y + math.sin(a) * (r - 5)
                draw_glow(surf, dx, dy, 7, c)
            draw_glow(surf, self.x, self.y, 11, WHITE)
        elif self.kind == "tank":
            pts = _rot([(-r, -r * 0.7), (r, -r * 0.7), (r, r * 0.7), (-r, r * 0.7)],
                       0, self.x, self.y)
            pygame.draw.polygon(surf, fill, pts)
            pygame.draw.polygon(surf, c, pts, 3)
            pygame.draw.circle(surf, fill, (int(self.x), int(self.y)), int(r * 0.55))
            pygame.draw.circle(surf, c, (int(self.x), int(self.y)), int(r * 0.55), 2)
            draw_glow(surf, self.x, self.y, 12, c)
        elif self.kind == "boss":
            self._draw_boss(surf, c, fill)

        # HP-Balken für robuste Gegner
        if self.kind in ("tank", "boss") and self.hp < self.max_hp:
            bw = int(r * 2)
            bx, by = int(self.x - r), int(self.y - r - 12)
            pygame.draw.rect(surf, (30, 30, 46), (bx, by, bw, 5))
            pygame.draw.rect(surf, RED, (bx, by, int(bw * self.hp / self.max_hp), 5))

    def _draw_boss(self, surf, c, fill):
        r = self.r
        pts = _rot([(r * math.cos(i * 0.785), r * math.sin(i * 0.785))
                    for i in range(8)], self.t * 0.35, self.x, self.y)
        pygame.draw.polygon(surf, fill, pts)
        pygame.draw.polygon(surf, c, pts, 3)
        inner = _rot([(r * 0.62 * math.cos(-i * 1.047), r * 0.62 * math.sin(-i * 1.047))
                      for i in range(6)], -self.t * 0.9, self.x, self.y)
        pygame.draw.polygon(surf, NEUTRAL_FILL2, inner)
        pygame.draw.polygon(surf, c, inner, 2)
        draw_glow(surf, self.x, self.y, int(26 + 8 * math.sin(self.t * 6)), c)
        draw_glow(surf, self.x, self.y, 14, WHITE)
        for i in range(4):
            a = self.t * 1.6 + i * 1.5708
            dx = self.x + math.cos(a) * (r + 12)
            dy = self.y + math.sin(a) * (r + 12)
            draw_glow(surf, dx, dy, 10, YELLOW)


# ================================================================= Powerup
PU_COLORS = {"rapid": YELLOW, "spread": GREEN, "shield": CYAN, "heal": MAGENTA}
PU_LABEL = {"rapid": "R", "spread": "S", "shield": "D", "heal": "+"}
PU_NAMES = {"rapid": "FEUERGESCHWINDIGKEIT", "spread": "DREIFACH-SCHUSS",
            "shield": "SCHILD", "heal": "+30 HP"}


class PowerUp:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.life = 13.0
        self.t = random.uniform(0, 6.28)
        self.r = 15
        self.color = PU_COLORS[kind]

    def update(self, dt, player):
        self.t += dt
        self.life -= dt
        self.y += 18 * dt
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy)
        if d < 190 and d > 0.1:
            pull = (1.0 - d / 190) * 620
            self.x += dx / d * pull * dt
            self.y += dy / d * pull * dt
        return self.life > 0

    def draw(self, surf):
        if self.life < 3.0 and int(self.t * 8) % 2 == 0:
            return
        draw_glow(surf, self.x, self.y, 34, self.color)
        r = self.r
        pts = _rot([(0, -r), (r, 0), (0, r), (-r, 0)], self.t * 1.6, self.x, self.y)
        pygame.draw.polygon(surf, (8, 14, 28), pts)
        pygame.draw.polygon(surf, self.color, pts, 2)
        text(surf, PU_LABEL[self.kind], 20, WHITE, (self.x, self.y), "center")
