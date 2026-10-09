"""Prozedurale Audio-Engine: alle Sounds und die Musik werden mit numpy synthetisiert.

Externe Imports: pygame, numpy, math.
"""
import math

import numpy as np
import pygame

SR = 44100


# ----------------------------------------------------------------- Helfer
def _to_sound(mono, vol=1.0):
    mono = np.clip(mono, -1.0, 1.0)
    data = (mono * 32000.0 * vol).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([data, data])))


def _to_stereo(left, right, vol=1.0):
    l = (np.clip(left, -1, 1) * 32000.0 * vol).astype(np.int16)
    r = (np.clip(right, -1, 1) * 32000.0 * vol).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([l, r])))


def _noise(n, seed, kernel=40):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    if kernel > 1:
        x = np.convolve(x, np.ones(kernel) / kernel, mode="same")
    return x


# ----------------------------------------------------------------- Sounds
def _s_laser():
    n = int(SR * 0.17)
    t = np.arange(n) / SR
    f = 1500 * np.exp(-t * 24) + 170
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sin(ph) + 0.40 * np.sin(2 * ph) + 0.18 * np.sin(3 * ph)
    env = np.exp(-t * 26) * (1 - np.exp(-t * 900))
    return _to_sound(w * env * 0.5)


def _s_laser_heavy():
    n = int(SR * 0.3)
    t = np.arange(n) / SR
    f = 700 * np.exp(-t * 12) + 90
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)
    env = np.exp(-t * 14) * (1 - np.exp(-t * 500))
    return _to_sound(w * env * 0.6)


def _s_boom(dur=0.75, decay=5.0, seed=3, punch=1.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = _noise(n, seed, 70)
    f = 220 * np.exp(-t * 11) + 34
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph)
    env = np.exp(-t * decay)
    return _to_sound((noise * 1.5 + body * 1.1) * env * 0.62 * punch)


def _s_hit():
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    noise = _noise(n, 11, 8)
    env = np.exp(-t * 70)
    return _to_sound(noise * env * 1.1)


def _s_tick():
    n = int(SR * 0.05)
    t = np.arange(n) / SR
    w = np.sin(2 * np.pi * 1800 * t) + 0.5 * np.sin(2 * np.pi * 900 * t)
    return _to_sound(w * np.exp(-t * 90) * 0.5)


def _s_shoot_enemy():
    n = int(SR * 0.13)
    t = np.arange(n) / SR
    f = 620 * np.exp(-t * 26) + 120
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = 2 * ((ph / (2 * np.pi)) % 1) - 1
    return _to_sound(w * np.exp(-t * 34) * 0.35)


def _s_pickup():
    notes = [523.25, 659.25, 783.99, 1046.50]
    total = int(SR * 0.45)
    buf = np.zeros(total)
    step = int(SR * 0.055)
    for i, f in enumerate(notes):
        n = int(SR * 0.16)
        t = np.arange(n) / SR
        w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
        seg = w * np.exp(-t * 17) * 0.5
        s = i * step
        buf[s:s + n] += seg
    return _to_sound(buf)


def _s_hurt():
    n = int(SR * 0.4)
    t = np.arange(n) / SR
    f = 340 * np.exp(-t * 8) + 70
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = 2 * ((ph / (2 * np.pi)) % 1) - 1
    noise = _noise(n, 5, 30) * 0.5
    return _to_sound((w * 0.7 + noise) * np.exp(-t * 8) * 0.7)


