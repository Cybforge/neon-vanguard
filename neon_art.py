"""NEON VANGUARD - prozeduraler Art-Generator.

Erzeugt Wallpaper und Key-Art im Neon-Look des Spiels - ohne Display,
ohne Bild-Dateien als Vorlage: alles mathematisch berechnet (wie die
Sounds und Grafiken im Spiel selbst).

Motive:
  grid     Synthwave-Horizont mit perspektivischem Neon-Grid und Sonne
  nebula   Sternennebel aus fraktalem Rauschen mit Glow
  burst    Partikel-Explosion mit Schockwellen (Game-Over-Feeling)
  tunnel   Vortex-Tunnel mit rotierenden Neon-Ringen

Beispiele:
  python neon_art.py --list
  python neon_art.py grid --size 1920x1080 --seed 7 --out art/grid.png
  python neon_art.py all --size 1280x720 --out art

Externe Imports: numpy (settings wird für die Palette genutzt, falls
im selben Verzeichnis vorhanden).
"""
import argparse
import os
import struct
import sys
import zlib

import numpy as np

try:
    import settings as _s
    PALETTE = {
        "black": _s.BLACK, "cyan": _s.CYAN, "magenta": _s.MAGENTA,
        "yellow": _s.YELLOW, "green": _s.GREEN, "orange": _s.ORANGE,
        "red": _s.RED, "purple": _s.PURPLE, "blue": _s.BLUE,
        "white": _s.WHITE, "bg_top": _s.BG_TOP, "bg_bot": _s.BG_BOT,
    }
except Exception:                                    # standalone nutzbar
    PALETTE = {
        "black": (4, 5, 12), "cyan": (0, 255, 255), "magenta": (255, 40, 170),
        "yellow": (255, 225, 70), "green": (80, 255, 150),
        "orange": (255, 150, 40), "red": (255, 70, 90),
        "purple": (170, 100, 255), "blue": (90, 150, 255),
        "white": (245, 250, 255), "bg_top": (8, 8, 26),
        "bg_bot": (22, 6, 44),
    }

MOTIFS = ("grid", "nebula", "burst", "tunnel", "city", "ridges", "aurora",
          "eclipse", "plasma", "topo", "circuit", "rain", "fireworks",
          "galaxy", "highway", "shards", "eq", "lightning", "orbit",
          # Retro-Pixel-Stil (Low-Res, Paletten, Bayer-Dithering)
          "px_space", "px_invader", "px_sunset", "px_maze", "px_snake",
          "px_platform", "px_boss", "px_racer", "px_gbland", "px_moon")


# ---------------------------------------------------------------- PNG ---
def save_png(path, img):
    """Schreibt ein uint8-Bild (H, W, 3) als PNG - ohne Bilibliothek."""
    h, w, _ = img.shape
    rows = np.zeros((h, 1 + 3 * w), dtype=np.uint8)
    rows[:, 1:] = img.reshape(h, 3 * w)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    head = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    blob = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) +
            chunk(b"IDAT", zlib.compress(rows.tobytes(), 9)) +
            chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)


# ------------------------------------------------------------- Math -----
def _blur1d(a, r, axis):
    """Kantengespiegelte Box-Blur-Variante (ein Durchgang)."""
    if r < 1:
        return a
    a = np.moveaxis(a, axis, -1)
    n = a.shape[-1]
    ap = np.concatenate([np.repeat(a[..., :1], r, -1), a,
                         np.repeat(a[..., -1:], r, -1)], axis=-1)
    c = np.cumsum(ap, axis=-1, dtype=np.float64)
    c = np.concatenate([np.zeros(c.shape[:-1] + (1,), np.float64), c], -1)
    out = (c[..., 2 * r + 1:] - c[..., :n]) / (2 * r + 1)
    return np.moveaxis(out.astype(np.float32, copy=False), -1, axis)


def blur(a, radius, passes=3):
    """Weicher Glow: mehrere Box-Durchgänge auf X und Y-Achse."""
    r = max(1, int(round(radius)))
    for _ in range(max(1, passes)):
        a = _blur1d(_blur1d(a, r, -1), r, -2)
    return a


def screen(dst, src):
    """Screen-Blendung (1 - (1-a)(1-b)) - additiv ohne Überbelichtung."""
    return 1.0 - (1.0 - dst) * (1.0 - src)


def colorize(mask, color):
    """Maske (H, W) * Farbe (3,) -> (H, W, 3)."""
    c = np.asarray(color, np.float32) / 255.0
    return mask[..., None] * c


def smooth_noise(w, h, cx, cy, rng):
    """Glatte Interpolation eines cx × cy Zufallsrasters."""
    grid = rng.random((cy + 1, cx + 1)).astype(np.float32)
    ys = np.linspace(0, cy, h, dtype=np.float32)
    xs = np.linspace(0, cx, w, dtype=np.float32)
    y0 = np.clip(np.floor(ys).astype(np.int32), 0, cy - 1)
    x0 = np.clip(np.floor(xs).astype(np.int32), 0, cx - 1)
    fy = ys - y0
    fx = xs - x0
    fy = (fy * fy * (3.0 - 2.0 * fy))[:, None]
    fx = (fx * fx * (3.0 - 2.0 * fx))[None, :]
    g00 = grid[np.ix_(y0, x0)]
    g10 = grid[np.ix_(y0 + 1, x0)]
    g01 = grid[np.ix_(y0, x0 + 1)]
    g11 = grid[np.ix_(y0 + 1, x0 + 1)]
    top = g00 * (1 - fx) + g01 * fx
    bot = g10 * (1 - fx) + g11 * fx
    return top * (1 - fy) + bot * fy


def value_noise(w, h, cells, rng):
    """Glattes Rauschen mit 'cells' Zellen auf der langen Achse."""
    cy = max(2, int(cells * h / max(w, h)))
    cx = max(2, int(cells * w / max(w, h)))
    return smooth_noise(w, h, cx, cy, rng)


def fbm(w, h, cells, octaves, rng):
    """Fraktale Summe (Rauschen-Summe) - Wolken-/Nebelbasis."""
    out = np.zeros((h, w), np.float32)
    amp, tot, c = 1.0, 0.0, cells
    for _ in range(octaves):
        out += amp * value_noise(w, h, c, rng)
        tot += amp
        amp *= 0.5
        c = int(c * 2.1) + 2
    return out / tot


def stars(w, h, rng, count, bright=1.0, r=1):
    """Punktförmige Sterne inkl. Glow (Blur über Streuung)."""
    layer = np.zeros((h, w), np.float32)
    ys = rng.integers(0, h, count)
    xs = rng.integers(0, w, count)
    power = rng.random(count) ** 4.0
    np.add.at(layer, (ys, xs), (0.25 + power) * bright)
    return blur(layer, r, passes=2)


def ramp(t, stops):
    """Farbfahrplan: t (H, W) 0..1 -> RGB (H, W, 3) in 0..1."""
    cols = np.asarray([np.asarray(c, np.float32) / 255.0 for c in stops],
                      np.float32)
    n = len(stops) - 1
    x = np.clip(t, 0.0, 1.0) * n
    i = np.clip(np.floor(x).astype(np.int32), 0, n - 1)
    f = (x - i)[..., None]
    return cols[i] * (1.0 - f) + cols[i + 1] * f


def line_mask(w, h, pts, width=4.0, core_boost=2.5):
    """Maske für eine Polylinie: scharfer Kern plus weicher Glow."""
    delta = np.zeros((h, w), np.float32)
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        n = int(max(abs(dx), abs(dy)) / 0.7) + 2
        t = np.linspace(0.0, 1.0, n)
        xi = np.clip((x0 + dx * t).astype(np.int32), 0, w - 1)
        yi = np.clip((y0 + dy * t).astype(np.int32), 0, h - 1)
        np.add.at(delta, (yi, xi), 1.0)
    core = blur(np.clip(delta, 0, 1), 1, passes=1)
    glow = blur(delta, width, passes=2)
    return np.clip(core * core_boost, 0.0, 1.0) + glow * 0.7


def dot(canvas, x, y, r, amp=1.0):
    """Weichen Punkt (Glow) in eine 2D-Maske schreiben."""
    hh, w = canvas.shape
    x0, x1 = int(max(0, x - r * 3)), int(min(w, x + r * 3 + 1))
    y0, y1 = int(max(0, y - r * 3)), int(min(hh, y + r * 3 + 1))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d2 = (xx - x) ** 2 + (yy - y) ** 2
    canvas[y0:y1, x0:x1] += amp * np.exp(-d2 / (2.0 * r * r))


# ----------------------------------------------------------- Look -------
def vignette(w, h, strength=0.55, power=1.6):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (xs - w * 0.5) / (w * 0.5)
    dy = (ys - h * 0.5) / (h * 0.5)
    d = np.sqrt(dx * dx + dy * dy) * 0.72
    return np.clip(1.0 - strength * np.power(np.clip(d, 0, 1.4), power),
                   0.0, 1.0)


def scanlines(w, h, strength=0.05, period=3.0):
    y = np.arange(h, dtype=np.float32)
    return (1.0 - strength * (0.5 + 0.5 * np.cos(2 * np.pi * y / period))
            )[:, None, None]


def grade(img, seed=0, grain=0.012):
    """Tonemapping, Kontrast, feines Korn - der finale Farblook."""
    img = np.maximum(img, 0.0)
    img = img / (1.0 + img * 0.85)                    # weiches Abblenden
    img = np.clip(img, 0.0, 1.0) ** (1.0 / 2.2)       # Gamma
    img = img * img * (3.0 - 2.0 * img)               # S-Kurve
    img += (np.random.default_rng(seed).random(img.shape).astype(np.float32)
            - 0.5) * grain
    return np.clip(img, 0.0, 1.0)


def finish(img, w, h, seed=0, vig=0.5, lines=0.045):
    """Vignette + Scanlines + Grading -> uint8."""
    img = img * vignette(w, h, vig)[..., None]
    img = img * scanlines(w, h, lines)
    out = (grade(img, seed) * 255.0 + 0.5).astype(np.uint8)
    return out


def sky(w, h, top=None, bot=None):
    """Vertikaler Himmel-Verlauf wie im Spiel."""
    top = top or PALETTE["bg_top"]
    bot = bot or PALETTE["bg_bot"]
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    a = np.asarray(top, np.float32) / 255.0
    b = np.asarray(bot, np.float32) / 255.0
    return np.broadcast_to(a * (1 - t) + b * t, (h, w, 3)).copy()


