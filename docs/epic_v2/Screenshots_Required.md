# Screenshots Required

**For:** whoever has access to the game machine.
**Why:** the developer implementing [AutoRaider v2](./Epic_AutoRaider_v2.md) cannot run the game. Without these captures, PR 1.4 cannot be fully verified. Phase 3 no longer needs capture 11 to start — it generates its fixture from capture 05 — but capture 11 remains the realism check on the finished HITL tool.

## Delivery status (2026-08-01)

| # | File | Status | Notes |
|---|---|---|---|
| 01 | `01_bastion.png` | Delivered (900×600) | `battleBTN.png` matches |
| 02 | `02_bastion_ad.png` | **Outstanding** | Needed to verify `exitAdd.png`; opportunistic |
| 03 | `03_battle_menu.png` | Delivered (900×600) | `arenaTab.png` matches |
| 04 | `04_arena_mode_selection.png` | Delivered (900×600) | `classicArena.png` matches |
| 05 | `05_arena_opponent_list.png` | Delivered (900×600) | `arenaBattle.png` matches |
| 06 | `06_pre_battle_team.png` | Delivered (900×600) | `arenaStart.png` matches |
| 07 | `07_loading_screen.png` | Delivered (900×600) | `loadingScreen.png` does **not** match this frame — crop may be stale or capture mistimed |
| 08 | `08_mid_battle.png` | Delivered (900×600) | `inBattle.png` does **not** match; `tapToContinue.png` *does* match (capture may be late-battle/results) |
| 09 | `09_battle_results.png` | Delivered (900×600) | `tapToContinue.png` matches |
| 10 | `10_out_of_tokens.png` | **Outstanding** | Completes PR 1.4 gem-refill guard coverage — high priority |
| 11 | (any lost screen) | **Outstanding** | No longer blocks Phase 3 — it is a realism check on the finished tool. Easiest route is now a crash dump — see below |

Phase 1 offline work shipped against 01 and 03–09. `tests/test_assets_match.py` skips `exitAdd.png` and `ArenaRefillGems.png` by name until 02 and 10 arrive. Replay of 01→09 reaches `COMPLETED`.

The repository previously had **zero** full-screen game captures. `assets/` still holds ~170 small template crops — enough to feed the matcher. The eight delivered window crops are what let us test it.

## How to capture

**Capture the game window only, not the whole desktop.** Every capture should be exactly **900×600**.

1. **Let the bot size the window first.** Launch AutoRaider once so `AutoRaider.configure_game_window` sets the window to 900×600 at position (500, 200). Do not resize or move it afterwards.
2. **Use the window rect exactly as `pygetwindow` reports it** (`left`, `top`, `width`, `height`) — see the snippet below. This matters: the engine derives its search region from the same call, so capturing any other way (a hand-drawn crop, a client-area-only grab) produces a haystack that differs from the live one by a few pixels of window frame, and the tests stop meaning anything.
3. **PNG, lossless, unscaled.** No JPEG, no "optimised" export, no resizing after the fact.
4. **Check the dimensions before sending.** If a file is not exactly 900×600, something is wrong — most likely Windows display scaling. Do not resize it to fix this; report it instead (see below).
5. Deliver as a zip. The developer places them in `tests/screenshots/`.

The v2 engine scopes its image search to the game window rect (Ticket 1, PR 1.2), so a window-sized capture is precisely what the bot sees. It also makes these files independent of your monitor resolution, wallpaper, and whatever else is open — and means you are not sending a picture of your whole desktop.

### If your captures are not 900×600

That means Windows display scaling is not at 100%: at 125% scaling, a "900×600" window produces a 1125×750 image. **Send them anyway and tell us the scaling percentage.** The existing templates in `assets/` were cropped at whatever scaling the bot normally runs at, so if that is also your setting, the captures are correct and useful — we just need to know the number. Resizing them yourself would destroy the pixel accuracy that template matching depends on.

### Capture helper

Use [`helper_scripts/capture_arena_screenshots.py`](../../helper_scripts/capture_arena_screenshots.py) on the Windows game machine. It writes into `tests/screenshots/` relative to the repo root (no hardcoded drive paths). Manual one-off:

```python
import pygetwindow as gw
from PIL import ImageGrab

w = gw.getWindowsWithTitle("Raid: Shadow Legends")[0]
im = ImageGrab.grab(bbox=(w.left, w.top, w.left + w.width, w.top + w.height))
print(im.size)  # expect (900, 600)
im.save("01_bastion.png")
```

**Keep the game on the primary monitor.** PyAutoGUI captures only the primary display by default (`ImageGrab.grab(all_screens=False)`), so the bot cannot see a window on a second screen anyway. Capturing from one is a silent trap.

## Naming

`NN_short_description.png`, using the numbers below — for example `05_arena_opponent_list.png`. The numbering matters because PR 1.4 replays them in order.

---

## Core set — required for PR 1.4

Ten captures, one per screen the Arena sequence touches. Each corresponds to a node in `configs/arena_v2.yaml`, and the template in the right-hand column must be visible and unobstructed in that capture.

