---
name: automation-best-practices
description: Best practices for reliable image-based desktop/game automation — screen-state thinking, template-matching discipline, waits vs timers, loop exits, retry/recovery, OCR, and testability. Apply when writing or debugging v2 YAML configs, ClickHandler/ScreenActions behavior, or OCR.
---

# Automation Best Practices

Guidance for building automation that survives at 3am: screen-state thinking, template-matching discipline, bounded waits, idempotent loops, and evidence on failure. Mapped onto this repo (AutoRaider — image-template automation of a game window, driven by `ClickHandler` and the v2 YAML graph engine).

The core idea, before any specific rule: **this is screen-state automation.** Detect the actual state, act, verify, and always have a bounded way out. Every rule below is an instance of that.

## 1. Think in screen states, not script steps

Model each config node as a transition between screen states. A node's `on_success` / `on_failure` is the answer to "did the screen change the way I expected?"

- **Classify states, not elements.** Ask "are we in the battle?" not "is the start button visible?". For example the Arena config does not count battles; it waits for `tapToContinue.png` to *appear* as the battle-ended signal, because that is a state change, not a timer.
- **Verify before AND after an action.** A click that "succeeds" because the template matched is only real if the next state actually arrived. The next node IS that verification — chain it.
- **Popups are random states.** Handle them with best-effort nodes whose both edges continue (`close_popup_ads` does this — no ad is the normal case). Expect an ad popup anywhere.
- **Recovery to a known baseline is the caller's job, not the graph's.** When a run goes lost (null `on_failure` → ABORTED), `run_sequence` recovers by ESC-spamming back to the Bastion and clearing popups. Do not encode "go home" as a fallback node.

## 2. Template-matching discipline

- **Targets are bare filenames**, resolved against `assets/` by `ClickHandler`. A path prefix (`assets/foo.png`) becomes `assets/assets/foo.png` and never matches.
- **Asset names are compared case-sensitively** (`missing_assets` walks `assets/` as posix-relative paths) even though Windows FS is case-insensitive — a case-mismatched target fails silently. Keep names exact (`arenaBattle.png`, not `arenabattle.png`).
- **Tight, unique crops.** The top false-positive cause is a template that includes borders, background, or surrounding context. Crop to the core element but keep an identifying anchor feature — cropping too far removes the uniqueness and invites false matches.
- **Lossless PNG, never JPEG**, for templates. The repo's assets are PNG.
- **Confidence is 0.8 everywhere** (`DEFAULT_CONFIDENCE`). If a template matches the wrong thing, fix the crop or scope the region — do not reach for lower confidence as a first move. Prefer distinctive templates over threshold tuning.
- **Scope the search region.** `python -m engine.run` scopes matching to the game-window rect (900×600); the in-app path searches the full desktop. This asymmetry is a known, deliberate v1-compatibility behaviour — do not "fix" it by changing `ClickHandler` defaults.
- **Multi-match** is how you "click each of several identical buttons": `CLICK_IMAGE` with `match: best|top|bottom` plus `ignore_visited` / `clear_visited`. Used in Arena to fight each opponent and to refresh after exhausting them.
- **Refresh stale crops.** A template that stops matching live screens is stale — re-crop, don't weaken the config around it. `tests/test_assets_match.py` exists to catch this; a target with no delivered capture belongs in `BLOCKED_BY_MISSING_CAPTURE`, loudly named, not silently dropped.

## 3. Wait on state change with a bounded timeout — not on sleeps

- Use `WAIT_FOR_IMAGE` / `WAIT_UNTIL_DISAPPEARS` for anything of variable duration (battle end: 120s timeout in Arena; check `check_interval_seconds` so polling is not a hot loop).
- `settle_seconds` is for short UI settle after an action. Do not chain `PRESS_KEY` + long settle as a substitute for waiting on the resulting state.
- **Every wait must be bounded.** A wait that cannot time out is a hang. `timeout_seconds` is required policy, not decoration.
- Wait for the *result* state, not an intermediate one. Battle completion is detected by `tapToContinue.png` appearing — there is no victory/defeat detection, and that is fine.

## 4. Loops, exits, idempotency

