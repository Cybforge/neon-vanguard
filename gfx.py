"""Grafik-Toolkit: Glow-Sprites, Bloom, Sternenhimmel, Partikel, Floating Text.

Externe Imports: pygame, numpy, math, random.
"""
import math
import random

import numpy as np
import pygame

from settings import BG_BOT, BG_TOP

# ----------------------------------------------------------------- Fonts
_font_cache = {}


def get_font(size, bold=True):
    key = (int(size), bold)
    f = _font_cache.get(key)
    if f is None:
        try:
            f = pygame.font.SysFont("bahnschrift,consolas,segoeui", int(size), bold=bold)
        except Exception:
            f = pygame.font.Font(None, int(size))
        _font_cache[key] = f
    return f


def text(surf, msg, size, color, pos, anchor="topleft", alpha=255, glow=True):
    f = get_font(size)
    img = f.render(msg, True, color)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(int(alpha))
    rect = img.get_rect(**{anchor: pos})
    if glow and size >= 36:
        halo = get_font(size).render(msg, True, tuple(min(255, c + 60) for c in color))
        halo.set_alpha(60)
        surf.blit(halo, rect.move(1, 1))
    surf.blit(img, rect)
    return rect


# ----------------------------------------------------------------- Glow
_glow_cache = {}
_SIZES = (4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128)


def glow_sprite(color, radius):
    key = (tuple(color), int(radius))
    s = _glow_cache.get(key)
    if s is not None:
        return s
    r = int(radius)
    size = max(4, r * 2)
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx - r - 0.5) ** 2 + (yy - r - 0.5) ** 2) / float(r)
    a = np.clip(1.0 - d, 0.0, 1.0) ** 2.1
    img = np.zeros((size, size, 4), np.uint8)
    img[..., 0] = color[0]
    img[..., 1] = color[1]
    img[..., 2] = color[2]
    img[..., 3] = (a * 255).astype(np.uint8)
    s = pygame.image.frombuffer(img.tobytes(), (size, size), "RGBA").convert_alpha()
    _glow_cache[key] = s
    return s


def draw_glow(surf, x, y, radius, color):
    r = int(radius)
    if r < 3:
        return
    # nächstgelegene feste Größe wählen (Cache-freundlich, kein Scaling)
    best = _SIZES[0]
    for s in _SIZES:
        if abs(s - r) < abs(best - r):
            best = s
    sp = glow_sprite(color, best)
    surf.blit(sp, (x - best, y - best))


def ring(surf, x, y, radius, color, width=2, alpha=255):
    s = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, alpha), (radius + 4, radius + 4), radius, width)
    surf.blit(s, (x - radius - 4, y - radius - 4))


# ----------------------------------------------------------------- Hintergrund
def make_background(w, h):
    t = np.linspace(0, 1, h)
    top = np.array(BG_TOP, float)
    bot = np.array(BG_BOT, float)
    col = top[None, :] * (1 - t)[:, None] + bot[None, :] * t[:, None]  # (h,3)
    arr = np.repeat(col[None, :, :], w, axis=0).astype(np.uint8)      # (w,h,3)
    bg = pygame.surfarray.make_surface(arr)
    # Nebula-Flecken (weiche Farbwolken)
    for (x, y, r, c) in (
        (w * 0.22, h * 0.32, 300, (70, 30, 130)),
        (w * 0.78, h * 0.62, 340, (30, 55, 140)),
        (w * 0.55, h * 0.10, 250, (120, 25, 90)),
    ):
        big = glow_sprite(c, 96)
        for k in range(3):
            size = max(16, int(r * (0.6 + 0.28 * k)))
            sm = pygame.transform.smoothscale(big, (size, size))
            sm.set_alpha(50)
            bg.blit(sm, (x - size / 2, y - size / 2))
    return bg


