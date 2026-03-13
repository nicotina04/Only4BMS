"""
Course Mode Mod for Only4BMS
=============================
Roguelike rhythm training mode.

Players clear 30-second stages with an HP bar that changes based on judgments.
Difficulty tiers: BEGINNER → INTERMEDIATE → ADVANCED → ORDEAL.
Each run procedurally generates different charts and modifier combinations.

All code is self-contained in this mod package:
  course_menu.py      — difficulty selection screen
  course_session.py   — stage loop, HP system, intermission screens
  course_generator.py — procedural BMS chart generation

Host APIs used (from only4bms):
  only4bms.core.bms_parser.BMSParser
  only4bms.game.rhythm_game.RhythmGame
  only4bms.i18n
  only4bms.paths
"""

MOD_ID = "course_mode"
MOD_NAME = "Course Mode"
MOD_DESCRIPTION = "Roguelike training — clear stages to survive. HP drops on misses."
MOD_VERSION = "1.0.0"


def run(settings, renderer, window, **ctx):
    """
    Entry point called by main.py when the player selects 'Course Mode'.

    Parameters
    ----------
    settings : dict
        Shared settings dict (speed, volume, keys, etc.).
    renderer : pygame._sdl2.video.Renderer
        The SDL2 renderer shared across all scenes.
    window : pygame._sdl2.video.Window
        The SDL2 window.
    **ctx : dict
        Optional context injected by the host:
          - init_mixer_fn  : callable(settings) — reinitialise pygame mixer
          - challenge_manager : ChallengeManager instance
    """
    from .course_menu import CourseMenu
    from .course_session import CourseSession
    from only4bms import paths

    init_mixer_fn = ctx.get("init_mixer_fn")
    challenge_manager = ctx.get("challenge_manager")

    course_res = CourseMenu(settings, renderer=renderer, window=window).run()
    if not course_res or course_res[0] != "START":
        return

    difficulty, duration_ms = course_res[1], course_res[2]

    if init_mixer_fn:
        init_mixer_fn(settings)

    CourseSession(
        settings, renderer, window,
        difficulty, duration_ms, paths,
        init_mixer_fn=init_mixer_fn,
        challenge_manager=challenge_manager,
    ).run()
