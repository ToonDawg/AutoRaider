# Coordinate strategy for V2 migrations
#
# Decision (2026-08-01): prefer cropped templates; fall back to CLICK_POINT
# only when an element has no stable visual anchor.
#
# Why not make every coordinate a CLICK_POINT?
#   v1's absolute desktop coords (e.g. Clan Boss (1200, 650)) break under any
#   window move or resolution change. Adding window-relative CLICK_POINT also
#   forces giving the app's shared ClickHandler a region_provider — a change
#   on the path all eight v1 commands use, which the epic guardrails forbid
#   until a live full-screen vs window-scoped proof demands it.
#
# Preferred path
#   1. Capture the screen that contains the element.
#   2. Crop a template into assets/ (or assets/dynamic/ via `python -m hitl`).
#   3. Reference it with CLICK_IMAGE / IMAGE_PRESENT.
#
# CLICK_POINT is allowed when
#   - The element has no distinctive crop (empty difficulty dropdown row,
#     Doom Tower boss node on the map, Gem Mine hotspot with no icon crop).
#   - A note on the node records that a crop is still wanted.
#
# Applied in this migration
#   - Clan Boss difficulties → CBhard.png / CBnightmare.png / Brutal.png
#     (Ultra-Nightmare skipped until a crop exists).
#   - Inbox collect → CLICK_IMAGE with offset [250, 0] on the item template.
#   - Faction Wars banner → CLICK_IMAGE with offset [50, 50].
#   - Doom Tower difficulty dropdown + boss nodes → CLICK_POINT (no crop yet).
#   - Gem Mine → CLICK_POINT (800, 560) until a gemMine.png crop lands.
#   - Daily Quests artifact upgrade (random box click) → dropped from v2;
#     no declarative equivalent for "click random until upgradeable".