# ---------------------------------------------------------- Motive ------
def smoothstep(x, a, b):
    """Weicher Übergang von a nach b."""
    t = np.clip((np.asarray(x, np.float32) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def m_grid(w, h, rng, seed):
    """Synthwave-Horizont: perspektivisches Grid, Sonne, Bergsilhouette."""
    hzn = int(h * 0.56)
    img = sky(w, h, (7, 6, 26), (46, 7, 64))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)

    # Sternenhimmel überm Horizont
    sky_mask = np.ones((h, w), np.float32)
    sky_mask[hzn:, :] = 0.0
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 4200), 0.9) *
                               sky_mask, PALETTE["white"]))

    # Sonne: gelb -> orange -> magenta, mit breiteren Streifen unten
    cx, cy = w * 0.5, hzn - h * 0.06
    r = h * 0.235
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    grad = np.clip((ys - (cy - r)) / (2 * r), 0.0, 1.0)
    y0 = np.asarray(PALETTE["yellow"], np.float32)
    o0 = np.asarray(PALETTE["orange"], np.float32)
    m0 = np.asarray(PALETTE["magenta"], np.float32)
    k1 = np.clip(grad / 0.5, 0, 1)[..., None]
    k2 = np.clip((grad - 0.5) / 0.5, 0, 1)[..., None]
    sun_col = ((y0 * (1 - k1) + o0 * k1) * (1 - k2) + m0 * k2) / 255.0
    stripes = 1.0 - 0.96 * ((grad > 0.44) &
                            (np.sin((grad - 0.44) * 58.0) > -0.25))
    sun = np.clip(1.0 - dist / r, 0.0, 1.0) ** 0.5 * (dist < r) * stripes
    img = screen(img, sun[..., None] * sun_col)
    halo = np.clip(1.0 - dist / r, 0, 1) * (dist >= r)
    halo = blur(halo, max(w, h) // 45, 2)
    img = screen(img, colorize(halo * 0.45, PALETTE["orange"]))

    # Bergsilhouette: dunkler Körper, Neon-Rim nur über der Kante
    prof = fbm(w, 16, 9, 4, rng)[8]
    prof = (prof - prof.min()) / (np.ptp(prof) + 1e-6)
    prof_y = hzn - (0.07 + 0.27 * prof) * h
    ridge = ys - prof_y[None, :]
    body = smoothstep(ridge, -2.0, 3.0)[..., None]
    shade = (0.10 + 0.16 * smoothstep(ridge, 0.0, h * 0.25))[..., None]
    img = img * (1.0 - body) + img * body * shade
    rim = np.exp(-np.clip(-ridge, 0, None) ** 2 / (2 * (h * 0.011) ** 2))
    rim = np.where(ridge < 0, rim, 0.0)
    img = screen(img, colorize(rim * 0.95, PALETTE["magenta"]))

    # Boden
    below = (ys >= hzn).astype(np.float32)
    floor_col = np.asarray((30, 9, 54), np.float32) / 255.0
    depth = np.maximum(ys - hzn + 1.0, 1.0)
    floor_dim = (0.45 + 0.55 * np.clip(depth / (h - hzn), 0, 1))[..., None]
    img = img * (1 - below[..., None]) + \
        floor_col * floor_dim * below[..., None]

    # Neon-Grid: pixelbreiten-abhängig gezeichnet, damit nichts flackert
    kv = 18.0 * (w / 1280.0)
    u = (xs - w * 0.5) / depth * kv
    sp_v = depth / kv                                   # Linienabstand (px)
    sig_v = np.maximum(0.5 / np.maximum(sp_v, 1e-3), 1e-3)   # sigma in u-Einheiten
    line_v = smoothstep(sp_v, 1.2, 4.5) * \
        np.exp(-((u - np.round(u)) ** 2) / (2 * sig_v ** 2)) * below

    c_h = float(h - hzn) * 1.7
    t = c_h / depth
    sp_h = depth ** 2 / c_h
    sig_h = np.maximum(0.5 / np.maximum(sp_h, 1e-3), 1e-3)   # sigma in t-Einheiten
    line_h = smoothstep(sp_h, 2.0, 6.0) * below * (t > 1.4) * \
        np.exp(-((t - np.round(t)) ** 2) / (2 * sig_h ** 2))
    img = screen(img, colorize(line_v * 0.8, PALETTE["cyan"]))
    img = screen(img, colorize(line_h * 0.6, PALETTE["magenta"]))

    # Sonnen-Reflexion auf dem Boden
    refl = np.exp(-np.abs(xs - cx) / (r * 0.85)) * below * \
        np.clip(1.3 - depth / (h - hzn) * 1.5, 0, 1) * 0.14
    img = screen(img, colorize(refl, PALETTE["magenta"]))

    # Horizont-Linie + Bloom über alles
    horizon = np.exp(-((ys - hzn) ** 2) / (2 * (h * 0.006) ** 2))
    img = screen(img, colorize(horizon * 0.5, PALETTE["cyan"]))
    bright = np.clip(img.mean(-1) - 0.62, 0, 1) * 2.2
    img = screen(img, colorize(blur(bright, max(w, h) // 110, 2) * 0.45,
                               PALETTE["magenta"]))
    return finish(img, w, h, seed, vig=0.5, lines=0.05)


def m_nebula(w, h, rng, seed):
    """Sternennebel: fraktales Rauschen, zweifarbig eingefärbt, Glow."""
    img = sky(w, h, (4, 4, 16), (14, 4, 34))
    dens = fbm(w, h, 5, 6, rng)
    dens = np.clip((dens - 0.44) * 2.6, 0.0, 1.0) ** 1.25
    tints = fbm(w, h, 3, 3, rng)

    cool = colorize(dens * (1 - tints) ** 1.4, PALETTE["purple"])
    warm = colorize(dens * tints ** 1.4, PALETTE["cyan"])
    hot = colorize(np.clip(dens - 0.72, 0, 1) * 3.0, PALETTE["magenta"])
    img = screen(img, screen(screen(cool * 0.85, warm * 0.8), hot * 0.7))

    # Kerne
    core = np.clip(dens - 0.86, 0, 1) * 6.0
    img = screen(img, colorize(blur(core, max(w, h) // 120, 2) * 0.9,
                               PALETTE["white"]))

    # Sternenfeld in zwei Ebenen
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 3000), 0.75, 1),
                               PALETTE["white"]))
    big = stars(w, h, rng, max(6, int(w * h / 90000)), 2.4, max(4, w // 260))
    img = screen(img, colorize(big * 0.8, PALETTE["cyan"]))

    bright = np.clip(img.mean(-1) - 0.5, 0, 1) * 2.0
    img = screen(img, colorize(blur(bright, max(w, h) // 70, 2) * 0.6,
                               PALETTE["purple"]))
    return finish(img, w, h, seed, vig=0.62, lines=0.035)


def m_burst(w, h, rng, seed):
    """Explosion: Strahlen, Schockwellen, Funken - Game-Over-Moment."""
    img = sky(w, h, (5, 3, 16), (24, 5, 34))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.5, h * 0.46
    dx, dy = xs - cx, ys - cy
    rad = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    rmax = np.hypot(w, h) * 0.5

    # Strahlen: Rauschen über den Winkel, gedreht mit dem Radius
    steps = 720
    a = np.linspace(-np.pi, np.pi, steps, endpoint=False, dtype=np.float32)
    prof = rng.random(steps).astype(np.float32) ** 2.8
    prof = np.convolve(np.r_[prof, prof, prof], np.ones(3) / 3, "same")[steps:2 * steps]
    swirl = ang + rad / rmax * 0.8
    idx = ((swirl + np.pi) / (2 * np.pi) * steps).astype(np.int32) % steps
    streak = prof[idx]
    fall = np.exp(-rad / (rmax * 0.30))
    rays = streak * fall * (rad > 6)
    rays = blur(rays[..., None], max(w, h) // 500, 1)[..., 0]
    img = screen(img, colorize(rays * 1.4, PALETTE["orange"]))
    img = screen(img, colorize(rays * 0.9, PALETTE["yellow"]))

    # Kern
    core = np.exp(-(rad / (rmax * 0.10)) ** 2)
    img = screen(img, colorize(core, PALETTE["white"]))
    img = screen(img, colorize(blur(core, max(w, h) // 60, 2) * 0.9,
                               PALETTE["yellow"]))

    # Schockwellen
    for rr, amp, col in ((0.22, 0.6, PALETTE["cyan"]),
                         (0.40, 0.42, PALETTE["magenta"]),
                         (0.58, 0.28, PALETTE["purple"])):
        ring = np.exp(-((rad - rmax * rr) ** 2) / (2 * (rmax * 0.008) ** 2))
        img = screen(img, colorize(ring * amp, col))

    # Funken / Partikel
    n = max(120, int(w * h / 5200))
    py = rng.integers(0, h, n)
    px = rng.integers(0, w, n)
    d = np.sqrt((px - cx) ** 2 + (py - cy) ** 2) + 1.0
    keep = rng.random(n) < np.exp(-d / (rmax * 0.55))
    sparks = np.zeros((h, w), np.float32)
    np.add.at(sparks, (py[keep], px[keep]),
              (0.5 + rng.random(int(keep.sum())) ** 2) * 3.0)
    img = screen(img, colorize(blur(sparks, max(w, h) // 400, 2) * 1.4,
                               PALETTE["white"]))
    img = screen(img, colorize(blur(sparks, max(w, h) // 90, 2) * 0.5,
                               PALETTE["yellow"]))

    # Sternenfeld dezent dahinter
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 9000), 0.5),
                               PALETTE["white"]))
    bright = np.clip(img.mean(-1) - 0.70, 0, 1) * 2.0
    img = screen(img, colorize(blur(bright, max(w, h) // 110, 2) * 0.35,
                               PALETTE["orange"]))
    return finish(img, w, h, seed, vig=0.6, lines=0.05)


def m_tunnel(w, h, rng, seed):
    """Vortex: sich verengende Neon-Ringe, leuchtendes Zentrum."""
    img = np.zeros((h, w, 3), np.float32) + \
        np.asarray(PALETTE["bg_top"], np.float32) / 255.0
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (xs - w * 0.5) / (h * 0.5)
    dy = (ys - h * 0.5) / (h * 0.5)
    rad = np.sqrt(dx * dx + dy * dy) + 1e-4
    ang = np.arctan2(dy, dx)
    logr = np.log(rad)
    unit = h * 0.5                                     # 1 rad-Einheit in px

    # Ringe im Log-Raum -> gleichmäßig werdende Abstände nach außen
    k = 40.0
    wave = np.sin(k * logr + ang * 2.0 + 1.2)
    rings = np.clip(0.5 + 0.5 * wave - 0.45, 0.0, 1.0) ** 1.3 * 1.5
    spacing = (2 * np.pi / k) * rad * unit              # Pixelabstand
    rings *= smoothstep(spacing, 1.2, 4.0)              # kein Flackern
    spokes = (0.5 + 0.5 * np.sin(ang * 8.0 - k * logr * 0.22)) ** 1.6
    falloff = np.clip(0.42 / (rad + 0.10), 0.0, 1.5)
    outer = np.clip(1.45 - rad, 0.0, 1.0)
    mask = rings * falloff * outer * (0.40 + 0.60 * spokes)

    hue = 0.5 + 0.5 * np.sin(ang * 2.0 + logr * 2.4)
    col = (np.asarray(PALETTE["cyan"], np.float32)[None, None] * (1 - hue[..., None]) +
           np.asarray(PALETTE["magenta"], np.float32)[None, None] * hue[..., None]) / 255.0
    img = screen(img, mask[..., None] * col * 1.3)
    img = screen(img, colorize(mask ** 2.2 * 0.5, PALETTE["white"]))

    # Leuchtendes Zentrum
    core = np.exp(-(rad / 0.13) ** 2)
    img = screen(img, colorize(core, PALETTE["white"]))
    halo = np.exp(-(rad / 0.5) ** 2) * 0.45
    img = screen(img, colorize(halo, PALETTE["cyan"]))

    img = screen(img, colorize(stars(w, h, rng, int(w * h / 8000), 0.6),
                               PALETTE["white"]))
    bright = np.clip(img.mean(-1) - 0.6, 0, 1) * 2.0
    img = screen(img, colorize(blur(bright, max(w, h) // 80, 2) * 0.5,
                               PALETTE["magenta"]))
    return finish(img, w, h, seed, vig=0.55, lines=0.045)


def m_city(w, h, rng, seed):
    """Neon-Skyline mit Spiegelung im Wasser."""
    hzn = int(h * 0.62)
    img = sky(w, h, (5, 5, 22), (48, 8, 68))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)

    sky_mask = np.zeros((h, w), np.float32)
    sky_mask[:max(1, hzn - 30)] = 1.0
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 5000), 0.85) *
                               sky_mask, PALETTE["white"]))

    # Mond
    mcx, mcy, mr = w * 0.76, h * 0.20, h * 0.07
    md = np.sqrt((xs - mcx) ** 2 + (ys - mcy) ** 2)
    moon = np.clip(1.0 - md / mr, 0.0, 1.0) ** 0.35 * (md < mr)
    img = screen(img, colorize(blur(moon, max(w, h) // 26, 2) * 0.40,
                               PALETTE["cyan"]))
    img = screen(img, colorize(moon * 0.95, (235, 238, 255)))

    # Gebäude: Körper, Kanten, Fenster
    body = np.zeros((h, w), np.float32)
    edge_c = np.zeros((h, w), np.float32)
    edge_m = np.zeros((h, w), np.float32)
    win_a = np.zeros((h, w), np.float32)
    win_b = np.zeros((h, w), np.float32)
    x = -int(rng.integers(10, 70))
    while x < w:
        bw = int(rng.integers(38, 115))
        top = int(hzn - rng.integers(int(h * 0.10), int(h * 0.45)))
        x0, x1 = max(0, x), min(w, x + bw)
        x += bw + int(rng.integers(0, 6))
        if x1 - x0 < 6 or top > hzn - 20:
            continue
        body[top:hzn, x0:x1] = 1.0
        edge = edge_c if rng.random() < 0.62 else edge_m
        edge[top:hzn, x0] = 1.0
        edge[top:hzn, x1 - 1] = 1.0
        edge[top, x0:x1] = 1.0
        if rng.random() < 0.35:                     # Antenne
            edge[max(0, top - int(h * 0.05)):top,
                 (x0 + x1) // 2] = 1.0
        hh, ww = hzn - top, x1 - x0
        wy = np.arange(6, max(7, hh - 5), 13)
        wx = np.arange(4, max(5, ww - 5), 10)
        if len(wy) and len(wx):
            on = rng.random((len(wy), len(wx))) < 0.45
            tgt = win_a if rng.random() < 0.68 else win_b
            for iy in range(len(wy)):
                for ix in range(len(wx)):
                    if on[iy, ix]:
                        yy = top + int(wy[iy])
                        xx = x0 + int(wx[ix])
                        tgt[yy:yy + 6, xx:xx + 4] = 1.0

    depth = np.clip(ys / max(1, hzn), 0, 1)
    fill = (0.050 + 0.025 * depth)[..., None] * \
        np.asarray((1.0, 0.9, 1.35), np.float32)
    img = img * (1 - body[..., None]) + fill * body[..., None]

    img = screen(img, colorize(blur(win_a, 1, 1) * 0.95, (255, 210, 130)))
    img = screen(img, colorize(blur(win_b, 1, 1) * 0.90, PALETTE["cyan"]))
    img = screen(img, colorize(blur(win_a, 6, 2) * 0.30, (255, 190, 110)))
    img = screen(img, colorize(blur(win_b, 6, 2) * 0.30, PALETTE["cyan"]))
    img = screen(img, colorize(edge_c * 0.9, PALETTE["cyan"]))
    img = screen(img, colorize(edge_m * 0.9, PALETTE["magenta"]))
    img = screen(img, colorize(blur(edge_c, 4, 2) * 0.45, PALETTE["cyan"]))
    img = screen(img, colorize(blur(edge_m, 4, 2) * 0.45, PALETTE["magenta"]))

    glow = np.exp(-((ys - hzn) ** 2) / (2 * (h * 0.010) ** 2))
    img = screen(img, colorize(glow * 0.5, PALETTE["magenta"]))

    # Spiegelung im Wasser
    rh = h - hzn
    src = img[hzn - rh:hzn][::-1].copy()
    ramp_y = np.arange(rh, dtype=np.float32)
    off = np.sin(ramp_y * 0.11 + seed * 0.7) * (1.5 + 4.0 * ramp_y / rh)
    idx = np.clip(np.arange(w)[None, :] + off.astype(np.int32)[:, None],
                  0, w - 1)
    refl = np.take_along_axis(src, np.repeat(idx[..., None], 3, axis=2), axis=1)
    fade = np.clip(1.0 - ramp_y / (rh * 1.15), 0, 1)[:, None, None] ** 1.3
    refl = blur(refl * fade * 0.6, 2, 2)
    ripple = 0.5 + 0.5 * np.sin(ys[hzn:] * 0.30 +
                                np.sin(xs[hzn:] * 0.017) * 2.5)
    water = np.asarray((0.05, 0.04, 0.13), np.float32)
    img[hzn:] = refl + water * (0.75 + 0.5 * ripple[..., None])
    return finish(img, w, h, seed, vig=0.55, lines=0.045)


def m_ridges(w, h, rng, seed):
    """Mehrschichtige Bergketten mit Nebel und Tiefenstaffelung."""
    img = sky(w, h, (4, 5, 22), (62, 12, 74))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    sky_mask = np.ones((h, w), np.float32)
    sky_mask[int(h * 0.5):] = 0.0
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 4200), 0.85) *
                               sky_mask, PALETTE["white"]))

    scx, scy, sr = w * 0.64, h * 0.52, h * 0.15
    sd = np.sqrt((xs - scx) ** 2 + (ys - scy) ** 2)
    img = screen(img, colorize(np.exp(-(sd / (sr * 1.6)) ** 2) * 0.70,
                               PALETTE["orange"]))
    img = screen(img, colorize(np.clip(1 - sd / sr, 0, 1) ** 0.6 * 0.75 *
                               (sd < sr), PALETTE["yellow"]))

    cols = [(46, 34, 88), (34, 24, 68), (24, 17, 50), (14, 11, 34), (6, 6, 18)]
    accents = [PALETTE["cyan"], PALETTE["magenta"], PALETTE["purple"],
               PALETTE["blue"], PALETTE["cyan"]]
    layers = len(cols)
    for i in range(layers):
        t = i / (layers - 1)
        prof = smooth_noise(w, 12, 7 + i * 3, 5, rng)[5]
        prof = 1.0 - np.abs(2.0 * prof - 1.0)          # Bergkämme
        prof = prof ** (1.15 + 0.25 * i)
        prof = np.convolve(np.pad(prof, 6, mode="edge"),
                           np.ones(11) / 11, "same")[6:-6]   # Kontur glätten
        prof = (prof - prof.min()) / (np.ptp(prof) + 1e-6)
        base = h * (0.46 + 0.10 * i)
        amp = h * (0.30 - 0.045 * i)
        prof_y = base - amp * prof
        below = ys >= prof_y[None, :]
        col = np.asarray(cols[i], np.float32) / 255.0
        shade = 1.0 - 0.30 * smoothstep(ys - prof_y[None, :], 0.0,
                                        h * 0.30)[..., None]
        img = np.where(below[..., None], col[None, None, :] * shade, img)
        mist = np.exp(-((prof_y[None, :] - ys) / (h * 0.035)) ** 2)
        mist = np.where(ys < prof_y[None, :], mist, 0.0)
        haze = ramp(np.full((1, 1), t, np.float32),
                    [(150, 170, 220), (255, 150, 190)])[0, 0]
        img = screen(img, mist[..., None] * haze[None, None, :] *
                     (0.03 + 0.09 * (1 - 0.5 * t)))
        rim = np.exp(-((ys - prof_y[None, :]) ** 2) / (2 * (h * 0.0032) ** 2))
        rim = np.where(ys < prof_y[None, :], rim, 0.0)
        img = screen(img, colorize(rim * (0.85 - 0.45 * t), accents[i]))
    return finish(img, w, h, seed, vig=0.55, lines=0.045)


