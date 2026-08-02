# Windows live-run runbook

**For:** whoever has the game machine. **Purpose:** close the live proofs that Phases 1–3 could not close from macOS, in the order that makes each one cheapest.

Nothing here may be faked from another OS. If a run cannot be done, say so and leave the box unticked — a guessed result is worse than an open one.

## Status after the 2026-08-01 session

**Runs 1, 2 and 5 passed.** A v2 click lands on the game, and a YAML-driven Arena battle runs from the app's own scheduler thread. That was the epic's central unknown and it is now retired.

**What that session did not deliver: the files.** `logs/` is gitignored, so neither the run logs nor the crash dump from run 4 reached the repo. The dump is not a nice-to-have — PR 4.2 is gated on repairing one real failure through `python -m hitl`, and that dump is the input. Run 3 wants the same file.

> **Before you close this window, copy the evidence out.** `logs/dumps/<timestamp>.json` and the `.png` beside it, plus the run log from `logs/`. Attach them to the ticket or commit them somewhere outside `logs/`. A ticked box with no artefact behind it costs more than an unticked one, because it stops anyone from asking again.

**Also: do not edit code on the game machine unless the change is the finding.** The 2026-08-01 session's commit regressed the test suite and deleted every task preset from `config.ini`. Both are fixed; the details are in [the epic](./Epic_AutoRaider_v2.md#what-the-live-run-brought-back). If a run exposes something that needs a code change, write down what you saw and let it be changed where the tests run.

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
| 1 | Live smoke, window-scoped | PR 1.3 acceptance #4 | **Passed** — below |
| 2 | Live smoke, full screen | PR 4.1 geometry parity | **Passed** — below |
| 3 | HITL real-mouse drag | the last unverified bit of Phase 3 | Open — [Ticket 3](./Ticket_3_Phase3_HITL.md#1-smoke-test-the-hitl-window--done-on-macos-with-one-human-check-left) |
| 4 | Deliberately-failed run | PR 2.2 acceptance #2 + capture 11 | Ran, but **the dump was never sent** — [Ticket 2](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups) |
| 5 | v2 tasks from the GUI | PR 4.1 acceptance | **Passed**, though the tab has since moved — below |
| 6 | Supervised loop, until tokens run out | the new Arena cycle, and capture 10 | **Do this next** — below |

**Run 6 is the priority**, followed by getting run 4's dump off the machine. Everything else above has passed.

Runs 3 and 4 feed each other: run 4 produces a real dump, which is the most realistic thing you can point the run-3 window at. If last session's dump is still on disk under `logs/dumps/`, run 3 needs nothing new — just send it.

---

## 1. Live smoke run, window-scoped: one Arena battle

**Passed on 2026-08-01.** Note that the config no longer stops after one battle — see [run 6](#6-supervised-loop-run-until-tokens-run-out). This section describes the run as it was proven.

This was the gate. It was the first time any v2 code moved a real mouse.

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

## 3. HITL real-mouse drag

Small, and the only part of Phase 3 still unverified. The HITL window was opened on macOS and driven through its whole checklist mechanically, so all that is left is the part a script cannot fake:

```text
python -m helper_scripts.make_sample_dump   # only if logs/dumps/ is empty
python -m helper_scripts.hitl_smoke         # should report all checks passing
python -m hitl
```

Point it at a **real** dump if you have one — last session's run 4 should have left one under `logs/dumps/`. A real screen is a much better test than the synthetic fixture.

Then drag a real rectangle around a landmark you can locate independently, and confirm the toolbar's `left/top/width/height` are image pixels — not display pixels, not scaled. That mapping is the one thing the smoke script steps over, and it is where the scaling bug would hide.

## 4. Deliberately-failed run

**Ran on 2026-08-01. The dump it produced never left the machine, so this is not closed.** Full detail in [Ticket 2 → Windows follow-ups](./Ticket_2_Phase2_Telemetry.md#windows-follow-ups).

Start the sequence from somewhere that is *not* the Bastion so it fails on purpose, then send the `.json` and the `.png` beside it from `logs/dumps/`. That pair is simultaneously the Phase 2 acceptance evidence, capture 11, the input to run 3, and the thing PR 4.2 is gated on. It is the single highest-value artefact this runbook produces.

## 5. v2 Engine tab

**Passed on 2026-08-01, but the tab has moved since.** This exercises the PR 4.1 adapter in the app: the scheduler's thread, the app's shared `ClickHandler`, and the F2 cancel path.

```text
python main.py
```

1. v2 tasks now live on their own **V2 Engine** tab, not the Tasks tab. Tick `Classic Arena (v2 engine)` there and press **Run Selected**.
2. Expect the same log lines as run 1, then `Returned to bastion and cleared popups.`
3. **Press F2 mid-run.** The run must stop, and cleanup still runs, so ESC spam back to the Bastion afterwards is expected and correct.
4. Confirm `Classic Arena` (v1) still runs from the **Tasks** tab exactly as it did before. This is the rollback path and it has to keep working.

The split is deliberate and worth understanding, because it is what stops an accident. The scheduler resolves a schedule's name to a `SelectionItems` preset section; `[V2 Tasks]` is not one, and v2 commands are no longer listed on the Tasks tab at all. So there is no sequence of clicks that puts a v2 task on a timer. PR 4.2 is what changes that, and it is gated on run 4 having produced a failure that the HITL tool then fixed.

## 6. Supervised loop run, until tokens run out

**This is the next thing to do, and it needs supervising — it can cost gems if it goes wrong.**

`configs/arena_v2.yaml` no longer stops after one battle. `return_to_opponent_list` now feeds back into `select_opponent`, so the sequence fights until the out-of-tokens refill prompt appears. There is no counter anywhere; the token guard *is* the exit.

That makes `check_out_of_tokens` load-bearing for the first time. Its target, `ArenaRefillGems.png`, has never been matched against a real screen — capture 10 is still undelivered — and every run now ends on it. If the crop is stale, the guard returns false and the sequence clicks `arenaStart.png` while the refill modal is up. Most likely nothing matches and the run aborts with a dump. The bad case is a match on the modal's confirm button.

So:

1. **Start with only a few Arena tokens left**, so the exit arrives in a minute or two rather than after thirty battles.
2. **Watch the whole run with a hand on F2.** If a gem-spend prompt appears, F2 immediately.
3. Run it from the Bastion:

```text
python -m engine.run configs/arena_v2.yaml
```

What a pass looks like: several battles, then `Step N: check_out_of_tokens — IMAGE_PRESENT(ArenaRefillGems.png)` succeeding, one ESC at `leave_refill_prompt`, and `Run finished: outcome=COMPLETED`. No gems spent.

**This run is worth doing whichever way it goes,** because both outcomes deliver capture 10:

- **The guard fires.** Send the log, and grab `10_out_of_tokens.png` off the screen while the prompt is up. That un-skips `tests/test_assets_match.py` and lets `test_replay.py` assert `COMPLETED` again.
- **The guard misses and the run aborts.** The crash dump under `logs/dumps/` *is* the out-of-tokens screen, captured at exactly the 900×600 geometry the matcher searched. Send the `.json` and `.png`. That is the better artefact of the two, and repairing the crop through `python -m hitl` would also close PR 4.2's gate.

`Run finished: outcome=STEP_LIMIT` means the cycle never found its exit and the runner capped it at 200 steps. That is the safety net working, not a hang. Send the dump.

---

## Do not, while you are in here

- **Do not commit code changes from the game machine.** Last session's commit broke six tests and deleted every task preset from `config.ini`. Write down what you saw instead; it gets changed where the tests run. See [the epic](./Epic_AutoRaider_v2.md#what-the-live-run-brought-back).
- **Do not fix `back_to_bastion()`'s unbounded ESC loop.** It is a real bug and it has its own ticket now ([Ticket 5](./Ticket_5_BackToBastion_Cap.md)). If a run hangs there, kill it and report it — the crash dump is already on disk by that point, so the evidence survives.
- **Do not lower the 0.8 confidence threshold** to make something match. That converts a visible failure into an intermittent one.
- **Do not resize a dump PNG** that came out at the wrong size. The wrong size is the finding.
- **Do not edit `configs/arena_v2.yaml` by hand** to get past a bad target. Repairing it through `python -m hitl` is the thing this epic exists to prove; doing it in an editor proves nothing.
