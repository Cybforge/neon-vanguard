# NEON VANGUARD

Ein Neon-Arcade-Shooter im Stil der 80er – komplett aus dem Programm code
erzeugt: **kein einziges Bild, kein einziger Sound, keine Musikdatei**.

## Start

```bash
python main.py
```

Benötigt: `pygame-ce` (oder `pygame`) und `numpy`.

## Steuerung

| Taste | Funktion |
|---|---|
| WASD / Pfeiltasten | Bewegen |
| Maus | Zielen |
| Linke Maustaste / Leertaste | Feuern (halten für Dauerfeuer) |
| P / ESC | Pause |
| M | Ton an/aus |
| R | Neustart |
| Enter / Klick | Starten (im Menü bzw. nach Game Over) |

## Die 5 Imports (und warum genau diese)

| Import | Aufgabe |
|---|---|
| `pygame` | Fenster, Rendering, Eingabe, Mixer |
| `numpy` | Synthese aller Sounds + Musik, Bloom-Postprozess, Hintergrund |
| `math` | Winkel, Vektoren, Bewegungsmuster |
| `random` | Wellen-Zusammensetzung, Spawnorte, Partikel |
| `sys` | sauberes Beenden (`sys.exit`) |

Alles andere sind eigene Module (`settings`, `audio`, `gfx`, `entities`,
`game`) – Dateien statt Imports.

## Aufbau

```
main.py      Einstieg
game.py      States (Menü/Play/Pause/Over), Waves, Kollisionen, HUD
entities.py  Spieler, Kugeln, 5 Gegnertypen, Boss, Powerups
gfx.py       Glow-Sprites, Bloom, Sternenhimmel, Partikel, Floating Text
audio.py     prozedurale Sound-Engine + prozedurale Loop-Musik (numpy)
settings.py  Konstanten und Farbpalette
neon_art.py  prozeduraler Art-/Wallpaper-Generator (PNG, ohne Display)
```

## Technik

- **Sound:** Jeder Sound wird zur Laufzeit aus Sinus/Noise/Envelope-Berechnungen
  gebaut (`numpy` → `pygame.sndarray`). Die Musik ist eine 8-taktige Schleife
  (Kick/Snare/Hats/Bass/Arp/Pad, Am–F–C–G, 126 BPM), ebenfalls synthetisiert
  und läuft endlos auf einem eigenen Kanal.
- **Bloom:** Die Szene wird auf 1/4 verkleinert, Helliges isoliert
  (Schwelle 118) und additiv zurückgeblendet → satter Neon-Look für ~2 ms.
- **Juice:** Screen-Shake (Trauma), Hit-Stop, Schadensblitz, Partikel,
  Score-Popups, Combo-Multiplikator (bis x4), Magnet-Powerups.
- **Gegner:** Chaser, Dart, Shooter, Orb, Tank – plus Boss „Void Sentinel"
  mit 3 Phasen (gezielter Salvo → Ring-Burst → Spirale).
- **Performance:** ~6 ms pro Frame bei 1280×720 (Update + Render + Bloom),
  deutlich über 60 fps.

## Art-Generator

`neon_art.py` erzeugt Wallpaper und Key-Art im Look des Spiels – wie die
Sounds und die Spielgrafik selbst komplett aus Zahlen berechnet, ohne eine
einzige Bilddatei als Vorlage. Läuft ohne Display (nur `numpy`) und schreibt
PNGs. **39 Motive** (19 Neon- + 10 Pixel- + 5 Frutiger-Aero- + 5
Plasma-Motive), alle per Seed reproduzierbar.

```bash
python neon_art.py --list
python neon_art.py grid --size 1920x1080 --seed 7 --out art/grid.png
python neon_art.py all --size 1280x720 --out art
```

Vier Motive, jedes mit eigenem Seed reproduzierbar:

| `grid` – Synthwave-Horizont | `nebula` – Sternennebel |
|---|---|
| ![grid](art/grid.png) | ![nebula](art/nebula.png) |

| `burst` – Explosion | `tunnel` – Vortex |
|---|---|
| ![burst](art/burst.png) | ![tunnel](art/tunnel.png) |

### Die 15 weiteren Motive

| `city` – Skyline mit Wasser-Spiegelung | `ridges` – Bergketten mit Nebel |
|---|---|
| ![city](art/city.png) | ![ridges](art/ridges.png) |

| `aurora` – Polarlicht | `eclipse` – Sonnenfinsternis |
|---|---|
| ![aurora](art/aurora.png) | ![eclipse](art/eclipse.png) |

| `plasma` – Interferenz-Muster | `topo` – Höhenlinien-Topografie |
|---|---|
| ![plasma](art/plasma.png) | ![topo](art/topo.png) |