# ----------------------------------------------------------------- Sternenhimmel
class Starfield:
    def __init__(self, w, h, n=240):
        self.w, self.h = w, h
        self.t = 0.0
        self.stars = []
        for _ in range(n):
            depth = random.uniform(0.2, 1.0)
            self.stars.append([
                random.uniform(0, w), random.uniform(0, h),
                25 + depth * 170, 1 + depth * 1.6,
                random.uniform(0, 6.283), depth,
            ])

    def update(self, dt, boost=1.0):
        self.t += dt
        for s in self.stars:
            s[1] += s[2] * boost * dt
            if s[1] > self.h:
                s[1] -= self.h
                s[0] = random.uniform(0, self.w)

    def draw(self, surf):
        for s in self.stars:
            tw = 0.6 + 0.4 * math.sin(self.t * (1.4 + s[5] * 3.5) + s[4])
            b = int(70 + 150 * tw * (0.35 + 0.65 * s[5]))
            sz = 1 if s[3] < 1.7 else 2
            surf.fill((b, min(255, b + 25), min(255, b + 45)), (int(s[0]), int(s[1]), sz, sz))


# ----------------------------------------------------------------- Partikel
class Particles:
    def __init__(self):
        self.items = []

    def burst(self, x, y, color, n=16, speed=240, life=0.55, size=16, drag=1.8,
              cone=None, angle=0.0):
        for _ in range(n):
            if cone is None:
                a = random.uniform(0, 6.283)
            else:
                a = angle + random.uniform(-cone / 2, cone / 2)
            sp = speed * random.uniform(0.25, 1.25)
            self.items.append([
                x, y, math.cos(a) * sp, math.sin(a) * sp,
                life * random.uniform(0.55, 1.25), life,
                color, size * random.uniform(0.55, 1.15), drag,
            ])

    def trail(self, x, y, color, vx=0.0, vy=0.0, life=0.3, size=12):
        self.items.append([x, y, vx, vy, life, life, color, size, 3.0])

    def update(self, dt):
        items = self.items
        for p in items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            d = max(0.0, 1.0 - p[8] * dt)
            p[2] *= d
            p[3] *= d
            p[4] -= dt
        self.items = [p for p in items if p[4] > 0.0]

    def draw(self, surf):
        for p in self.items:
            k = max(0.0, p[4] / p[5])
            sz = max(3, int(p[7] * (0.35 + 0.65 * k)))
            draw_glow(surf, p[0], p[1], sz, p[6])

    def clear(self):
        self.items.clear()


# ----------------------------------------------------------------- Floating Text
class FloatingText:
    def __init__(self):
        self.items = []

    def add(self, x, y, msg, color, size=22, life=0.9, vy=-55):
        self.items.append([x, y, msg, color, size, life, life, vy])

    def update(self, dt):
        for it in self.items:
            it[1] += it[7] * dt
            it[7] *= max(0.0, 1.0 - 2.0 * dt)
            it[5] -= dt
        self.items = [it for it in self.items if it[5] > 0.0]

    def draw(self, surf):
        for it in self.items:
            k = it[5] / it[6]
            a = int(255 * min(1.0, k * 1.6))
            grow = 1.0 if k > 0.75 else 1.0 + (1.0 - k) * 0.0
            size = int(it[4] * (1.0 + 0.25 * (1.0 - k)))
            text(surf, it[2], size, it[3], (it[0], it[1]), "center", a, glow=True)
            del grow

    def clear(self):
        self.items.clear()


# ----------------------------------------------------------------- Bloom
def apply_bloom(scene, strength=1.0, threshold=118, factor=4):
    """Helle Partien herausziehen, weichzeichnen, additiv zurückblenden.

    Arbeitet komplett in factor-facher Verkleinerung -> kostet ~4 ms statt ~21 ms.
    """
    w, h = scene.get_size()
    sw, sh = max(8, w // factor), max(8, h // factor)
    small = pygame.transform.smoothscale(scene, (sw, sh))
    arr = pygame.surfarray.array3d(small)
    mask = arr.max(axis=2) >= threshold
    if not mask.any():
        return
    arr *= mask[:, :, None]                      # nur Helliges behalten (uint8)
    if strength != 1.0:
        arr = np.clip(arr * strength, 0, 255).astype(np.uint8)
    glow = pygame.surfarray.make_surface(arr)
    mid = pygame.transform.smoothscale(glow, (w // 2, h // 2))
    up = pygame.transform.smoothscale(mid, (w, h))
    scene.blit(up, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
