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

MOTIFS = ("grid", "nebula", "burst", "tunnel")


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


def value_noise(w, h, cells, rng):
    """Glattes Zufallsraster, bilinear interpoliert."""
    cy = max(2, int(cells * h / max(w, h)))
    cx = max(2, int(cells * w / max(w, h)))
    grid = rng.random((cy + 1, cx + 1)).astype(np.float32)
    ys = np.linspace(0, cy, h, dtype=np.float32)
    xs = np.linspace(0, cx, w, dtype=np.float32)
    y0 = np.clip(np.floor(ys).astype(np.int32), 0, cy - 1)
    x0 = np.clip(np.floor(xs).astype(np.int32), 0, cx - 1)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3.0 - 2.0 * fy)
    fx = fx * fx * (3.0 - 2.0 * fx)
    g00 = grid[np.ix_(y0, x0)]
    g10 = grid[np.ix_(y0 + 1, x0)]
    g01 = grid[np.ix_(y0, x0 + 1)]
    g11 = grid[np.ix_(y0 + 1, x0 + 1)]
    top = g00 * (1 - fx) + g01 * fx
    bot = g10 * (1 - fx) + g11 * fx
    return top * (1 - fy) + bot * fy


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


BUILDERS = {"grid": m_grid, "nebula": m_nebula, "burst": m_burst,
            "tunnel": m_tunnel}


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
