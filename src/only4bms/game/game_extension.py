"""
GameExtension — Mod hook interface for RhythmGame
===================================================
Mods that need in-game integration (HUD overlays, network sync, custom fail
conditions, etc.) subclass :class:`GameExtension` and pass an instance to
``RhythmGame(extension=...)``.

All methods have default no-op implementations so subclasses only override
what they need.

Public attributes available via ``self._game`` after :meth:`attach`:
  _game.renderer, _game.window         — SDL2 renderer / window
  _game.width, _game.height            — window size in pixels
  _game.judgments                      — dict of current judgment counts
  _game.combo, _game.max_combo         — combo tracking
  _game.mode                           — 'single' | 'ai_multi' | 'online_multi'
  _game.state                          — 'PLAYING' | 'PAUSED' | 'RESULT'
  _game.ai_judgments, _game.ai_engine  — opponent data (ai_multi / online_multi)
"""


class GameExtension:
    """Base class for mod extensions attached to a RhythmGame session."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, game) -> None:
        """Called once at the end of ``RhythmGame.__init__``.
        Store a reference to the game so callbacks can read game state.
        """
        self._game = game

    # ------------------------------------------------------------------
    # Per-note hooks
    # ------------------------------------------------------------------

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        """Called after each note judgment.

        Parameters
        ----------
        key   : 'PERFECT' | 'GREAT' | 'GOOD' | 'MISS'
        lane  : 0-based lane index, or -1 for LN-release judgments
        t_ms  : song-relative time in milliseconds
        """

    # ------------------------------------------------------------------
    # Per-frame hooks
    # ------------------------------------------------------------------

    def on_tick(self, sim_time_ms: float) -> None:
        """Called once per render frame while state == 'PLAYING'.
        Use this for network polling, time-based effects, etc.
        """

    def should_abort(self) -> bool:
        """Return True to immediately end the current song (transitions to
        RESULT).  Use this to implement fail-on-HP-zero, etc.
        """
        return False

    # ------------------------------------------------------------------
    # Rendering hooks (called around the base game render)
    # ------------------------------------------------------------------

    def draw_background(self, renderer, window) -> None:
        """Draw behind the BGA / notes.
        Called after ``renderer.clear()`` but before ``draw_bga()``.
        Use this for animated backgrounds when no BGA is present.
        """

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        """Draw on top of the game frame, before ``renderer.present()``.

        Parameters
        ----------
        renderer   : pygame._sdl2.video.Renderer
        window     : pygame._sdl2.video.Window
        game_state : ``_get_draw_state('p1', t)`` dict while playing,
                     or ``get_stats()`` dict during result phase
        phase      : 'playing' | 'paused' | 'result'
        """

    # ------------------------------------------------------------------
    # Stats contribution
    # ------------------------------------------------------------------

    def get_extra_stats(self) -> dict:
        """Extra key/value pairs merged into ``RhythmGame.get_stats()``
        before the dict is returned to callers (e.g. challenge checks).

        Common keys:  'failed' (bool), 'hp' (float), 'must_win' (bool)
        """
        return {}