| `circuit` – Leiterplatte | `rain` – Neon-Regen |
|---|---|
| ![circuit](art/circuit.png) | ![rain](art/rain.png) |

| `fireworks` – Feuerwerk | `galaxy` – Spiralgalaxie |
|---|---|
| ![fireworks](art/fireworks.png) | ![galaxy](art/galaxy.png) |

| `highway` – Autobahn-Lichtspuren | `shards` – Glas-Facetten |
|---|---|
| ![highway](art/highway.png) | ![shards](art/shards.png) |

| `eq` – Audio-Visualizer | `lightning` – Gewitterblitze |
|---|---|
| ![eq](art/eq.png) | ![lightning](art/lightning.png) |

| `orbit` – Planet mit Ringen |
|---|
| ![orbit](art/orbit.png) |

### Die 10 Pixel-Motive (Retro-Stil)

Ein komplett anderer Look: Statt weicher Verläufe und Glows zeichnen diese
Motive auf einer Low-Res-Fläche (160×90 Pixel), quantisieren jede Farbe auf
eine klassische Retro-Palette (Game Boy, CGA, Arcade, Outrun …) und
skalieren verlustfrei nearest-neighbour hoch. Dazu Bayer-Dithering –
also echtes Pixel-Art-Handwerk, nur komplett aus Zahlen:

| `px_space` – Side-Scroller im All | `px_invader` – Invader-Formation |
|---|---|
| ![px_space](art/px_space.png) | ![px_invader](art/px_invader.png) |

| `px_sunset` – Outrun-Straße | `px_maze` – Mazeduelle |
|---|---|
| ![px_sunset](art/px_sunset.png) | ![px_maze](art/px_maze.png) |

| `px_snake` – Snake-Board | `px_platform` – Jump-’n’-Run |
|---|---|
| ![px_snake](art/px_snake.png) | ![px_platform](art/px_platform.png) |

| `px_boss` – Bosskampf | `px_racer` – Rennstrecke |
|---|---|
| ![px_boss](art/px_boss.png) | ![px_racer](art/px_racer.png) |

| `px_gbland` – Game-Boy-Landschaft | `px_moon` – Mondlandung |
|---|---|
| ![px_gbland](art/px_gbland.png) | ![px_moon](art/px_moon.png) |

Alle 19 Neon-Motive auf einen Blick (jeweils Seed 42, 640×360):

![Übersicht aller Motive](art/_sheet.png)

Alle 10 Pixel-Motive auf einen Blick:

![Übersicht der Pixel-Motive](art/_px_sheet.png)

### Die 5 Frutiger-Aero- und 5 Plasma-Motive

Zwei weitere Stilfamilien. **Frutiger Aero** (2006–2009): hell, hochglänzend,
grün-blau – Wassertropfen mit echter Lichtbrechung, Irisierendes an
Seifenblasen, Glas-Panels mit unscharfem Hintergrund, glänzende 3D-Kugeln
mit Fresnel-Rim und Lens-Flare mit Blenden-Geistern. **Plasma**: dunkler
Grund, heiße Ader- und Entladungsmuster – von der Glaskugel mit 22
kletternden Entladungen bis zum Spiralwirbel mit glühendem Auge.

| `aero_sky` – Blauer Himmel mit Wolkentürmen | `aero_hills` – Grüne Hügel mit See |
|---|---|
| ![aero_sky](art/aero_sky.png) | ![aero_hills](art/aero_hills.png) |

| `aero_drops` – Wassertropfen im Makro | `aero_glass` – Glas-Panels & Blasen |
|---|---|
| ![aero_drops](art/aero_drops.png) | ![aero_glass](art/aero_glass.png) |

| `aero_orbs` – Glänzende Kugeln mit Reflexion |
|---|
| ![aero_orbs](art/aero_orbs.png) |

| `plasma_ball` – Plasmakugel mit Entladungen | `plasma_filament` – Energie-Adern |
|---|---|
| ![plasma_ball](art/plasma_ball.png) | ![plasma_filament](art/plasma_filament.png) |

| `plasma_ribbons` – Fließende Energie-Bänder | `plasma_core` – Pulsierender Energiekern |
|---|---|
| ![plasma_ribbons](art/plasma_ribbons.png) | ![plasma_core](art/plasma_core.png) |

| `plasma_swirl` – Spiralwirbel |
|---|
| ![plasma_swirl](art/plasma_swirl.png) |

Alle 10 Aero-/Plasma-Motive auf einen Blick:

![Übersicht der Aero- und Plasma-Motive](art/_ap_sheet.png)

## Dateien

Der Highscore wird in `neon_vanguard_highscore.txt` gespeichert.
