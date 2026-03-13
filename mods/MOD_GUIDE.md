# Only4BMS Mod Development Guide

This guide explains how to create a mod for **Only4BMS**.
Mods live in the `mods/` folder at the project root and are loaded automatically at startup.

---

## Quick Start

1. Create a folder inside `mods/` — the folder name becomes your mod's default ID.
2. Create `__init__.py` inside that folder with the required fields.
3. Launch Only4BMS — your mod's button will appear in the main menu.

```
mods/
└── my_mod/
    └── __init__.py      ← everything lives here (or import sub-modules as needed)
```

---

## Required Interface (`__init__.py`)

```python
MOD_ID          = "my_mod"                      # unique, no spaces
MOD_NAME        = "My Mod"                      # shown in the main menu
MOD_DESCRIPTION = "A short one-line description."
MOD_VERSION     = "1.0.0"                       # semver recommended

def run(settings, renderer, window, **ctx):
    """Called when the player clicks your mod's menu button."""
    ...
```

> Only `run` is mandatory. The four metadata constants are optional but recommended.

---

## Parameters

### `settings` — `dict`

The player's current settings. Read-only recommended; do not persist changes without consent.

| Key | Type | Description |
|---|---|---|
| `fps` | int | Target frame rate |
| `speed` | float | Note scroll speed (0.1 – 5.0) |
| `volume` | float | Master volume (0.0 – 1.0) |
| `keys` | list[int] | pygame key codes for lanes D F J K |
| `joystick_keys` | list[str] | Joystick bindings |
| `fullscreen` | int | 1 = fullscreen |
| `language` | str/int | Current language |
| `hit_window_mult` | float | Judgment window multiplier |
| `judge_delay` | float | Extra input delay in ms |
| `note_type` | int | 0 = bar, 1 = circle |

### `renderer` — `pygame._sdl2.video.Renderer`

The shared SDL2 renderer.
Draw your scene to a `pygame.Surface`, convert it to a `Texture`, and blit it each frame:

```python
from pygame._sdl2.video import Texture

surf = pygame.Surface((w, h))
# ... draw to surf ...
tex = Texture.from_surface(renderer, surf)
renderer.clear()
renderer.blit(tex, pygame.Rect(0, 0, w, h))
renderer.present()
```

### `window` — `pygame._sdl2.video.Window`

The SDL2 window. Read `window.size` to get the current resolution.
You can call `window.set_fullscreen(True/False)` if your mod needs to switch modes.

### `**ctx` — optional host context

The host may inject the following keyword arguments:

| Key | Type | Description |
|---|---|---|
| `init_mixer_fn` | `callable(settings)` | Re-initialise the audio mixer with current settings |
| `challenge_manager` | `ChallengeManager` | Pass to `RhythmGame` to track achievements |

Always use `.get()` so your mod works even if a key is absent:

```python
init_mixer_fn = ctx.get("init_mixer_fn")
challenge_manager = ctx.get("challenge_manager")
```

---

## Using Only4BMS APIs

Your mod runs inside the same Python process as the game, so all internal modules are importable:

```python
# Parse a BMS file
from only4bms.core.bms_parser import BMSParser
parser = BMSParser("/path/to/song.bms")
notes, bgms, bgas, bmp_map, visual_timing_map, measures = parser.parse()

# Launch the core rhythm game engine
from only4bms.game.rhythm_game import RhythmGame
game = RhythmGame(
    notes, bgms, bgas, parser.wav_map, bmp_map,
    parser.title, settings,
    visual_timing_map=visual_timing_map,
    measures=measures,
    mode='single',           # 'single' | 'ai_multi' | 'online_multi'
    renderer=renderer,
    window=window,
    ai_difficulty='normal',  # 'normal' | 'hard'
    note_mod='None',         # 'None' | 'MIRROR' | 'RANDOM'
    challenge_manager=challenge_manager,
)
result = game.run()          # returns dict with 'action', 'score', etc.

# Internationalisation
from only4bms.i18n import get as _t
label = _t("menu_single")    # returns localised string

# Paths
from only4bms import paths
print(paths.SONG_DIR)        # BMS files directory
print(paths.MODS_DIR)        # this mods/ folder
```

---

## Rendering Your Own UI

You have full control over the screen. The recommended pattern:

```python
import pygame
from pygame._sdl2.video import Texture

def run(settings, renderer, window, **ctx):
    w, h = window.size
    clock = pygame.time.Clock()
    screen = pygame.Surface((w, h), pygame.SRCALPHA)
    texture = None

    pygame.key.set_repeat(300, 50)
    pygame.event.clear()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # --- draw your scene ---
        screen.fill((10, 10, 20))
        # ... pygame.draw calls, font renders, etc. ...

        # --- upload to GPU and present ---
        if texture is None:
            texture = Texture.from_surface(renderer, screen)
        else:
            texture.update(screen)

        renderer.clear()
        renderer.blit(texture, pygame.Rect(0, 0, w, h))
        renderer.present()
        clock.tick(settings.get("fps", 60))

    pygame.key.set_repeat(0)
```

---

## Sub-modules

For larger mods, split your code into multiple files:

```
mods/
└── my_mod/
    ├── __init__.py      ← entry point (MOD_* constants + run())
    ├── ui.py            ← custom menu / HUD
    ├── game_logic.py    ← mod-specific gameplay
    └── assets/          ← images, sounds, etc.
```

Import them with a relative import:

```python
# inside __init__.py
from .ui import MyModMenu
from .game_logic import MyModGame
```

Or an absolute import using the module name `mods.my_mod`:

```python
from mods.my_mod.ui import MyModMenu
```

---

## Example — Minimal Custom Scene

```python
# mods/hello_world/__init__.py
import pygame
from pygame._sdl2.video import Texture

MOD_ID          = "hello_world"
MOD_NAME        = "Hello World"
MOD_DESCRIPTION = "Displays a greeting and returns to the menu."
MOD_VERSION     = "0.1.0"


def run(settings, renderer, window, **ctx):
    w, h = window.size
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, int(h * 0.08))
    screen = pygame.Surface((w, h))
    texture = None

    pygame.event.clear()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                running = False

        screen.fill((10, 5, 30))
        msg = font.render("Hello from my mod!  (press any key)", True, (0, 255, 200))
        screen.blit(msg, msg.get_rect(center=(w // 2, h // 2)))

        if texture is None:
            texture = Texture.from_surface(renderer, screen)
        else:
            texture.update(screen)

        renderer.clear()
        renderer.blit(texture, pygame.Rect(0, 0, w, h))
        renderer.present()
        clock.tick(settings.get("fps", 60))
```

---

## Packaging & Distribution

A mod is just a folder — zip it and share:

```
my_mod.zip
└── my_mod/
    ├── __init__.py
    └── ...
```

Users extract it into the `mods/` directory next to the Only4BMS executable (or project root in development).

---

## Built-in Mods (Reference Implementations)

| Folder | Description |
|---|---|
| `course_mode/` | Roguelike HP training mode — uses `CourseMenu` + `CourseSession` |
| `online_multiplay/` | Socket.IO 1v1 multiplayer — uses `MultiplayerMenu` + `RhythmGame` |

Reading their `__init__.py` is the best way to see how to wire Only4BMS internals into a mod.