| # | Screen | Template that must be visible | Used by node |
|---|---|---|---|
| 01 | Bastion / home screen | `battleBTN.png` | `open_battle_menu` |
| 02 | Bastion with a pop-up ad open | `exitAdd.png` | `close_popup_ads` |
| 03 | Battle menu | `arenaTab.png` | `open_arena_tab` |
| 04 | Arena mode selection | `classicArena.png` | `enter_classic_arena` |
| 05 | Classic Arena opponent list, top of list | `arenaBattle.png`, ideally 3+ visible | `select_opponent` |
| 06 | Pre-battle team screen | `arenaStart.png` | `start_battle` |
| 07 | Loading screen | `loadingScreen.png` | future use |
| 08 | Mid-battle | `inBattle.png` | future use |
| 09 | Battle results | `tapToContinue.png` | `await_battle_end`, `dismiss_results` |
| 10 | Out-of-tokens refill prompt | `ArenaRefillGems.png` | `check_out_of_tokens` |

Notes:

- **02** is opportunistic — capture it whenever an ad appears. If ads have stopped appearing, say so and the developer will skip that assertion.
- **10** only shows up when Arena tokens are actually exhausted, so grab it at the end of a session. It is worth the wait: it is the guard that stops the bot spending real gems, and it is the one node we most want tested.
- **07** and **08** are not used by the Phase 1 config but cost nothing while you are there, and the next sequence will want them. Current 07/08 deliveries do not match `loadingScreen.png` / `inBattle.png` — re-capture or refresh those crops when convenient.

## Failure case — wanted for Phase 3, no longer blocking it

| # | Screen | Purpose |
|---|---|---|
| 11 | Any screen where the bot would be lost — an unexpected modal, an event popup, a login screen, mid-transition | The realistic input for the HITL crop tool |

Anything genuinely unexpected works. A real one from a failed run is ideal; a plausible stand-in is fine.

**This is no longer a gate on starting Phase 3.** Phase 3 can be built and tested against a dump generated from capture 05. What capture 11 uniquely gives us is a screen with something genuinely *unanticipated* on it, which is the only honest way to check the repair tool helps in the situation it exists for. So it is still wanted — just as a review step on the finished tool rather than a blocker on writing it.

### The bot can capture this one for you (easiest route)

Phase 2 shipped, so a failed v2 run now writes its own 900×600 crop of whatever screen it got stuck on, plus a JSON file naming the node that failed and the path it took to get there. That is a better capture 11 than anything posed by hand, and delivering it also closes the last Phase 2 acceptance item.

Start the sequence from somewhere that is *not* the Bastion so it fails on purpose:

```text
pip install -r requirements.txt
python -m engine.run configs/arena_v2.yaml
```

Look for `Crash dump written: logs/dumps/<timestamp>.json` in the log, then send that `.json` and the `.png` sitting next to it. If the PNG is not exactly 900×600, say so and include your display scaling percentage — do not resize it.

## Nice to have — not blocking

| # | Screen | Purpose |
|---|---|---|
| 12 | Opponent list scrolled to the bottom | Scroll support, deferred out of the MVP |
| 13 | Opponent list with the refresh button available | Refresh support, deferred out of the MVP |
| 14 | Quit Game confirmation prompt | Testing `back_to_bastion` |
| 15 | Lightning Offer popup | Testing `back_to_bastion` |

---

## What the developer will do with them

1. **Confirm each template still matches.** Run `pyscreeze.locate(template, screenshot, confidence=0.8)` for every target in `configs/arena_v2.yaml`. Any miss is a stale asset crop — a real bug that would otherwise only surface as a mystery failure on a live run.
2. **Replay the sequence offline.** Feed 01 → 09 to the engine in order and assert the config reaches `COMPLETED`. This is the closest thing to an integration test available without the game.
3. **Build and test the HITL tool** against capture 11, including verifying that a freshly cropped target is then found in that same screenshot.

The Phase 2 crash dump is deliberately the same 900×600 window crop as these captures, for the same reason: it is exactly the haystack the matcher was searching, so a target cropped from a dump is guaranteed to be searched for at the same scale it was cut at.

## What these captures do and do not prove

The matching is a pure function of two PNG files, both of which are fixed artifacts — the templates live in git, the captures are delivered as-is. So the offline results are identical on any machine the developer works from. There is no hidden dependency on their OS, monitor, or display settings.

What that buys is real but bounded. It proves a template still matches **that particular frame**. It does not prove the template matches every variant of that screen, and Arena screens vary constantly — different opponents, different power ratings, different portraits, seasonal banners and event overlays. A crop that matches capture 05 can still miss on a live opponent list.

It also says nothing about timing, animations, mid-transition frames, window focus, or whether a click at the matched coordinates does what we expect.

So a green offline suite means "the assets are not stale and the graph is wired correctly", which is most of the value and catches most of the bugs. It does not replace the live smoke run in PR 1.3. **If any capture can include an unusual variant of a screen — an event banner across the Arena list, an unusual opponent layout — send that too.** Variety is worth more here than perfection.

## If some captures cannot be supplied

Say which ones. Phase 1's core (PRs 1.1–1.3) still ships — it is tested against a hand-written fake and needs no images. What is lost is any confidence that the asset crops are still valid, which means the first live run becomes the first real test. Phase 3 is built and tested against a dump generated from capture 05; what you lose without capture 11 is only the realism check on an unanticipated screen.
