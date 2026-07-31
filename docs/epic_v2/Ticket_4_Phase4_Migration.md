# Phase 4: Migration & Deprecation

**Goal:** move real scheduled work onto the v2 engine, one module at a time, without breaking the running app.

**Do not start this ticket until Phases 1–3 are complete and the Arena sequence has survived real scheduled runs.** Everything here is reversible by design, because migration is where a rewrite usually breaks the thing it was replacing.

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

---

## PR 4.1 — Run Arena v2 through the existing app

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

---

## PR 4.2 — Soak and cut over Arena

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
