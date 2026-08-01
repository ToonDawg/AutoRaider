# Phase 4: Migration & Deprecation

**Status: PR 4.1 shipped (offline) — 2026-08-01.** Suite: `65 passed, 2 skipped` on macOS with no game (was 55/2 after Phase 3). PR 4.2 is **gated and not started** — see [the gate](#the-gate-reads-on-cutover-not-on-the-adapter) below. PR 4.3 is untouched.

**Goal:** move real scheduled work onto the v2 engine, one module at a time, without breaking the running app.

Everything here is reversible by design, because migration is where a rewrite usually breaks the thing it was replacing.

## The gate reads on cutover, not on the adapter

The original wording — *"do not start this ticket until Phases 1–3 are complete and the Arena sequence has survived real scheduled runs"* — is circular if applied to the whole ticket: the Arena sequence cannot survive a scheduled run until something can schedule it, and PR 4.1 is that something.

Read the gate against what each PR actually risks:

| PR | Risk to the running app | Gated on |
|---|---|---|
| 4.1 adapter | None. A new key, off in every preset, run by hand. v1 untouched. | Nothing |
| 4.2 cutover | Real. Scheduled tasks and Daily Quests start depending on v2. | A week of scheduled v2 runs **and** one real failure fixed entirely through the HITL tool |
| 4.3 second module | Low, same shape as 4.1 | 4.2 proving the loop works |

So PR 4.1 ships now and PR 4.2 does not. The strict reading applies where the epic meant it: at the point v1 stops being what actually runs.

**PR 4.1 is offline-complete but not live-proven.** The live proofs it needs are in the [Windows live-run runbook](./Windows_Live_Runbook.md), runs 1, 2 and 5.

## Why the original plan was rewritten

The draft was: write "best guess" YAML for every module, run them, fix them with the HITL tool, then `rm -rf Modules/`.

The last step breaks the application. `Modules/` is not a leaf:

- `app/pyAutoRaid.py` imports all eight command classes and registers them in `__init__`.
- `utils/command_factory.py` defines `CommandKeys` for each one.
- `config.ini` references those command keys in five task presets (`10am Tasks`, `Arena`, `Backup Tasks`, `Clan Boss/ Arena`, `None`) and in `[Schedules]`.
- `gui/main_gui.py` renders a checkbox per registered command.
- `utils/scheduler.py` fires those keys on a timer.
- `Modules/daily_quests/DailyQuests.py` calls `self.arena_battles.execute(5)` directly.

Deleting the directory takes out the scheduler, the GUI task list, and Daily Quests along with it. The other problem is the draft's sequencing: writing eight speculative YAML files before any of them has run is eight times the rework when the engine's shape turns out to need adjusting.

## Blocker to resolve before any v1 module can be retired

**The YAML has no counters, and the app depends on counts.** `DailyQuests` needs exactly 5 Arena battles; the Classic Arena command takes a `count` argument. A cyclic graph gives "repeat until nothing matches", which is not the same thing.

This needs an explicit decision from the epic owner before Phase 4 can finish, and it is a real design question rather than an implementation detail. The realistic options:

1. **Repeat count lives on the runner, not in the YAML** — the caller runs the sequence N times. Keeps the guardrail intact and is by far the simplest. Probably the right answer.
2. **A `repeat` field on the sequence** (not on nodes) — one integer at the top of the file, no expressions.
3. **Accept "until exhausted"** and drop exact counts, if nothing actually depends on the precise number.

Option 1 requires no schema change at all. Do not invent a counter node type.

### Recommendation: option 1, awaiting sign-off

**PR 4.1 built option 1 and does not commit anyone to it.** `SequenceCommand` takes `repeat: int = 1`; the registered `classic_arena_v2` key uses the default, so nothing in the app repeats anything yet. The decision only becomes load-bearing at PR 4.2, when `DailyQuests` swaps `arena_battles.execute(5)` for `SequenceCommand(..., ARENA_V2_CONFIG, repeat=5)`. It is cheap to change until then, and option 2 would still be available.

Two things the epic owner should weigh before signing off, both discovered while wiring it:

**Repeat cannot see why an attempt ended.** The refill guard in `arena_v2.yaml` is a legitimate stop, so running out of tokens exits `leave_refill_prompt` with a null `on_success` and reports `COMPLETED`. A caller asking for 5 will therefore do all 5, and attempts 2–5 will each navigate to the Arena, find the refill prompt, and ESC back out. Nothing is spent and nothing breaks — it just wastes about a minute. Today v1 detects this and stops immediately.

Fixing it properly means the sequence needs a way to say *"finished, and do not call me again"*, which is a second outcome, not a counter. That is a schema question worth answering deliberately rather than smuggling into the cutover. The cheap alternative is to leave it: five wasted navigations once a day, on a bot that already runs unattended.

**A failed attempt stops the remaining ones.** If an attempt does not reach `COMPLETED`, `SequenceCommand` writes the dump and returns rather than starting the next one — the bot is somewhere the sequence does not know how to start from, and repeating would multiply dumps of the same failure. v1's behaviour differs here: it swallows the error and moves on. If Daily Quests would rather get 3 battles than 0, say so and this becomes a one-line change.

---

## PR 4.1 — Run Arena v2 through the existing app

**Status: DONE (offline).** `engine/sequence_command.py`, registered in `app/pyAutoRaid.py`, 9 tests in `tests/test_sequence_command.py`. Acceptance 1–3 are all live checks on the game machine — [runbook run 5](./Windows_Live_Runbook.md#5-classic_arena_v2-from-the-gui).

A single adapter, so a YAML sequence can be scheduled like any other command.

```python
class SequenceCommand(CommandBase):
    """Runs a YAML sequence. Knows nothing about which sequence it is running."""
    def __init__(self, app, logger, click_handler, config_path: Path, repeat: int = 1): ...
```

It loads and validates the config, runs it `repeat` times through `SequenceRunner`, writes a crash dump on a non-`COMPLETED` outcome, and cleans up exactly like `_cleanup_after_task` does today.

Register it under a **new** command key (`classic_arena_v2`), alongside the existing one. Do not replace the v1 registration yet. Both appear in the GUI; v2 gets run manually and watched.

### Acceptance

1. `classic_arena_v2` appears in the task list and runs from the GUI.
2. The v1 `Classic Arena` command is unchanged and still works.
3. Cancelling with F2 mid-run stops it — `CancellationException` propagates out of the runner as specified in Ticket 1.

### How it was built

**The adapter lives in `engine/`, not `Modules/`.** `Modules/` is v1 and frozen. `engine/sequence_command.py` imports `utils.base_command` and nothing from `app/`, so the dependency arrow points app → engine like every other v2 module, and `tests/test_seam.py` now guards that: importing it must not pull in `pyautogui`, `pygetwindow`, or `app.pyAutoRaid`. Without that guard the whole engine suite would follow the adapter onto Windows the first time someone adds a convenience import.

**Registration uses a bound constructor, so the factory did not have to change.** `CommandFactory.get_command` constructs every command as `cls(app, logger, click_handler)` — three positional arguments, shared by all eight v1 commands. `SequenceCommand.bind(config_path, repeat)` returns a `functools.partial` that satisfies exactly that signature:

```python
self.command_factory.register_command(
    CommandKeys.CLASSIC_ARENA_V2,
    "Classic Arena (v2 engine)",
    SequenceCommand.bind(ARENA_V2_CONFIG),
)
```

Widening the factory to pass per-command kwargs was the alternative. It is two lines, but they are two lines on the code path every v1 command is constructed through, for the benefit of one new command. The partial costs nothing and cannot regress v1.

**Dump and cleanup are the existing ones, not new ones.** The adapter calls `engine.run.run_sequence`, the same function `python -m engine.run` calls, so the load-bearing dump-before-recover ordering from PR 2.2 is shared rather than reimplemented. `_cleanup_after_task` is a copy of v1's, down to the log line: `back_to_bastion()`, then `delete_popup()`, wrapped so a failed cleanup cannot kill the bot. `_screen_grabber` in `engine/run.py` became public `screen_grabber` so both callers capture identically.

**Cancellation propagates.** `execute()` catches `CancellationException` only to log which attempt was interrupted, then re-raises. Swallowing it would be invisible at `repeat=1` and would start the next battle at `repeat=5`. Cleanup still runs, because `run_sequence` recovers in a `finally`.

### Finding: the in-app path is not window-scoped

`AutoRaider.__init__` builds `ClickHandler(logger)` with no `region_provider`, so `click_handler.region` is `None` and **an in-app v2 run searches the whole desktop**, while `python -m engine.run` searches the 900×600 game window. The adapter uses whatever region the app's handler reports and logs `Region: FULL SCREEN` when there is none, so a log always says which geometry produced a result.

This was left alone deliberately. Giving the app's shared `ClickHandler` a region provider would change matching for all eight v1 commands, which is exactly what this epic's guardrails forbid, and it is not the kind of change to make blind on a machine with no game.

What it means in practice: **the Phase 1 live smoke run does not prove the in-app path.** The runbook therefore asks for the same run twice, once with `--full-screen` ([run 2](./Windows_Live_Runbook.md#2-live-smoke-run-full-screen)). If window-scoped passes and full-screen fails, region scoping is load-bearing and PR 4.2 needs its own decision about giving the app a region provider before anything is cut over. The epic already notes why this matters: several templates are tiny (`loadingScreen.png` is 16×14), and a desktop-wide search invites false positives.

---

## PR 4.2 — Soak and cut over Arena

**Status: NOT STARTED, and deliberately so.** Do not open this until acceptance #2 below has actually happened. It is not a formality — it is the one criterion that tests the epic's premise rather than its code, and it cannot be satisfied offline, by a fixture, or by a failure that someone fixed in an editor while they were in there.

The prerequisites, in order: the [runbook](./Windows_Live_Runbook.md) runs 1–5 pass, then a week of scheduled v2 runs, then at least one real failure repaired entirely through `python -m hitl`. Also settle the [counter decision](#recommendation-option-1-awaiting-sign-off) and, if run 2 exposed it, the region-provider question, before any key is repointed.

Run `classic_arena_v2` on the real schedule for a meaningful stretch (at least a week of scheduled runs), fixing failures through the HITL tool rather than by editing Python. The measure of success is that the HITL loop actually works: dumps get produced, crops get repaired, runs get better.

Only once that holds:

- Point the `daily_ten_classic_arena` key at `SequenceCommand`.
- Update `DailyQuests` to use it, honouring whichever counter decision was made above.
- Leave `Modules/arena/DailyTenArenaCommand.py` on disk, unregistered. It is the rollback, and it costs nothing to keep.

### Acceptance

1. A week of scheduled Arena runs on v2 with no regression against v1's hit rate.
2. At least one real failure diagnosed and fixed entirely through the Phase 3 UI, with no Python changes. If this has not happened, the epic's core premise is unproven and Phase 4 should stop here.
3. Daily Quests still completes its Arena portion.

---

## PR 4.3 — One more module

**Status: NOT STARTED.** Gated on 4.2, and worth restating because this is where a migration ticket usually turns into a rewrite: **one** module. Not speculative YAML for the remaining seven, and not `Modules/` deletion, which the last section of this ticket puts explicitly out of the epic.

Pick **one** — whichever is simplest, likely `RewardsCommand` or Iron Twins. Not all of them.

The point is to find out what the engine is missing when pointed at something that is not Arena. Expect to need one or two new action types (`WAIT_UNTIL_DISAPPEARS` and a swipe are the likely candidates). Add them only when a real node needs them, and add them to the engine, never as special cases.

Write up what the second module revealed. That write-up is what makes migrating the remaining modules a planning exercise rather than a discovery exercise, and it is the natural end of this epic.

### Acceptance

1. One additional module runs from YAML.
2. Any new action types are justified by a node in a committed config, and are covered by `FakeScreen` tests.
3. A short note on what the engine was missing, and what the remaining modules will need.

---

## Removing `Modules/` — not in this epic

Deletion is a separate ticket, raised only when every module has a working v2 equivalent that has soaked. When that time comes, it is a coordinated change across `app/pyAutoRaid.py`, `utils/command_factory.py`, `config.ini` presets and schedules, `gui/main_gui.py`, and `DailyQuests` — not a `git rm`.

Until then the old modules cost nothing. They are unregistered, unimported dead weight, and they are the only rollback path.

---

## Deliverables — PR 4.1

```
engine/sequence_command.py     # SequenceCommand, bind(), ARENA_V2_CONFIG
engine/run.py                  # _screen_grabber -> screen_grabber (now has two callers)
utils/command_factory.py       # + CommandKeys.CLASSIC_ARENA_V2
app/pyAutoRaid.py              # + one register_command call, v1 registrations untouched
tests/test_sequence_command.py # bind, repeat, dump-and-stop, cancellation, region, bad config
tests/fakes.py                 # + FakeClickHandler (region + back_to_bastion + delete_popup)
tests/test_seam.py             # + guard: engine.sequence_command imports without app/ or Windows deps
```

No new dependencies. Nothing in `Modules/` or `gui/` was touched, and every change to an existing file is additive apart from the one rename in `engine/run.py`.

`config.ini` is not edited by hand. `ConfigHandler._initialize_enum_settings` adds `classic_arena_v2 = False` under `[Settings]` on the next launch, and the task presets do not mention the key at all, so `run_task` will never pick it up until someone ticks the checkbox. The v2 command cannot fire on a schedule by accident.