def _s_ui(up=True):
    n = int(SR * 0.1)
    t = np.arange(n) / SR
    f0, f1 = (700, 1200) if up else (1100, 600)
    f = np.linspace(f0, f1, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return _to_sound(np.sin(ph) * np.exp(-t * 40) * 0.5)


def _s_alarm():
    n = int(SR * 1.1)
    t = np.arange(n) / SR
    f = 220 + 110 * np.sin(2 * np.pi * 3.2 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = 2 * ((ph / (2 * np.pi)) % 1) - 1
    env = np.minimum(1, t * 30) * np.minimum(1, (n / SR - t) * 8)
    return _to_sound(w * env * 0.4)


def _s_powerup_full():
    notes = [523.25, 659.25, 783.99, 1046.50, 1318.5]
    total = int(SR * 0.7)
    buf = np.zeros(total)
    step = int(SR * 0.08)
    for i, f in enumerate(notes):
        n = int(SR * 0.3)
        t = np.arange(n) / SR
        w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t)
        s = i * step
        buf[s:s + n] += w * np.exp(-t * 11) * 0.45
    return _to_sound(buf)


# ----------------------------------------------------------------- Musik
def _music_loop(bpm=126, bars=8):
    beat = 60.0 / bpm
    n = int(bars * 4 * beat * SR)
    left = np.zeros(n)
    right = np.zeros(n)

    def add(buf, start, dur, freq, kind, vol, decay):
        s = int(start * SR)
        m = int(dur * SR)
        if s >= len(buf) or m <= 0:
            return
        m = min(m, len(buf) - s)
        t = np.arange(m) / SR
        if kind == "saw":
            w = 2 * ((t * freq) % 1.0) - 1
        elif kind == "sq":
            w = np.sign(np.sin(2 * np.pi * freq * t))
        elif kind == "tri":
            w = 2 * np.abs(2 * ((t * freq) % 1.0) - 1) - 1
        else:
            w = np.sin(2 * np.pi * freq * t)
        env = np.exp(-t * decay) * np.minimum(1.0, t * 700)
        buf[s:s + m] += w * env * vol

    # Am - F - C - G
    roots = [110.00, 87.31, 130.81, 98.00]
    chords = [
        [220.00, 261.63, 329.63],
        [174.61, 220.00, 261.63],
        [261.63, 329.63, 392.00],
        [196.00, 246.94, 293.66],
    ]

    for bar in range(bars):
        b0 = bar * 4 * beat
        ci = bar % 4
        root = roots[ci]
        chord = chords[ci]

        # Kick (4 on the floor) + Snare + Hats
        for k in range(4):
            tk = b0 + k * beat
            # Kick
            nk = int(SR * 0.2)
            tkk = np.arange(nk) / SR
            fk = 130 * np.exp(-tkk * 26) + 44
            pk = 2 * np.pi * np.cumsum(fk) / SR
            kick = np.sin(pk) * np.exp(-tkk * 15)
            s = int(tk * SR)
            m = min(nk, n - s)
            if m > 0:
                left[s:s + m] += kick[:m] * 0.95
                right[s:s + m] += kick[:m] * 0.95
            # Snare auf 2 und 4
            if k in (1, 3):
                ns = int(SR * 0.16)
                sn = _noise(ns, 40 + bar, 6) * np.exp(-np.arange(ns) / SR * 28)
                add(left, tk, 0.16, 0, "sin", 0, 1)  # Platzhalter (kein Effekt)
                s = int(tk * SR)
                m = min(ns, n - s)
                if m > 0:
                    left[s:s + m] += sn[:m] * 0.5
                    right[s:s + m] += sn[:m] * 0.5
            # Hi-Hat auf Achtel
            for h in range(2):
                th = tk + h * beat * 0.5
                nh = int(SR * 0.05)
                hn = np.diff(np.concatenate([[0.0], _noise(nh, 90 + bar + h, 3)]))
                hn *= np.exp(-np.arange(nh) / SR * 90)
                s = int(th * SR)
                m = min(nh, n - s)
                if m > 0:
                    vol = 0.3 if h else 0.42
                    left[s:s + m] += hn[:m] * vol * 0.9
                    right[s:s + m] += hn[:m] * vol * 1.1

        # Bass: Achtel
        for e in range(8):
            te = b0 + e * beat * 0.5
            f = root if e % 4 != 3 else root * 1.5
            add(left, te, 0.24, f, "saw", 0.30, 13)
            add(right, te, 0.24, f, "saw", 0.30, 13)

        # Arpeggio: 16tel, links/rechts leicht versetzt (Breite)
        order = [0, 1, 2, 1, 2, 0, 1, 2, 2, 1, 0, 1, 0, 2, 1, 2]
        for i in range(16):
            te = b0 + i * beat * 0.25
            f = chord[order[i]] * (2.0 if i % 8 >= 4 else 1.0)
            add(left, te, 0.2, f, "tri", 0.15, 22)
            add(right, te + 0.012, 0.2, f * 1.005, "tri", 0.15, 22)

        # Pad: gehaltener Akkordton
        for f in chord:
            add(left, b0, 4 * beat, f / 2, "sin", 0.045, 0.6)
            add(right, b0, 4 * beat, f / 2, "sin", 0.045, 0.6)

    mix = np.tanh(np.stack([left, right]) * 1.15) * 0.86
    return _to_stereo(mix[0], mix[1])


# ----------------------------------------------------------------- Engine
class Audio:
    """Baut alle Sounds, verwaltet Kanäle und Mute-Status."""

    def __init__(self):
        self.ok = False
        self.muted = False
        self.sfx = {}
        self.music_snd = None
        self.music_ch = None
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(SR, -16, 2, 512)
            pygame.mixer.set_num_channels(28)
            self.sfx = {
                "laser": _s_laser(),
                "heavy": _s_laser_heavy(),
                "boom": _s_boom(0.7, 5.0, 3),
                "bigboom": _s_boom(1.4, 3.0, 8, 1.3),
                "hit": _s_hit(),
                "tick": _s_tick(),
                "eshoot": _s_shoot_enemy(),
                "pickup": _s_pickup(),
                "full": _s_powerup_full(),
                "hurt": _s_hurt(),
                "ui": _s_ui(True),
                "uidown": _s_ui(False),
                "alarm": _s_alarm(),
            }
            self.music_snd = _music_loop()
            self.music_ch = pygame.mixer.Channel(0)
            self.ok = True
        except Exception as exc:  # kein Audio -> Spiel läuft stumm weiter
            print("[audio] deaktiviert:", exc)

    def play(self, name, vol=1.0):
        if not self.ok or self.muted:
            return
        snd = self.sfx.get(name)
        if snd is None:
            return
        snd.set_volume(max(0.0, min(1.0, vol)))
        snd.play()

    def music(self, on=True):
        if not self.ok or self.music_ch is None:
            return
        if on and not self.muted:
            if not self.music_ch.get_busy():
                self.music_ch.play(self.music_snd, loops=-1, fade_ms=400)
        elif not on:
            self.music_ch.fadeout(300)

    def toggle_mute(self):
        self.muted = not self.muted
        if not self.ok:
            return self.muted
        pygame.mixer.pause() if self.muted else pygame.mixer.unpause()
        if not self.muted and self.music_ch is not None and self.music_ch.get_busy():
            self.music_ch.play(self.music_snd, loops=-1)
        return self.muted