def m_aurora(w, h, rng, seed):
    """Polarlicht-Bänder über Sternenhimmel und dunklem Boden."""
    img = sky(w, h, (2, 4, 16), (7, 9, 32))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 2600), 1.0),
                               PALETTE["white"]))
    cols = [PALETTE["green"], PALETTE["cyan"], PALETTE["magenta"],
            PALETTE["purple"]]
    for i, c in enumerate(cols):
        base = h * (0.16 + 0.16 * i)
        amp = h * (0.22 - 0.03 * i)
        curve = smooth_noise(w, 6, 5 + i * 2, 4, rng)[2]
        curve = base + amp * (curve - 0.5) * 2.0
        width = h * (0.075 + 0.018 * i)
        d = (ys - curve[None, :])
        band = np.exp(-(d / width) ** 2)
        # nach unten auslaufende Schleier
        tail = np.where(d > 0, np.exp(-d / (width * 1.9)), 0.0) * 0.55
        rays = 0.22 + 0.78 * smooth_noise(w, h, 45, 6, rng) ** 1.2
        inten = np.clip((band + tail) * rays * (0.66 - 0.08 * i), 0.0, 1.0)
        img = screen(img, colorize(inten, c))
        edge = np.exp(-((d + width * 0.35) / (width * 0.30)) ** 2) * 0.6
        img = screen(img, colorize(np.clip(edge * rays * (0.45 - 0.07 * i),
                                           0, 1), PALETTE["white"]))

    prof = smooth_noise(w, 8, 5, 3, rng)[4]
    ground_y = h * 0.88 - h * 0.05 * prof
    below = ys >= ground_y[None, :]
    gcol = np.asarray((5, 6, 14), np.float32) / 255.0
    img = np.where(below[..., None], gcol[None, None, :], img)
    rim = np.exp(-((ys - ground_y[None, :]) ** 2) / (2 * (h * 0.003) ** 2))
    rim = np.where(ys < ground_y[None, :], rim, 0.0)
    img = screen(img, colorize(rim * 0.7, PALETTE["cyan"]))
    return finish(img, w, h, seed, vig=0.6, lines=0.04)


def m_eclipse(w, h, rng, seed):
    """Sonnenfinsternis mit Corona und anamorphem Lichtstreifen."""
    img = sky(w, h, (3, 3, 16), (18, 5, 44))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 3200), 1.1),
                               PALETTE["white"]))
    cx, cy, r0 = w * 0.5, h * 0.45, h * 0.21
    dx, dy = xs - cx, ys - cy
    dist = np.sqrt(dx * dx + dy * dy)
    rad = np.clip(dist - r0, 0.0, None)
    ang = np.arctan2(dy, dx)

    steps = 1024
    spikes = rng.random(steps).astype(np.float32) ** 3.0
    spikes = np.convolve(np.r_[spikes, spikes, spikes],
                         np.ones(11) / 11, "same")[steps:2 * steps]
    idx = ((ang + np.pi) / (2 * np.pi) * steps).astype(np.int32) % steps
    spike = spikes[idx] * np.exp(-rad / (r0 * 0.75)) * (dist >= r0)
    corona = np.exp(-rad / (r0 * 0.30)) * (dist >= r0)
    streak = np.exp(-(dy ** 2) / (2 * (h * 0.006) ** 2)) * \
        np.exp(-np.abs(dx) / (w * 0.40))
    glow = corona + spike * 1.1 + streak * 0.7
    img = screen(img, colorize(np.clip(glow, 0, 2) * 0.85, (215, 235, 255)))
    img = screen(img, colorize(np.exp(-rad / (r0 * 0.55)) * 0.5 *
                               (dist >= r0), PALETTE["magenta"]))

    disc = (dist < r0).astype(np.float32)
    img = img * (1 - disc[..., None]) + \
        np.asarray((3, 3, 10), np.float32)[None, None] / 255.0 * disc[..., None]
    rim = np.exp(-((dist - r0) ** 2) / (2 * (h * 0.0035) ** 2))
    img = screen(img, colorize(rim * 0.95, (255, 250, 240)))
    return finish(img, w, h, seed, vig=0.55, lines=0.045)


