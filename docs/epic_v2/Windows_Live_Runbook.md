# Windows live-run runbook

**For:** whoever has the game machine. **Purpose:** close the live proofs that Phases 1–3 could not close from macOS, in the order that makes each one cheapest.

Everything in this epic so far has been proven against fakes, replayed screenshots, and synthetic images. That is enough to know the engine walks the graph correctly. It is **not** enough to know a single click lands on the game. Until run 1 below passes, every later phase is wiring an unproven click path into something.

Nothing here may be faked from another OS. If a run cannot be done, say so and leave the box unticked — a guessed result is worse than an open one.

## Before you start

```text
git pull
pip install -r requirements.txt     # the full set; pywin32 and customtkinter are Windows-only
```

- Launch RAID through Plarium Play and leave it at the Bastion.
- Windows display scaling must be **100%**. At any other setting `ImageGrab` returns a different pixel size from the window rect, and every template match degrades. See [Screenshots Required → if your captures are not 900×600](./Screenshots_Required.md#if-your-captures-are-not-900600).
- The app resizes the window to 900×600 at (500, 200) itself. Do not resize it by hand.

## Run the proofs in this order

| # | Run | Closes | Detail |
|---|---|---|---|
| 1 | Live smoke, window-scoped | PR 1.3 acceptance #4 | below |
| 2 | Live smoke, full screen | PR 4.1 geometry parity | below |
| 3 | HITL window smoke | Phase 3 GUI unverified | [Ticket 3](./Ticket_3_Phase3_HITL.md#1-smoke-test-the-hitl-window-you-can-do-this-without-the-game) |
| 4 | Deliberately-failed run | PR 2.2 acceptance #2 + capture 11 | [Ticket 2](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups) |
| 5 | `classic_arena_v2` from the GUI | PR 4.1 acceptance | below |

Runs 3 and 4 feed each other: run 4 produces a real dump, which is the most realistic thing you can point the run-3 window at. Do run 4 first if you only have time for one.

---

## 1. Live smoke run, window-scoped: one Arena battle

This is the gate. It is the first time any v2 code has moved a real mouse.

```text
python -m engine.run configs/arena_v2.yaml
```

Start it **from the Bastion** — the sequence's first node looks for an ad to dismiss and then the Battle button.

What a pass looks like:

1. A `Region: left=500 top=200 width=900 height=600` line in the log. A `could not find window titled` warning instead means the game is not open, and the run will search your whole desktop.
2. Ten `Step N: <node> — <ACTION>(<target>)` lines, ending at `return_to_opponent_list`.
3. `Run finished: outcome=COMPLETED`.
4. Exit code 0, one Arena battle actually fought, and the game back at the Bastion.

Send back the log file from `logs/` either way, plus which node it stopped on if it did not complete.

Two failure modes worth telling apart before reporting anything else:

- **Stops at `open_battle_menu`** — the click path works but nothing matched. Try run 2 to find out whether region scoping is the cause.
- **Completes but no battle happened** — matches are landing on the wrong thing. Send the log and a screenshot of where it ended up; do not adjust the confidence threshold.

## 2. Live smoke run, full screen

```text
python -m engine.run configs/arena_v2.yaml --full-screen
```

Same expected outcome as run 1. This is not a duplicate: **the in-app adapter shipped in PR 4.1 runs full-screen**, because the application builds its `ClickHandler` without a region provider and PR 4.1 deliberately did not change that (it would alter matching for all eight v1 commands). So run 1 proves the CLI path and run 2 proves the geometry the GUI path will actually use.

If run 1 passes and run 2 fails, that is a real finding and the most useful thing this runbook can produce: it means region scoping is load-bearing, and PR 4.2 cannot cut over until the app's `ClickHandler` gets a region provider of its own. Report it rather than working around it.

## 5. `classic_arena_v2` from the GUI

Only after runs 1–4. This exercises the PR 4.1 adapter in the app: the scheduler's thread, the app's shared `ClickHandler`, and the F2 cancel path.

```text
python main.py
```

1. On the **Tasks** tab there are now two Arena entries: `Classic Arena` (v1, unchanged) and `Classic Arena (v2 engine)`. Tick only the v2 one and run the task.
2. Expect the same log lines as run 1, then `Returned to bastion and cleared popups.`
3. **Press F2 mid-run** on a second attempt. The run must stop; it must not finish the battle and it must not start another attempt. Cleanup still runs, so ESC spam back to the Bastion afterwards is expected and correct.
4. Confirm `Classic Arena` (v1) still runs exactly as it did before. This is the rollback path and it has to keep working.

The new key defaults to off in every preset and every schedule, so it cannot fire on a timer until someone ticks it deliberately. Leave it that way — PR 4.2 is what puts v2 on the schedule, and it is gated on run 4 having produced a failure that the HITL tool then fixed.

---

## Do not, while you are in here

- **Do not fix `back_to_bastion()`'s unbounded ESC loop.** It is a real bug ([Ticket 2](./Ticket_2_Phase2_Telemetry.md#known-risk-not-fixed-here)) and it needs its own ticket. If a run hangs there, kill it and report it — the crash dump is already on disk by that point, so the evidence survives.
- **Do not lower the 0.8 confidence threshold** to make something match. That converts a visible failure into an intermittent one.
- **Do not resize a dump PNG** that came out at the wrong size. The wrong size is the finding.
- **Do not edit `configs/arena_v2.yaml` by hand** to get past a bad target. Repairing it through `python -m hitl` is the thing this epic exists to prove; doing it in an editor proves nothing.