- **Loops are cycles in the graph, never counters.** No variables, expressions, or loop constructs in YAML. Arena fights "until tokens run out", not "10 times".
- **Every cycle needs a state-based exit guard.** In Arena the only clean exit is the `ArenaRefillGems.png` token guard — every run ends there. If that guard ever stopped matching, the run would fight forever, which is why:
- **Runaway cycles are capped by `max_steps` (200)**, ending as STEP_LIMIT with a crash dump rather than spinning. Keep this property — a cycle with no exit is a bug, and the cap is the safety net, not the design.
- **Nodes should be idempotent under replay.** Re-running a config must not double-consume — e.g. don't click a Confirm button when the prompt may already have been handled. Arena's free-refill `Confirm` click feeds back to re-check rather than blindly advancing.

## 5. Retry, recovery, evidence

- The runner treats any node exception as a failure → `on_failure` edge — **except `CancellationException`, which must propagate.** If the runner swallows it, the F2 cancel silently stops working.
- **Evidence before recovery, in that order.** `run_sequence` writes a crash dump (screenshot + JSON context: failed node, visited path, region) to `logs/dumps/` BEFORE recovering, because recovery (ESC back to bastion, close popups) changes the screen. Keep that ordering if you touch it.
- On ABORTED, the crash dump is the evidence. Debug offline with `python -m engine.validate <config>` (schema/assets/reachability) and a `ScreenshotScreen` replay against delivered captures — don't burn a live run to reproduce.
- `retries` on a node exist for transient misses (animation, rendering lag). Don't set them high to mask a genuinely wrong template.
- If recovery itself fails, it is logged and the run still reports its outcome. Failing to collect a dump must never take down the run.

## 6. OCR (tesseract)

The repo's `OCRHandler.text_on_screen_contains` is raw: full-screen grab, default `image_to_string`, case-insensitive substring match. It is a fallback, not a primary control — do not gate a critical single point of failure on it.

If you must make OCR reliable:

- **Preprocessing is the biggest lever** (research: +15–25% accuracy): grayscale, upscale to ~300 DPI, denoise, adaptive threshold, contrast (CLAHE), deskew.
- **Scope the region** — OCR the element's region, not the whole desktop.
- **Tune Tesseract**: LSTM engine (`--oem 1/3`), `--psm 6`/`7` for single-line regions, `tessedit_char_whitelist` when a region is known digits, `tessdata_best` language models.
- **Validate output** — regex or known-format check on the result; treat low-confidence/low-relevance hits as "not found".

## 7. Keep it testable (the repo's superpower)

The `ScreenActions` protocol is the whole architecture: the engine never imports pyautogui, and tests drive a `FakeScreen` (scripted) or `ScreenshotScreen` (replays real captures through the same pyscreeze matcher at confidence 0.8).

- New node/edge paths → add a `FakeScreen` graph test in the style of `test_arena_config.py`. Script the per-target results queue and assert the visited node path and final outcome.
- New image targets → must match a delivered 900×600 capture (`test_assets_match.py`). Until the capture exists, name the target in `BLOCKED_BY_MISSING_CAPTURE` with a comment saying which capture it awaits.
- Any new config → run `python -m engine.validate configs/<name>_v2.yaml`; it checks schema, that every image asset exists (case-sensitively), and that all nodes are reachable from `start_node`.
- Keep `engine/` free of platform imports so the suite runs on any OS with no game.

## Failure-mode quick reference

| Symptom | Likely cause | Move |
|---|---|---|
| Node never succeeds, times out | Template stale / wrong state expected | Re-crop the asset or add a capture; verify with ScreenshotScreen replay |
| Wrong element clicked | Template too loose / includes context | Tighten the crop; prefer `region` scoping; raise effective distinctiveness |
| Run ends ABORTED at node X | Null `on_failure` — bot lost | Add an `on_failure` edge or accept the abort + crash dump as evidence |
| Run ends STEP_LIMIT | Cycle with no exit guard | Add a state-based exit (like the token guard) |
| Cancel (F2) ignored | `CancellationException` swallowed | Make sure it propagates through runner + nodes |
| Config passes validate but fails live | In-app path is full-desktop, not window-scoped | Expected asymmetry; check `--full-screen` on CLI runs |
| OCR misses text | Raw tesseract, no preprocessing | Restrict region; preprocess; tune PSM/whitelist |