def m_plasma(w, h, rng, seed):
    """Klassische Plasma-Interference im Neon-Look."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x = xs / w * 7.0
    y = ys / h * 4.5
    r = np.sqrt((xs - w * 0.5) ** 2 + (ys - h * 0.5) ** 2) / (h * 0.5)
    v = (np.sin(x * 1.7 + 0.6) + np.sin(y * 2.3 - 0.4) +
         np.sin((x + y) * 1.15 + 1.3) + np.sin(r * 6.5 + 0.8)) / 4.0
    t = 0.5 + 0.5 * v
    img = ramp(t, [(4, 3, 16), (52, 16, 100), (0, 165, 200), (5, 3, 20),
                   (215, 35, 150), (4, 2, 14)]) * 0.92
    bright = np.clip(t - 0.82, 0, 1) * 3.0
    img = screen(img, colorize(blur(bright, max(w, h) // 70, 2) * 0.45,
                               PALETTE["cyan"]))
    return finish(img, w, h, seed, vig=0.6, lines=0.05)


def m_topo(w, h, rng, seed):
    """Neon-Höhenlinien-Topografie."""
    f = fbm(w, h, 4, 5, rng)
    f = (f - f.min()) / (np.ptp(f) + 1e-6)
    lvl = f * 24.0
    d = lvl - np.round(lvl)
    gy, gx = np.gradient(lvl)
    g = np.sqrt(gy * gy + gx * gx) + 1e-5
    sigma = np.maximum(0.5 * g, 0.004)
    line = np.exp(-(d * d) / (2 * sigma * sigma))
    idxv = np.round(lvl).astype(np.int32)
    major = ((idxv % 5) == 0).astype(np.float32)

    img = ramp(f, [(7, 9, 30), (26, 16, 62), (60, 24, 96),
                   (14, 46, 84), (10, 24, 60)]) * 0.8
    img = screen(img, colorize(line * (0.30 + 0.45 * major), PALETTE["cyan"]))
    img = screen(img, colorize(line * major * 0.55, PALETTE["magenta"]))
    peak = (f > 0.92).astype(np.float32)
    img = screen(img, colorize(blur(peak, max(w, h) // 90, 2) * 0.55,
                               PALETTE["yellow"]))
    return finish(img, w, h, seed, vig=0.5, lines=0.04)


def m_circuit(w, h, rng, seed):
    """Leiterplatte: leuchtende Bahnen, Pads und ein Chip."""
    img = np.zeros((h, w, 3), np.float32) + \
        np.asarray((5, 9, 17), np.float32) / 255.0
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cell = max(8, int(min(w, h) // 46))
    dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))
    paths = []
    for _ in range(26):
        px = int(rng.integers(1, max(2, w // cell - 1)))
        py = int(rng.integers(1, max(2, h // cell - 1)))
        pts = [(px, py)]
        d = int(rng.integers(0, 4))
        for _ in range(int(rng.integers(6, 20))):
            if rng.random() < 0.35:
                d = (d + int(rng.integers(1, 3))) % 4
            for _ in range(int(rng.integers(1, 4))):
                nx = pts[-1][0] + dirs[d][0]
                ny = pts[-1][1] + dirs[d][1]
                if 1 <= nx < w // cell - 1 and 1 <= ny < h // cell - 1:
                    pts.append((nx, ny))
                else:
                    break
        if len(pts) >= 3:
            paths.append([(p[0] * cell + cell // 2,
                           p[1] * cell + cell // 2) for p in pts])

    cyan_m = np.zeros((h, w), np.float32)
    mag_m = np.zeros((h, w), np.float32)
    for i, p in enumerate(paths):
        m = line_mask(w, h, p, width=4.0)
        if i % 3:
            np.maximum(cyan_m, m, out=cyan_m)
        else:
            np.maximum(mag_m, m, out=mag_m)

    pads = np.zeros((h, w), np.float32)
    for p in paths:
        for ex, ey in (p[0], p[-1]):
            rr = 5.0 + 2.0 * float(rng.random())
            x0, x1 = int(max(0, ex - rr * 3)), int(min(w, ex + rr * 3 + 1))
            y0, y1 = int(max(0, ey - rr * 3)), int(min(h, ey + rr * 3 + 1))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1]
            dd = np.sqrt((xx - ex) ** 2 + (yy - ey) ** 2)
            ring = np.exp(-((dd - rr) ** 2) / (2 * 1.6 ** 2))
            np.maximum(pads[y0:y1, x0:x1], ring, out=pads[y0:y1, x0:x1])

    # Chip mittig
    cw, chh = int(w * 0.16), int(h * 0.20)
    ccx, ccy = w // 2, int(h * 0.5)
    x0, x1 = max(2, ccx - cw // 2), min(w - 2, ccx + cw // 2)
    y0, y1 = max(2, ccy - chh // 2), min(h - 2, ccy + chh // 2)
    chip = np.zeros((h, w), np.float32)
    chip[y0:y1, x0:x1] = 1.0
    img = img * (1 - chip[..., None] * 0.92) + \
        np.asarray((11, 13, 26), np.float32)[None, None] / 255.0 * \
        chip[..., None] * 0.92
    border = np.zeros((h, w), np.float32)
    border[y0:y0 + 2, x0:x1] = 1.0
    border[y1 - 2:y1, x0:x1] = 1.0
    border[y0:y1, x0:x0 + 2] = 1.0
    border[y0:y1, x1 - 2:x1] = 1.0
    for yy in range(y0 + 6, y1 - 6, 12):            # Pins
        if x0 > 12:
            border[yy:yy + 5, x0 - 9:x0] = 1.0
        if x1 + 9 < w:
            border[yy:yy + 5, x1:x1 + 9] = 1.0

    img = screen(img, colorize(cyan_m * 0.9, PALETTE["cyan"]))
    img = screen(img, colorize(mag_m * 0.9, PALETTE["magenta"]))
    img = screen(img, colorize(pads * 0.9, PALETTE["yellow"]))
    img = screen(img, colorize(border * 0.9, PALETTE["green"]))
    img = screen(img, colorize(blur(cyan_m, 7, 2) * 0.35, PALETTE["cyan"]))
    img = screen(img, colorize(blur(mag_m, 7, 2) * 0.35, PALETTE["magenta"]))
    img = screen(img, colorize(blur(pads, 7, 2) * 0.40, PALETTE["yellow"]))
    img = screen(img, colorize(blur(border, 6, 2) * 0.30, PALETTE["green"]))
    grid_dots = ((np.sin(xs * 0.7) * np.sin(ys * 0.7)) > 0.985).astype(np.float32)
    img = screen(img, colorize(grid_dots * 0.05, (70, 130, 170)))
    return finish(img, w, h, seed, vig=0.5, lines=0.05)


def m_rain(w, h, rng, seed):
    """Neon-Regen mit weichen Bokeh-Kreisen im Hintergrund."""
    img = sky(w, h, (4, 6, 18), (12, 7, 30))
    bok = np.zeros((h, w), np.float32)
    for _ in range(14):
        dot(bok, rng.uniform(0, w), rng.uniform(0, h),
            rng.uniform(h * 0.03, h * 0.08), amp=rng.uniform(0.25, 0.5))
    img = screen(img, colorize(blur(bok, 3, 2) * 0.5, PALETTE["purple"]))

    a = np.zeros((h, w), np.float32)
    b = np.zeros((h, w), np.float32)
    for _ in range(460):
        tgt = a if rng.random() < 0.78 else b
        x = rng.uniform(-0.1, 1.1) * w
        y = rng.uniform(-0.25, 1.25) * h
        ln = rng.uniform(0.035, 0.16) * h
        ang = rng.uniform(-0.22, -0.06)
        x1 = x + np.sin(ang) * ln
        y1 = y + np.cos(ang) * ln
        n = max(4, int(ln / 2))
        t = np.linspace(0.0, 1.0, n)
        xi = np.clip((x + (x1 - x) * t).astype(np.int32), 0, w - 1)
        yi = np.clip((y + (y1 - y) * t).astype(np.int32), 0, h - 1)
        np.add.at(tgt, (yi, xi), (0.25 + 0.75 * t) * rng.uniform(0.5, 1.0))

    img = screen(img, colorize(np.clip(blur(np.clip(a, 0, 1), 1, 1) * 1.6,
                                       0, 1) * 0.9, PALETTE["cyan"]))
    img = screen(img, colorize(np.clip(blur(np.clip(b, 0, 1), 1, 1) * 1.6,
                                       0, 1) * 0.9, PALETTE["magenta"]))
    img = screen(img, colorize(blur(a, 6, 2) * 0.5, PALETTE["cyan"]))
    img = screen(img, colorize(blur(b, 6, 2) * 0.5, PALETTE["magenta"]))
    return finish(img, w, h, seed, vig=0.6, lines=0.05)


def m_fireworks(w, h, rng, seed):
    """Mehrere Feuerwerke über dunklem Nachthimmel."""
    img = sky(w, h, (4, 4, 16), (16, 5, 36))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 3800), 0.9),
                               PALETTE["white"]))
    cols = [PALETTE["cyan"], PALETTE["magenta"], PALETTE["yellow"],
            PALETTE["green"], PALETTE["orange"], PALETTE["purple"]]
    for i in range(6):
        cx = rng.uniform(0.10, 0.90) * w
        cy = rng.uniform(0.12, 0.55) * h
        rr = rng.uniform(0.11, 0.26) * min(w, h)
        col = cols[i % len(cols)]
        dx, dy = xs - cx, ys - cy
        rad = np.sqrt(dx * dx + dy * dy) + 1e-3
        ang = np.arctan2(dy, dx)
        steps = 512
        prof = rng.random(steps).astype(np.float32) ** 2.4
        prof = np.convolve(np.r_[prof, prof, prof],
                           np.ones(5) / 5, "same")[steps:2 * steps]
        idx = ((ang + np.pi) / (2 * np.pi) * steps).astype(np.int32) % steps
        streak = prof[idx] * np.exp(-rad / (rr * 0.5)) * (rad > 4)
        core = np.exp(-(rad / (rr * 0.14)) ** 2)
        layer = streak * 1.5 + core * 1.4
        sparks = np.zeros((h, w), np.float32)
        for _ in range(46):
            aa = rng.uniform(-np.pi, np.pi)
            LL = rr * rng.uniform(0.55, 1.35)
            sx = cx + np.cos(aa) * LL
            sy = cy + np.sin(aa) * LL
            n = 10
            tt = np.linspace(0.0, 1.0, n)
            tx = sx + rng.uniform(-6, 6) * tt
            ty = sy + rng.uniform(6, 34) * tt ** 1.4
            xi = np.clip(tx.astype(np.int32), 0, w - 1)
            yi = np.clip(ty.astype(np.int32), 0, h - 1)
            np.add.at(sparks, (yi, xi), (1.0 - tt) * rng.uniform(0.5, 1.0))
        layer = layer + blur(np.clip(sparks, 0, 1), 2, 2) * 1.3
        layer = np.clip(layer, 0, 1.6)
        img = screen(img, colorize(layer, col))
        img = screen(img, colorize(blur(layer, max(w, h) // 60, 2) * 0.35, col))
    return finish(img, w, h, seed, vig=0.6, lines=0.045)


def m_galaxy(w, h, rng, seed):
    """Spiralgalaxie in schräger Draufsicht."""
    img = sky(w, h, (3, 3, 14), (10, 4, 30))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 2400), 1.0),
                               PALETTE["white"]))
    cx, cy = w * 0.5, h * 0.5
    th = np.deg2rad(-20.0)
    rx = (xs - cx) * np.cos(th) + (ys - cy) * np.sin(th)
    ry = (-(xs - cx) * np.sin(th) + (ys - cy) * np.cos(th)) / 0.58
    r = np.sqrt(rx * rx + ry * ry) / (0.58 * min(w, h)) + 1e-4
    ang = np.arctan2(ry, rx)
    arms = (0.5 + 0.5 * np.sin(2.0 * ang - 4.5 * np.log(r + 0.05))) ** 2.4
    dust = 0.45 + 0.55 * fbm(w, h, 6, 5, rng)
    fall = np.exp(-r * 1.75) * smoothstep(r, 0.02, 0.14)
    disc = fall * (0.30 + 0.70 * arms) * dust
    core = np.exp(-(r / 0.10) ** 2)
    col = ramp(np.clip(r * 1.1, 0, 1),
               [(255, 248, 230), (210, 240, 255), PALETTE["cyan"],
                PALETTE["purple"], PALETTE["magenta"]])
    img = screen(img, col * np.clip(disc * 1.9, 0, 1.6)[..., None])
    img = screen(img, colorize(np.clip(core, 0, 1) * 1.3, (255, 250, 240)))
    bright = np.clip(img.mean(-1) - 0.48, 0, 1) * 2.0
    img = screen(img, colorize(blur(bright, max(w, h) // 60, 2) * 0.65,
                               PALETTE["purple"]))
    return finish(img, w, h, seed, vig=0.55, lines=0.045)


def m_highway(w, h, rng, seed):
    """Nächtliche Autobahn mit Lichtspuren aus der Langzeitbelichtung."""
    hzn = int(h * 0.42)
    img = sky(w, h, (5, 5, 22), (40, 7, 62))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    sky_mask = np.zeros((h, w), np.float32)
    sky_mask[:max(1, hzn - 6)] = 1.0
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 3600), 1.0) *
                               sky_mask, PALETTE["white"]))
    clouds = fbm(w, h, 4, 4, rng)
    cl = np.clip(clouds - 0.42, 0, 1) * 1.6 * sky_mask
    img = screen(img, colorize(blur(cl, max(w, h) // 45, 2) * 0.5,
                               PALETTE["purple"]))

    sil = np.zeros((h, w), np.float32)
    x = 0
    while x < w:
        bw = int(rng.integers(6, 26))
        bh = int(rng.integers(4, max(5, int(h * 0.07))))
        sil[max(0, hzn - bh):hzn, x:min(w, x + bw)] = 1.0
        x += bw + 1
    img = img * (1 - sil[..., None] * 0.92)
    img = screen(img, colorize(blur(sil, 3, 2) * 0.12, PALETTE["purple"]))
    glow = np.exp(-((ys - hzn) ** 2) / (2 * (h * 0.012) ** 2))
    img = screen(img, colorize(glow * 0.5, PALETTE["magenta"]))

    depth = np.maximum(ys - hzn, 1.0)
    half = depth * 0.95 + 4.0
    road = (np.abs(xs - w * 0.5) < half) & (ys >= hzn)
    asphalt = (0.055 + 0.05 * np.clip(depth / (h - hzn), 0, 1))[..., None] * \
        np.asarray((1.0, 1.0, 1.25), np.float32)
    img = np.where(road[..., None], asphalt, img)

    dash = (np.sin(depth * 0.22) > 0.1).astype(np.float32)
    mid = (np.abs(xs - w * 0.5) < 3.0) & road
    img = screen(img, colorize(mid * dash * 0.8, (255, 235, 170)))

    lanes = [(-0.62, PALETTE["cyan"]), (-0.30, (235, 245, 255)),
             (0.28, PALETTE["red"]), (0.56, PALETTE["magenta"])]
    for frac, col in lanes:
        phase = rng.uniform(0, 6.28)
        wig = rng.uniform(0.010, 0.035)
        pts = []
        for k in range(70):
            d = 1.0 + (h - hzn - 1.0) * (k / 69.0) ** 1.6
            xoff = w * 0.5 + frac * (d * 0.95 + 4.0) + \
                np.sin(d * 0.012 + phase) * d * wig
            pts.append((float(xoff), float(hzn + d)))
        m = line_mask(w, h, pts, width=4.0, core_boost=2.8)
        img = screen(img, colorize(np.clip(m, 0, 1) * 0.95, col))
        img = screen(img, colorize(blur(m, 9, 2) * 0.45, col))

    vp = np.exp(-(((xs - w * 0.5) / (w * 0.07)) ** 2 +
                  ((ys - hzn) / (h * 0.022)) ** 2))
    img = screen(img, colorize(vp * 0.7, (255, 240, 205)))

    lamps = np.zeros((h, w), np.float32)
    for side in (-1.0, 1.0):
        for k in range(28):
            d = 3.0 + (h - hzn) * (k / 27.0) ** 1.7
            lx = w * 0.5 + side * (d * 0.95 + 12.0)
            ly = hzn + d
            dot(lamps, lx, ly, 3.0, 1.0)
    img = screen(img, colorize(np.clip(lamps, 0, 1) * 0.9, PALETTE["yellow"]))
    img = screen(img, colorize(blur(lamps, 7, 2) * 0.5, PALETTE["orange"]))
    return finish(img, w, h, seed, vig=0.6, lines=0.045)


def m_shards(w, h, rng, seed):
    """Glas-Scherben: Voronoi-Facetten mit Neon-Kanten."""
    n = 26
    px = rng.uniform(0.02 * w, 0.98 * w, n)
    py = rng.uniform(0.02 * h, 0.98 * h, n)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d1 = np.full((h, w), 1e9, np.float32)
    d2 = np.full((h, w), 1e9, np.float32)
    owner = np.zeros((h, w), np.int32)
    for i in range(n):
        d = np.sqrt((xs - px[i]) ** 2 + (ys - py[i]) ** 2)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        owner = np.where(closer, i, owner)
        d1 = np.where(closer, d, d1)
    edge = np.exp(-((d2 - d1) / 1.7) ** 2)

    facet = ramp(rng.random(n).astype(np.float32),
                 [(9, 11, 34), (34, 16, 66), (14, 40, 76), (54, 18, 82),
                  (12, 46, 62), (26, 12, 48)])
    shade = (0.55 + 0.70 * (ys / h) + 0.25 * (xs / w))[..., None]
    img = facet[owner] * shade
    ecol = ramp((owner / max(1, n - 1)).astype(np.float32),
                [PALETTE["cyan"], PALETTE["magenta"], PALETTE["purple"],
                 PALETTE["blue"]])
    sheen = np.clip(np.sin((xs - ys) / (w * 0.18)) - 0.75, 0, 1) * 0.45
    img = screen(img, colorize(sheen, (190, 225, 255)))
    img = screen(img, edge[..., None] * ecol * 0.95)
    img = screen(img, colorize(blur(edge, 9, 2) * 0.45, PALETTE["cyan"]))
    return finish(img, w, h, seed, vig=0.55, lines=0.05)


def m_eq(w, h, rng, seed):
    """Audio-Visualizer: Balken, Peak-Hold und Wellenform."""
    img = np.zeros((h, w, 3), np.float32) + \
        np.asarray((6, 6, 20), np.float32) / 255.0
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)

    # Hintergrund-Gitter + Radialglow hinter den Balken
    vline = (np.abs(np.mod(xs, w / 40.0) - 0.5) < 0.06).astype(np.float32) * 0.05
    hline = (np.abs(np.mod(ys, h / 20.0) - 0.5) < 0.06).astype(np.float32) * 0.05
    img = screen(img, colorize(vline + hline, (40, 70, 120)))
    rg = np.exp(-(((xs - w * 0.5) / (w * 0.55)) ** 2 +
                  ((ys - h * 0.55) / (h * 0.55)) ** 2))
    img = screen(img, colorize(rg * 0.22, PALETTE["purple"]))

    nb = 64
    spec = smooth_noise(w, 8, 26, 4, rng)[2]
    xs_bars = np.linspace(0, w - 1, nb).astype(np.int32)
    hs = spec[xs_bars] ** 1.7
    env = 1.15 - 0.60 * (np.arange(nb) / (nb - 1))
    hs = np.clip(hs * env, 0.05, 1.0) * 0.66 + 0.05

    base_y = int(h * 0.84)
    bw = w / nb
    gap = bw * 0.30
    bars = np.zeros((h, w), np.float32)
    caps = np.zeros((h, w), np.float32)
    for i in range(nb):
        x0 = int(i * bw + gap / 2)
        x1 = int((i + 1) * bw - gap / 2)
        hgt = int(hs[i] * (base_y - int(h * 0.08)))
        if hgt < 3 or x1 <= x0:
            continue
        y0 = max(0, base_y - hgt)
        bars[y0:base_y, x0:x1] = 1.0
        caps[max(0, y0 - 5):max(1, y0 - 1), x0:x1] = 1.0

    colbar = ramp(np.linspace(0, 1, max(2, base_y))[:, None],
                  [PALETTE["magenta"], (255, 120, 60), PALETTE["yellow"],
                   PALETTE["cyan"], (150, 255, 255)])
    colbar = colbar[:base_y]
    barlayer = np.zeros((h, w, 3), np.float32)
    barlayer[:base_y] = bars[:base_y, :, None] * colbar * 1.1
    img = screen(img, barlayer)
    img = screen(img, colorize(caps * 0.95, (255, 255, 255)))

    # Reflexion unter den Balken
    refl = bars[base_y - 140:base_y][::-1]
    rh = min(refl.shape[0], h - base_y)
    if rh > 0:
        fade = np.clip(1.0 - np.arange(rh) / (rh * 1.1), 0, 1)[:, None, None]
        rcol = ramp(np.linspace(0, 1, max(2, refl.shape[0]))[:, None],
                    [PALETTE["magenta"], PALETTE["purple"], PALETTE["cyan"]])
        rlayer = np.zeros((h, w, 3), np.float32)
        rlayer[base_y:base_y + rh] = refl[:rh, :, None] * \
            rcol[:rh] * fade * 0.45
        img = screen(img, blur(rlayer, 3, 2))

    # Wellenform über den Balken
    wave_y = h * 0.30 + h * 0.10 * np.sin(xs / w * 14.0 + seed * 0.3) * \
        (0.4 + 0.6 * smooth_noise(w, 4, 9, 3, rng)[1])
    line = np.exp(-((ys - wave_y) ** 2) / (2 * 2.2 ** 2))
    img = screen(img, colorize(line * 0.9, (235, 250, 255)))
    img = screen(img, colorize(blur(line, 7, 2) * 0.4, PALETTE["cyan"]))
    return finish(img, w, h, seed, vig=0.55, lines=0.05)


def m_lightning(w, h, rng, seed):
    """Gewitterblitze über dunklem, bewölktem Himmel."""
    img = sky(w, h, (5, 5, 20), (16, 6, 34))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    clouds = fbm(w, h, 4, 5, rng)
    shade = (0.55 + 0.45 * smoothstep(ys, 0, h * 0.75)) * (0.55 + 0.65 * clouds)
    img = img * shade[..., None]
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 8000), 0.5) *
                               np.clip(1.0 - clouds, 0, 1), PALETTE["white"]))

    def make_bolt(x0, y0, x1, y1, segs, spread):
        pts = [(float(x0), float(y0))]
        for s in range(1, segs + 1):
            t = s / segs
            xx = x0 + (x1 - x0) * t + rng.normal(0, spread) * (1.0 - abs(0.5 - t))
            yy = y0 + (y1 - y0) * t
            pts.append((float(xx), float(yy)))
        return pts

    bolts = []
    for k in range(2):
        bolts.append(make_bolt(w * rng.uniform(0.28, 0.72), -12.0,
                               w * rng.uniform(0.2, 0.8),
                               h * rng.uniform(0.70, 0.92),
                               13, w * (0.070 - 0.018 * k)))
    core_m = np.clip(line_mask(w, h, bolts[0], width=9.0, core_boost=3.6), 0, 1)
    core2 = np.clip(line_mask(w, h, bolts[1], width=6.0, core_boost=2.8), 0, 1)
    branch_m = np.zeros((h, w), np.float32)
    for k, bpts_main in enumerate(bolts):
        for _ in range(7 if k == 0 else 4):
            i0 = int(rng.integers(3, len(bpts_main) - 3))
            bx, by = bpts_main[i0]
            ex = bx + rng.normal(0, w * 0.15)
            ey = by + h * rng.uniform(0.10, 0.30)
            bpts = make_bolt(bx, by, ex, ey, 6, w * 0.030)
            np.maximum(branch_m, np.clip(line_mask(w, h, bpts, width=3.5,
                                                   core_boost=2.2), 0, 1),
                       out=branch_m)

    img = screen(img, colorize(core_m * 1.0, (245, 252, 255)))
    img = screen(img, colorize(core2 * 0.8, (225, 245, 255)))
    img = screen(img, colorize(branch_m * 0.9, PALETTE["cyan"]))
    flash = blur(core_m + core2 * 0.7 + branch_m * 0.8,
                 max(w, h) // 10, 2)
    img = screen(img, colorize(flash * 1.15, PALETTE["purple"]))
    img = screen(img, colorize(blur(flash, max(w, h) // 5, 2) * 0.60,
                               PALETTE["cyan"]))

    ground = np.zeros((h, w), np.float32)
    x = 0
    while x < w:
        bw = int(rng.integers(10, 46))
        bh = int(rng.integers(6, max(7, int(h * 0.14))))
        ground[max(0, int(h * 0.90) - bh):h, x:min(w, x + bw)] = 1.0
        x += bw + 2
    img = img * (1 - ground[..., None] * 0.97)
    img = screen(img, colorize(blur(ground, 5, 2) * 0.10, PALETTE["magenta"]))
    return finish(img, w, h, seed, vig=0.6, lines=0.05)


def m_orbit(w, h, rng, seed):
    """Planet mit Ringen, Mond und Sternenfeld."""
    img = sky(w, h, (3, 4, 16), (12, 5, 34))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    neb = fbm(w, h, 3, 4, rng)
    img = screen(img, colorize(np.clip(neb - 0.5, 0, 1) * 0.8,
                               PALETTE["purple"]))
    img = screen(img, colorize(stars(w, h, rng, int(w * h / 2800), 1.0),
                               PALETTE["white"]))

    cx, cy, R = w * 0.52, h * 0.5, h * 0.25
    dx, dy = xs - cx, ys - cy
    dp = np.sqrt(dx * dx + dy * dy)

    # Ring (hinten)
    e = np.sqrt((dx / (R * 1.95)) ** 2 + (dy / (R * 0.52)) ** 2)
    band = smoothstep(e, 1.0, 1.06) * (1.0 - smoothstep(e, 1.45, 1.55))
    band = band * (0.55 + 0.45 * np.sin(e * 46.0) ** 2)
    ring_col = ramp(np.clip((e - 1.0) / 0.55, 0, 1),
                    [(210, 235, 255), PALETTE["cyan"], PALETTE["purple"],
                     PALETTE["magenta"]])
    back = (ys < cy)
    img = screen(img, (band * back)[..., None] * ring_col * 1.1)

    # Planet
    inside = dp < R
    nx = np.clip(dx / R, -1, 1)
    ny = np.clip(dy / R, -1, 1)
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
    lam = np.clip(nx * -0.55 + ny * -0.55 + nz * 0.63, 0, 1)
    bands = np.sin((ny * 3.6 + fbm(w, h, 5, 4, rng) * 4.0) * np.pi)
    surf = ramp(0.5 + 0.5 * bands,
                [(16, 20, 60), PALETTE["blue"], PALETTE["purple"],
                 (120, 200, 255), PALETTE["magenta"]])
    body = surf * (0.10 + 1.05 * lam[..., None]) * inside[..., None]
    img = np.where(inside[..., None], body, img)
    rim = np.exp(-((dp - R) ** 2) / (2 * (R * 0.045) ** 2)) * (1 - lam * 0.6)
    img = screen(img, colorize(rim * 0.85, PALETTE["cyan"]))

    # Ring (vorne) über dem Planeten
    front = (ys >= cy)
    img = screen(img, (band * front)[..., None] * ring_col * 1.1)

    # Mond
    mx, my, mr = w * 0.24, h * 0.26, h * 0.055
    mdx, mdy = xs - mx, ys - my
    md = np.sqrt(mdx * mdx + mdy * mdy)
    m_in = md < mr
    mnx = np.clip(mdx / mr, -1, 1)
    mny = np.clip(mdy / mr, -1, 1)
    mnz = np.sqrt(np.clip(1 - mnx * mnx - mny * mny, 0, 1))
    mlam = np.clip(mnx * -0.5 + mny * -0.6 + mnz * 0.6, 0, 1)
    moon = ramp(mlam, [(20, 22, 48), (110, 130, 190), (235, 240, 255)])
    img = np.where(m_in[..., None], moon * 0.9, img)
    return finish(img, w, h, seed, vig=0.55, lines=0.045)


# ---------------------------------------------------- Pixel-Stil ------
# Eigene Pipeline: Low-Res-Canvas zeichnen -> auf Retro-Paletten
# quantisieren (Bayer-Dithering) -> nearest-neighbor hochskalieren.
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0 - 0.5

PALS = {
    # Game Boy (4 Grautöne der Originalpalette)
    "gb": [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)],
    # CGA Modus 4, Palette 1 (hoch)
    "cga": [(6, 6, 26), (0, 170, 170), (170, 0, 170), (255, 85, 170),
            (255, 255, 255)],
    # Arcade-Automat: 8 feste Farben
    "arcade": [(6, 6, 18), (36, 40, 140), (0, 200, 255), (255, 255, 255),
               (240, 60, 70), (255, 210, 60), (70, 230, 110), (255, 80, 200)],
    # Sunset / Outrun
    "sunset": [(16, 6, 34), (72, 18, 96), (190, 40, 130), (255, 90, 90),
               (255, 170, 60), (255, 235, 150), (255, 255, 255)],
    # Platformer (Himmel, Erde, Münzen)
    "plat": [(10, 10, 26), (92, 168, 248), (255, 255, 255), (168, 112, 56),
             (64, 160, 64), (255, 210, 60), (240, 70, 70), (120, 60, 160)],
    # Weltraum
    "space": [(4, 4, 14), (24, 26, 70), (60, 90, 200), (0, 230, 255),
              (255, 255, 255), (255, 220, 80), (255, 70, 170), (140, 255, 160)],
}

# Sprites: "#" = Pixel an, "." = aus
INVADER = [
    "..#.....#..",
    "...#...#...",
    "..#######..",
    ".##.###.##.",
    "###########",
    "#.#######.#",
    "#.#.....#.#",
    "...##.##...",
]
SHIP = [
    "....#....",
    "...###...",
    "..#####..",
    ".#######.",
    "#########",
    ".#.###.#.",
    "#..###..#",
]
# Seitanschauendes Raumschiff (Side-Scroller, zeigt nach rechts)
RSHIP = [
    "#........",
    "###......",
    "#####....",
    "#######..",
    "#########",
    "#######..",
    "#####....",
    "###......",
    "#........",
]
GHOST = [
    "..####..",
    ".######.",
    "#.####.#",
    "#.####.#",
    "########",
    "########",
    "#.##.##.",
    "#.#..#.#",
]
HERO = [
    "..####..",
    "..####..",
    "...##...",
    ".######.",
    ".######.",
    "..####..",
    "..#..#..",
    "..#..#..",
]
BOSS = [
    "......########......",
    "....############....",
    "..################..",
    ".##################.",
    "###..########..#####",
    "####################",
    "####################",
    ".####.######.####...",
    "..##...####...##....",
    "..#.....##.....#....",
]
CAR = [
    "...###...",
    "..#####..",
    ".#######.",
    "###.#.###",
    "###.#.###",
    ".#######.",
    "..#####..",
    "...###...",
]
LANDER = [
    ".....#.....",
    "....###....",
    "...#####...",
    "..#######..",
    ".#.#####.#.",
    ".#.#...#.#.",
    "#...#.#...#",
    "..##...##..",
]


def px_canvas(w, h, lw=160):
    """Low-Res-Zeichenfläche mit dem Seitenverhältnis des Zielbildes."""
    lw = int(lw)
    lh = max(8, int(round(lw * h / w)))
    return np.zeros((lh, lw, 3), np.float32), lw, lh


def px_grad(c, top, bot):
    """Vertikaler Verlauf als Grundfläche (wird gedithert)."""
    ch = c.shape[0]
    t = np.linspace(0.0, 1.0, ch, dtype=np.float32)[:, None, None]
    a = np.asarray(top, np.float32) / 255.0
    b = np.asarray(bot, np.float32) / 255.0
    c[:] = a * (1 - t) + b * t


def px_rect(c, x, y, ww, hh, col):
    """Ausgefülltes Rechteck (Pixelkoordinaten, wird geclippt)."""
    ch, cw, _ = c.shape
    x0, y0 = int(max(0, x)), int(max(0, y))
    x1, y1 = int(min(cw, x + ww)), int(min(ch, y + hh))
    if x1 > x0 and y1 > y0:
        c[y0:y1, x0:x1] = np.asarray(col, np.float32) / 255.0


def px_hollow(c, x, y, ww, hh, col, t=1):
    """Rand eines Rechtecks (Rahmenstärke t)."""
    px_rect(c, x, y, ww, t, col)
    px_rect(c, x, y + hh - t, ww, t, col)
    px_rect(c, x, y, t, hh, col)
    px_rect(c, x + ww - t, y, t, hh, col)


def px_circ(c, cx, cy, r, col, hollow=False, t=1):
    """Kreis als gefüllte Fläche oder 1px-Ring."""
    ch, cw, _ = c.shape
    x0, x1 = int(max(0, cx - r - 1)), int(min(cw, cx + r + 2))
    y0, y1 = int(max(0, cy - r - 1)), int(min(ch, cy + r + 2))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.sqrt((xx - cx + 0.5) ** 2 + (yy - cy + 0.5) ** 2)
    if hollow:
        m = (d <= r + 0.5) & (d > r - t)
    else:
        m = d <= r + 0.5
    sub = c[y0:y1, x0:x1]
    sub[m] = np.asarray(col, np.float32) / 255.0


def px_line(c, x0, y0, x1, y1, col):
    """Einfache Linie (für Laser, Masten, Gitter)."""
    ch, cw, _ = c.shape
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    xs = np.round(np.linspace(x0, x1, n)).astype(np.int32)
    ys = np.round(np.linspace(y0, y1, n)).astype(np.int32)
    ok = (xs >= 0) & (xs < cw) & (ys >= 0) & (ys < ch)
    c[ys[ok], xs[ok]] = np.asarray(col, np.float32) / 255.0


def px_sprite(c, rows, x, y, col, sc=1):
    """Sprite aus einer '#'/'.'-Maske setzen."""
    col_a = np.asarray(col, np.float32) / 255.0
    for ry, row in enumerate(rows):
        for rx, ch_ in enumerate(row):
            if ch_ == "#":
                px_rect(c, x + rx * sc, y + ry * sc, sc, sc, col_a * 255.0)


def px_out(c, w, h, pal_name, dither=0.6):
    """Auf Palette quantisieren (Bayer) und verlustfrei hochskalieren."""
    ch, cw, _ = c.shape
    bay = BAYER4[np.arange(ch)[:, None] % 4, np.arange(cw)[None, :] % 4]
    v = c + bay[..., None] * dither
    p = np.asarray(PALS[pal_name], np.float32) / 255.0
    d = ((v[..., None, :] - p[None, None]) ** 2).sum(-1)
    q = p[d.argmin(-1)]
    sx = -(-w // cw)
    sy = -(-h // ch)
    up = np.repeat(np.repeat(q, sy, 0), sx, 1)
    return (np.clip(up[:h, :w], 0, 1) * 255.0 + 0.5).astype(np.uint8)


def px_space(w, h, rng, seed):
    """Pixel-Art: Side-Scroller im Weltraum."""
    c, lw, lh = px_canvas(w, h)
    px_grad(c, (24, 26, 70), (4, 4, 14))
    for _ in range(lw * lh // 32):
        col = (255, 255, 255) if rng.random() < 0.7 else (0, 230, 255)
        px_rect(c, int(rng.integers(0, lw)), int(rng.integers(0, lh)),
                1, 1, col)
    pcx, pcy, pr = lw * 0.84, lh * 0.55, lh * 0.30
    px_circ(c, pcx + 3, pcy + 3, pr, (24, 26, 70))
    px_circ(c, pcx, pcy, pr, (60, 90, 200))
    px_circ(c, pcx, pcy, pr, (0, 230, 255), hollow=True)
    for ax, ay, ar in ((61, 15, 5), (80, 38, 6), (96, 65, 4)):   # Asteroiden
        px_circ(c, ax, ay, ar, (60, 90, 200))
        px_circ(c, ax - 1, ay - 1, max(1, ar // 3), (4, 4, 14))
        px_circ(c, ax, ay, ar, (0, 230, 255), hollow=True)
    sx, sy = int(lw * 0.10), int(lh * 0.46)
    px_sprite(c, RSHIP, sx, sy, (255, 255, 255))
    px_rect(c, sx + 4, sy + 3, 2, 2, (0, 230, 255))     # Cockpit
    px_rect(c, sx - 4, sy + 4, 3, 1, (255, 170, 60))    # Triebwerk
    px_rect(c, sx - 2, sy + 4, 2, 1, (255, 220, 80))
    for i in range(3):                                  # Schüsse
        px_rect(c, sx + 14 + i * 16, sy + 4, 6, 1, (255, 220, 80))
    px_rect(c, 0, lh - 8, lw, 8, (4, 4, 14))            # HUD
    for i in range(3):
        px_rect(c, 4 + i * 6, lh - 6, 4, 4, (140, 255, 160))
    for i in range(10):
        px_rect(c, lw - 6 - (10 - i) * 6, lh - 6, 4, 4,
                (255, 70, 170) if i < 7 else (24, 26, 70))
    return px_out(c, w, h, "space")


def px_invader(w, h, rng, seed):
    """Pixel-Art: Invader-Formation à la Arcade-Automat."""
    c, lw, lh = px_canvas(w, h)
    px_rect(c, 0, 0, lw, lh, (6, 6, 26))
    for _ in range(lw * lh // 80):
        px_rect(c, int(rng.integers(0, lw)), int(rng.integers(0, lh)),
                1, 1, (170, 0, 170))
    rows = [(255, 85, 170), (170, 0, 170), (0, 170, 170)]
    for r in range(3):
        for k in range(5):
            px_sprite(c, INVADER, 14 + k * 28, 18 + r * 16, rows[r])
    px_sprite(c, SHIP, lw // 2 - 4, lh - 22, (255, 255, 255))
    px_line(c, lw // 2, lh - 24, lw // 2, int(lh * 0.58), (255, 255, 255))
    px_rect(c, 0, lh - 10, lw, 1, (0, 170, 170))
    for i in range(3):                                  # Leben
        px_rect(c, 5 + i * 9, 5, 7, 5, (0, 170, 170))
    for i in range(8):                                  # Punkte
        px_rect(c, lw - 7 - i * 7, 5, 6, 5,
                (255, 85, 170) if i < 5 else (6, 6, 26))
    return px_out(c, w, h, "cga", dither=0.35)


def px_sunset(w, h, rng, seed):
    """Pixel-Art: Outrun-Landschaft mit gestreifter Sonne."""
    c, lw, lh = px_canvas(w, h)
    px_grad(c, (72, 18, 96), (16, 6, 34))
    horizon = int(lh * 0.55)
    cx, cy, r = lw * 0.5, horizon - lh * 0.12, lh * 0.26
    for y in range(int(cy - r), int(min(cy + r, horizon))):
        dy = y - cy
        if abs(dy) > r:
            continue
        if dy > r * 0.10 and int(dy) % 5 < 2:           # Streifen
            continue
        halfw = int(np.sqrt(max(0.0, r * r - dy * dy)))
        px_rect(c, int(cx - halfw), y, 2 * halfw, 1,
                (255, 170, 60) if dy < 0 else (255, 90, 90))
    prof = smooth_noise(w, 8, 7, 3, rng)[4]
    prof = (prof - prof.min()) / (np.ptp(prof) + 1e-6)
    for x in range(lw):
        px_ = min(w - 1, int(x * w / lw))
        y = int(horizon - 6 - prof[px_] * lh * 0.20)
        px_rect(c, x, y, 1, horizon - y, (16, 6, 34))
        px_rect(c, x, y, 1, 1, (190, 40, 130))
    px_rect(c, 0, horizon, lw, lh - horizon, (16, 6, 34))
    span = max(1, lh - horizon)
    for y in range(horizon + 3, lh, 5):                 # Gitter VOR der Straße
        px_rect(c, 0, y, lw, 1, (190, 40, 130))
    for y in range(horizon, lh):                        # Straße mit Rändern
        t = (y - horizon) / span
        halfw = 3 + int(t * lw * 0.46)
        px_rect(c, int(lw * 0.5 - halfw), y, 2 * halfw, 1, (72, 18, 96))
        px_rect(c, int(lw * 0.5 - halfw), y, 2, 1, (255, 255, 255))
        px_rect(c, int(lw * 0.5 + halfw - 1), y, 2, 1, (255, 255, 255))
    k = 0
    for y in range(horizon + 4, lh, 5):                 # Mittelstriche
        k += 1
        if k % 2:
            continue
        t = (y - horizon) / span
        wdt = 1 + int(t * 4)
        px_rect(c, int(lw * 0.5 - wdt // 2), y, wdt + 1, 4, (255, 235, 150))
    return px_out(c, w, h, "sunset", dither=0.45)


def px_maze(w, h, rng, seed):
    """Pixel-Art: Mazeduelle mit Pellets und Geistern."""
    c, lw, lh = px_canvas(w, h)
    bg, wall = (6, 6, 18), (36, 40, 140)
    px_rect(c, 0, 0, lw, lh, bg)
    blocks = [(2, 2, lw - 4, 3), (2, lh - 5, lw - 4, 3),
              (2, 2, 3, lh - 4), (lw - 5, 2, 3, lh - 4),
              (int(lw * 0.15), int(lh * 0.22), 32, 10),
              (int(lw * 0.61), int(lh * 0.22), 32, 10),
              (int(lw * 0.15), int(lh * 0.64), 32, 10),
              (int(lw * 0.61), int(lh * 0.64), 32, 10),
              (int(lw * 0.43), int(lh * 0.43), int(lw * 0.14), 11)]
    for b in blocks:
        px_hollow(c, b[0], b[1], b[2], b[3], wall, t=3)
    halo = [(b[0] - 2, b[1] - 2, b[2] + 4, b[3] + 4) for b in blocks]

    def free(x, y):
        return not any(x0 <= x < x0 + ww and y0 <= y < y0 + hh
                       for x0, y0, ww, hh in halo)

    for y in range(9, lh - 9, 6):
        for x in range(9, lw - 9, 6):
            if free(x, y):
                px_rect(c, x, y, 1, 1, (255, 255, 255))
    for gx, gy in ((9, 9), (lw - 10, 9), (9, lh - 10), (lw - 10, lh - 10)):
        px_circ(c, gx, gy, 2, (255, 210, 60))
    cx, cy, r = int(lw * 0.30), int(lh * 0.87), 5        # Spielfigur
    px_circ(c, cx, cy, r, (255, 210, 60))
    for x in range(cx, cx + r + 1):
        half = int((x - cx) * 1.15) + 1
        px_rect(c, x, cy - half, 1, half, bg)
        px_rect(c, x, cy + 1, 1, half, bg)
    cols = [(240, 60, 70), (255, 80, 200), (0, 200, 255), (255, 210, 60)]
    for i, col in enumerate(cols):
        gx, gy = int(lw * 0.36) + i * 12, int(lh * 0.34)
        px_sprite(c, GHOST, gx, gy, col)
        px_rect(c, gx + 1, gy + 2, 2, 2, (255, 255, 255))
        px_rect(c, gx + 5, gy + 2, 2, 2, (255, 255, 255))
        px_rect(c, gx + 2, gy + 3, 1, 1, (36, 40, 140))
        px_rect(c, gx + 6, gy + 3, 1, 1, (36, 40, 140))
    return px_out(c, w, h, "arcade", dither=0.3)


def px_snake(w, h, rng, seed):
    """Pixel-Art: Snake-Board mit Apfel und HUD."""
    c, lw, lh = px_canvas(w, h)
    bg, grid, green, head, red = (6, 6, 18), (36, 40, 140), (70, 230, 110), \
        (255, 255, 255), (240, 60, 70)
    px_rect(c, 0, 0, lw, lh, bg)
    px_rect(c, 0, 0, lw, 13, grid)                      # HUD-Leiste
    px_hollow(c, 4, 16, lw - 8, lh - 21, grid, t=2)
    cell = 7
    for y in range(20, lh - 8, cell):
        for x in range(8, lw - 8, cell):
            px_rect(c, x, y, 1, 1, grid)
    segs = []
    sx, sy = 8 + cell, 20 + cell * 2
    for i in range(9):
        segs.append((sx + i * cell, sy))
    for i in range(5):
        segs.append((sx + 8 * cell, sy + (i + 1) * cell))
    for i in range(6):
        segs.append((sx + (8 - i) * cell, sy + 6 * cell))
    for qx, qy in segs[:-1]:
        px_rect(c, qx - 2, qy - 2, 5, 5, green)
    hx, hy = segs[-1]
    px_rect(c, hx - 3, hy - 3, 6, 6, head)              # Kopf
    px_rect(c, hx + 1, hy - 4, 2, 2, green)             # Zunge
    ax, ay = int(lw * 0.76), int(lh * 0.34)
    px_circ(c, ax, ay, 3, red)
    px_rect(c, ax, ay - 4, 1, 2, green)                 # Stiel
    px_rect(c, ax + 1, ay - 2, 1, 1, (255, 255, 255))   # Glanz
    px_rect(c, 5, 4, 5, 5, green)                       # HUD-Icon
    for i in range(10):
        px_rect(c, lw - 8 - i * 7, 4, 6, 5,
                (255, 210, 60) if i < 6 else (6, 6, 18))
    return px_out(c, w, h, "arcade", dither=0.3)


def px_platform(w, h, rng, seed):
    """Pixel-Art: Jump-’n’-Run-Szenerie."""
    c, lw, lh = px_canvas(w, h)
    px_grad(c, (92, 168, 248), (150, 210, 255))
    for _ in range(4):                                  # Wolken
        x0 = int(rng.integers(6, max(7, lw - 32)))
        y0 = int(rng.integers(6, max(7, int(lh * 0.38))))
        px_rect(c, x0, y0, 26, 6, (255, 255, 255))
        px_rect(c, x0 + 5, y0 - 4, 16, 5, (255, 255, 255))
        px_rect(c, x0 + 10, y0 - 7, 7, 4, (255, 255, 255))
    gy = lh - 15
    px_rect(c, 0, gy, lw, 15, (168, 112, 56))           # Boden
    for y in range(gy, lh, 3):
        px_rect(c, 0, y, lw, 1, (10, 10, 26))
    for y in range(gy, lh, 6):                          # Backsteine
        for x in range(((y // 6) % 2) * 8, lw, 16):
            px_rect(c, x, y, 1, 3, (10, 10, 26))
    plats = [(int(lw * 0.14), int(lh * 0.60), 34),
             (int(lw * 0.50), int(lh * 0.44), 42),
             (int(lw * 0.74), int(lh * 0.68), 30)]
    for px_, py_, pw in plats:                          # Inseln
        px_rect(c, px_, py_, pw, 5, (168, 112, 56))
        px_rect(c, px_, py_ + 4, pw, 2, (10, 10, 26))
        px_circ(c, px_ + pw // 2, py_ - 9, 3, (255, 210, 60))
        px_rect(c, px_ + pw // 2 - 1, py_ - 11, 1, 5, (255, 210, 60))
    px_sprite(c, HERO, int(lw * 0.28), gy - 8, (240, 70, 70))
    px_rect(c, int(lw * 0.28) + 4, gy - 7, 2, 2, (255, 255, 255))
    px_rect(c, lw - 26, gy - 6, 18, 6, (64, 160, 64))   # Busch
    px_line(c, lw - 42, gy, lw - 42, gy - 26, (255, 255, 255))
    px_rect(c, lw - 41, gy - 26, 14, 9, (70, 230, 110))     # Fahne
    return px_out(c, w, h, "plat", dither=0.45)


def px_boss(w, h, rng, seed):
    """Pixel-Art: Bosskampf mit Lebensbalken und Explosionen."""
    c, lw, lh = px_canvas(w, h)
    px_grad(c, (4, 4, 14), (24, 26, 70))
    for _ in range(lw * lh // 18):
        px_rect(c, int(rng.integers(0, lw)), int(rng.integers(0, lh)),
                1, 1, (255, 255, 255) if rng.random() < 0.8 else (0, 230, 255))
    bx, by = int(lw / 2 - 10), int(lh * 0.16)
    px_sprite(c, BOSS, bx, by, (255, 70, 170))
    px_rect(c, bx + 6, by + 4, 3, 2, (255, 255, 255))   # Augen
    px_rect(c, bx + 13, by + 4, 3, 2, (255, 255, 255))
    px_rect(c, bx + 7, by + 5, 1, 1, (4, 4, 14))
    px_rect(c, bx + 14, by + 5, 1, 1, (4, 4, 14))
    bw = int(lw * 0.6)                                   # Lebensbalken
    px_hollow(c, int(lw * 0.2), 4, bw, 8, (255, 255, 255), t=1)
    px_rect(c, int(lw * 0.2) + 2, 6, int(bw * 0.68) - 4, 4, (70, 230, 110))
    px_rect(c, int(lw * 0.2) + int(bw * 0.68) - 2, 6, bw - int(bw * 0.68), 4,
            (240, 60, 70))
    sx = lw // 2 - 4                                      # Spieler + Laser
    px_sprite(c, SHIP, sx, lh - 20, (0, 230, 255))
    px_line(c, sx + 4, lh - 21, bx + 6, by + 13, (0, 230, 255))
    px_line(c, sx + 4, lh - 21, bx + 14, by + 13, (0, 230, 255))
    for ex, ey, er in ((bx - 7, by + 9, 5), (bx + 27, by + 5, 4),
                       (bx + 10, by + 17, 6)):           # Explosionen
        px_circ(c, ex, ey, er, (255, 170, 60))
        px_circ(c, ex, ey, max(1, er - 2), (255, 220, 80))
        px_circ(c, ex, ey, max(1, er - 4), (255, 255, 255))
    px_rect(c, 0, lh - 9, lw, 9, (4, 4, 14))             # HUD
    for i in range(3):
        px_rect(c, 5 + i * 8, lh - 7, 6, 5, (140, 255, 160))
    for i in range(9):
        px_rect(c, lw - 7 - i * 7, lh - 7, 6, 5,
                (255, 220, 80) if i < 6 else (24, 26, 70))
    return px_out(c, w, h, "space")


def px_racer(w, h, rng, seed):
    """Pixel-Art: Rennstrecke in Pseudo-3D-Perspektive."""
    c, lw, lh = px_canvas(w, h)
    px_grad(c, (16, 6, 34), (190, 40, 130))
    horizon = int(lh * 0.45)
    px_circ(c, lw * 0.5, horizon - 11, 15, (255, 170, 60))
    prof = smooth_noise(w, 8, 8, 3, rng)[3]
    prof = (prof - prof.min()) / (np.ptp(prof) + 1e-6)
    for x in range(lw):
        yy = int(horizon - 4 - prof[min(w - 1, int(x * w / lw))] * lh * 0.10)
        px_rect(c, x, yy, 1, horizon - yy, (16, 6, 34))
    curve = lw * 0.12
    span = max(1, lh - horizon)
    for y in range(horizon, lh):
        t = (y - horizon) / span
        center = lw * 0.5 + curve * (1 - t) ** 2
        halfw = 3 + int(t * lw * 0.46)
        px_rect(c, int(center - halfw), y, 2 * halfw, 1, (16, 6, 34))
        px_rect(c, int(center - halfw), y, 2, 1, (255, 255, 255))
        px_rect(c, int(center + halfw - 2), y, 2, 1, (255, 255, 255))
    k = 0
    for y in range(horizon + 2, lh, 4):
        k += 1
        if k % 2:
            continue
        t = (y - horizon) / span
        center = lw * 0.5 + curve * (1 - t) ** 2
        wdt = 1 + int(t * 4)
        px_rect(c, int(center - wdt // 2), y, wdt + 1, 3, (255, 235, 150))
    t_r = 0.20                                            # Gegnerwagen
    px_sprite(c, CAR, int(lw * 0.52 + curve * (1 - t_r) ** 2 - 4),
              int(horizon + span * t_r), (255, 90, 90))
    px_sprite(c, CAR, int(lw * 0.5 - 9), lh - 28, (255, 235, 150), sc=2)
    px_rect(c, 0, lh - 9, lw, 9, (16, 6, 34))            # HUD
    for i in range(14):
        px_rect(c, 5 + i * 5, lh - 7, 4, 4,
                (255, 170, 60) if i < 9 else (72, 18, 96))
    return px_out(c, w, h, "sunset", dither=0.45)


def px_gbland(w, h, rng, seed):
    """Pixel-Art: Game-Boy-Landschaft in den 4 Original-Tönen."""
    c, lw, lh = px_canvas(w, h)
    dark, mid, light, lightest = PALS["gb"]
    px_grad(c, lightest, light)
    horizon = int(lh * 0.60)
    sx_, sy_ = lw * 0.72, lh * 0.24
    px_circ(c, sx_, sy_, 13, mid)                        # Sonne mit Rand
    px_circ(c, sx_, sy_, 12, lightest)
    for k in range(3):                                   # Vögel
        bx = int(lw * (0.14 + 0.11 * k))
        by = int(lh * (0.16 + 0.07 * (k % 2)))
        px_rect(c, bx, by, 3, 1, dark)
        px_rect(c, bx - 1, by - 1, 2, 1, dark)
        px_rect(c, bx + 3, by - 1, 2, 1, dark)
        px_rect(c, bx + 4, by, 2, 1, dark)
    prof_f = smooth_noise(w, 10, 6, 4, rng)[7]
    prof_f = (prof_f - prof_f.min()) / (np.ptp(prof_f) + 1e-6)
    prof_n = smooth_noise(w, 10, 10, 4, rng)[7]
    prof_n = (prof_n - prof_n.min()) / (np.ptp(prof_n) + 1e-6)
    for x in range(lw):                                  # Berge (hinten)
        px_ = min(w - 1, int(x * w / lw))
        y = int(horizon - prof_f[px_] * lh * 0.28)
        px_rect(c, x, y, 1, horizon - y, light)
        px_rect(c, x, y, 1, 1, lightest)
    for x in range(lw):                                  # Hügel (vorn)
        px_ = min(w - 1, int(x * w / lw))
        y = int(horizon - prof_n[px_] * lh * 0.13)
        px_rect(c, x, y, 1, horizon - y, mid)
        px_rect(c, x, y, 1, 1, lightest)
    px_rect(c, 0, horizon, lw, lh - horizon, dark)       # See
    for y in range(horizon + 2, lh, 4):                  # Reflexe
        px_rect(c, int(lw * 0.55), y, int(lw * 0.30), 1, mid)
        px_rect(c, int(lw * 0.05), y + 2, int(lw * 0.22), 1, mid)
    for k in range(4):                                   # Bäume
        tx = int(lw * (0.08 + 0.24 * k))
        ty = horizon - int(lh * (0.05 + 0.03 * (k % 2)))
        px_rect(c, tx, ty - 10, 3, 10, dark)
        px_rect(c, tx - 3, ty - 14, 9, 5, dark)
        px_rect(c, tx - 1, ty - 17, 5, 4, dark)
    return px_out(c, w, h, "gb", dither=0.85)


def px_moon(w, h, rng, seed):
    """Pixel-Art: Mondlandung mit Landegerät und Fahne."""
    c, lw, lh = px_canvas(w, h)
    px_grad(c, (4, 4, 14), (24, 26, 70))
    for _ in range(lw * lh // 16):
        col = (255, 255, 255) if rng.random() < 0.75 else (0, 230, 255)
        px_rect(c, int(rng.integers(0, lw)), int(rng.integers(0, lh)),
                1, 1, col)
    ex, ey, er = lw * 0.17, lh * 0.22, 13                # Erde
    px_circ(c, ex + 3, ey + 3, er, (4, 4, 14))
    px_circ(c, ex, ey, er, (60, 90, 200))
    px_circ(c, ex, ey, er, (0, 230, 255), hollow=True)
    gh = int(lh * 0.74)
    prof = smooth_noise(w, 8, 6, 4, rng)[5]
    prof = (prof - prof.min()) / (np.ptp(prof) + 1e-6)
    for x in range(lw):                                  # Mondhügel
        px_ = min(w - 1, int(x * w / lw))
        y = int(gh - prof[px_] * lh * 0.07)
        px_rect(c, x, y, 1, lh - y, (24, 26, 70))
        px_rect(c, x, y, 1, 1, (60, 90, 200))
    for _ in range(7):                                   # Krater
        pxk = int(rng.integers(4, lw - 4))
        pyk = int(rng.integers(gh + 5, lh - 4))
        rk = int(rng.integers(2, 5))
        px_circ(c, pxk, pyk, rk, (4, 4, 14))
        px_circ(c, pxk, pyk, rk, (60, 90, 200), hollow=True)
    lx = int(lw * 0.55)                                  # Landegerät
    px_sprite(c, LANDER, lx, gh - 8, (255, 255, 255))
    px_rect(c, lx + 4, gh, 3, 3, (255, 220, 80))
    px_rect(c, lx + 5, gh + 2, 1, 2, (255, 70, 170))
    fx = int(lw * 0.30)                                  # Fahne
    px_line(c, fx, gh + 1, fx, gh - 17, (255, 255, 255))
    px_rect(c, fx + 1, gh - 17, 11, 7, (255, 70, 170))
    px_rect(c, fx + 2, gh - 16, 3, 2, (255, 255, 255))
    return px_out(c, w, h, "space")


BUILDERS = {"grid": m_grid, "nebula": m_nebula, "burst": m_burst,
            "tunnel": m_tunnel, "city": m_city, "ridges": m_ridges,
            "aurora": m_aurora, "eclipse": m_eclipse, "plasma": m_plasma,
            "topo": m_topo, "circuit": m_circuit, "rain": m_rain,
            "fireworks": m_fireworks, "galaxy": m_galaxy,
            "highway": m_highway, "shards": m_shards, "eq": m_eq,
            "lightning": m_lightning, "orbit": m_orbit,
            "px_space": px_space, "px_invader": px_invader,
            "px_sunset": px_sunset, "px_maze": px_maze, "px_snake": px_snake,
            "px_platform": px_platform, "px_boss": px_boss,
            "px_racer": px_racer, "px_gbland": px_gbland, "px_moon": px_moon}


# -------------------------------------------------------------- API -----
def render(motif, w=1920, h=1080, seed=42):
    """Ein Motiv rendern -> uint8 (h, w, 3)."""
    if motif not in BUILDERS:
        raise ValueError(f"Unbekanntes Motiv: {motif!r} (nutze {MOTIFS})")
    rng = np.random.default_rng(seed)
    return BUILDERS[motif](w, h, rng, seed)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Prozeduraler Neon-Art-Generator für NEON VANGUARD.")
    p.add_argument("motif", nargs="?", default="all",
                   help=f"Motiv oder 'all' ({', '.join(MOTIFS)})")
    p.add_argument("--size", default="1920x1080",
                   help="Auflösung WxH (Standard 1920x1080)")
    p.add_argument("--seed", type=int, default=42, help="Zufalls-Seed")
    p.add_argument("--out", default="art",
                   help="Datei oder Ordner (Standard: art/)")
    p.add_argument("--list", action="store_true", help="Motive auflisten")
    a = p.parse_args(argv)

    if a.list:
        print("Motive:", ", ".join(MOTIFS))
        return 0

    try:
        w, h = (int(v) for v in a.size.lower().split("x"))
    except ValueError:
        p.error("--size muss WxH sein, z.B. 1920x1080")

    motifs = MOTIFS if a.motif == "all" else (a.motif,)
    file_mode = a.out.lower().endswith(".png")

    for i, m in enumerate(motifs):
        if file_mode:
            out = a.out if len(motifs) == 1 else \
                os.path.splitext(a.out)[0] + f"_{m}.png"
        else:
            out = os.path.join(a.out, f"{m}.png")
        img = render(m, w, h, a.seed)
        save_png(out, img)
        print(f"{m:8s} -> {out}  ({w}x{h}, seed {a.seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
