"""
Mod Loader for Only4BMS
=======================
Discovers and loads mods from the 'mods/' directory (MODS_DIR in paths.py).

Each mod is a Python package (subfolder with __init__.py) that exports:
  - MOD_ID          : str   — unique identifier, no spaces (e.g. "course_mode")
  - MOD_NAME        : str   — display name shown in the main menu
  - MOD_DESCRIPTION : str   — short description (shown as tooltip or subtitle)
  - MOD_VERSION     : str   — semver string (e.g. "1.0.0")
  - run(settings, renderer, window, **ctx) -> None
                            — entry point called when the player selects the mod

See mods/MOD_GUIDE.md for the full developer guide.
"""

import os
import sys
import importlib.util
from dataclasses import dataclass
from typing import Callable


@dataclass
class ModInfo:
    """Metadata and entry point for a single loaded mod."""
    id: str                # Unique identifier (folder name fallback)
    name: str              # Display name in the main menu (static fallback)
    description: str       # Short description
    version: str           # Version string
    action: str            # Action key returned by MainMenu (e.g. "MOD_course_mode")
    run_fn: Callable       # run(settings, renderer, window, **ctx) -> None
    name_fn: Callable = None   # Optional: callable() -> str for localised display name
    setup_fn: Callable = None  # Optional: setup(ctx) called once after host context is ready


def discover_mods() -> list:
    """
    Scan MODS_DIR for valid mod packages and return a list of ModInfo.

    Loading order is alphabetical by folder name. Mods that fail to load
    are skipped with a warning printed to stdout.
    """
    from only4bms.paths import MODS_DIR

    mods: list[ModInfo] = []

    if not os.path.isdir(MODS_DIR):
        return mods

    # Make the mods/ parent importable so relative imports inside mods work
    mods_parent = os.path.dirname(MODS_DIR)
    if mods_parent not in sys.path:
        sys.path.insert(0, mods_parent)

    for entry in sorted(os.listdir(MODS_DIR)):
        mod_path = os.path.join(MODS_DIR, entry)
        init_path = os.path.join(mod_path, "__init__.py")

        # Only process directories that have an __init__.py
        if not os.path.isdir(mod_path) or not os.path.isfile(init_path):
            continue

        module_name = f"mods.{entry}"
        try:
            spec = importlib.util.spec_from_file_location(
                module_name,
                init_path,
                submodule_search_locations=[mod_path],
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            run_fn = getattr(module, "run", None)
            if run_fn is None or not callable(run_fn):
                print(f"[ModLoader] Skipping '{entry}': no callable 'run' found.")
                continue

            mod_id = getattr(module, "MOD_ID", entry)
            mod_name = getattr(module, "MOD_NAME", entry)
            mod_desc = getattr(module, "MOD_DESCRIPTION", "")
            mod_ver = getattr(module, "MOD_VERSION", "1.0.0")
            name_fn = getattr(module, "get_display_name", None)
            setup_fn = getattr(module, "setup", None)

            mods.append(ModInfo(
                id=mod_id,
                name=mod_name,
                description=mod_desc,
                version=mod_ver,
                action=f"MOD_{mod_id}",
                run_fn=run_fn,
                name_fn=name_fn,
                setup_fn=setup_fn if callable(setup_fn) else None,
            ))
            print(f"[ModLoader] Loaded: '{mod_name}' v{mod_ver}  ({entry})")

        except Exception as exc:
            print(f"[ModLoader] Failed to load '{entry}': {exc}")

    return mods


def initialize_mods(mods: list, ctx: dict) -> None:
    """
    Call each mod's setup(ctx) if it defines one.
    Runs once after the shared context (challenge_manager, etc.) is ready.
    """
    for mod in mods:
        if mod.setup_fn is None:
            continue
        try:
            mod.setup_fn(ctx)
            print(f"[ModLoader] setup() ok: '{mod.id}'")
        except Exception as exc:
            print(f"[ModLoader] setup() failed for '{mod.id}': {exc}")
