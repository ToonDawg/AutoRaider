"""Thin wrapper kept for the Arena runbook / muscle memory.

Delegates to ``capture_screenshots.py`` with the Arena map. Prefer calling
that script directly for new tasks::

    python helper_scripts/capture_screenshots.py daily_ten_classic_arena --task arena
"""

from __future__ import annotations

import sys

from capture_screenshots import main

if __name__ == "__main__":
    # Preserve `python helper_scripts/capture_arena_screenshots.py` by injecting
    # the Arena defaults when no args were given.
    if len(sys.argv) == 1:
        sys.argv.extend(
            ["daily_ten_classic_arena", "--task", "arena", "--map", "arena"]
        )
    main()
