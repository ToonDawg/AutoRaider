# Ticket 5: Cap `back_to_bastion()` and make F2 work during cleanup

**Status:** NOT STARTED. **Owner:** epic owner. **Blocks:** nothing, but it undermines every other safety guarantee in the epic while it stands.

Carved out of [Ticket 2](./Ticket_2_Phase2_Telemetry.md#known-risk-not-fixed-here), where it was flagged three times and deliberately not fixed. It has its own ticket now so it stops being a drive-by temptation in someone else's PR.

## The bug is worse than "unbounded loop"

The original flag said `back_to_bastion()` is a `while True` with no attempt cap, so it hangs if the quit prompt never appears. That is true. Reading the cancel path alongside it turns up something more serious:

**F2 cannot interrupt `back_to_bastion()`.** Two independent reasons, either of which is sufficient:

1. **Nothing in the loop's hot path checks `cancel_flag`.** `click_image`, `wait_for_image` and `wait_until_disappears` all check it and raise `CancellationException`. `press_key` and `_locate_image` do not. The loop calls only those two unless a Lightning Offer happens to be on screen, so in the ordinary hang there is no point at which cancellation is noticed.
2. **The loop swallows the exception even if it were raised.** `CancellationException` subclasses `Exception`, and `back_to_bastion()` wraps its whole body in `except Exception`. A cancel arriving via the Lightning Offer branch would be logged as an error and discarded.

```347:381:utils/click_handler.py
    def back_to_bastion(self) -> None:
        try:
            self.logger.info("Navigating back to Bastion.")
            # ...
            while True:
                self.press_key("esc", "Pressing ESC key to navigate back.")
                time.sleep(.5)
                # ... locate lightning offer, locate quit prompt, maybe return ...
                self.logger.info("No Quit Game or Battle screen detected. Continuing ESC loop.")

        except Exception as e:
            self.logger.error(f"Error in back_to_bastion: {e}", exc_info=True)
```

## Why it matters more than its size suggests

`back_to_bastion()` is not an edge path. It runs:

- Before **every** command, in `AutoRaider.run_command`.
- In `SequenceCommand._cleanup_after_task`, which `run_sequence` calls from a `finally` — so **every v2 failure ends here**, and a v2 failure is the case the whole epic is designed around.

Combine that with reason 1 above and the practical statement is: *when a v2 run fails, the bot enters a loop that cannot be stopped with F2 and does not stop on its own.* The scheduler's thread is then wedged, so every task scheduled afterwards silently does not happen. That is the failure mode most likely to make someone distrust the v2 engine for a reason that has nothing to do with the v2 engine.

Phase 2 already made it less costly without touching it: the crash dump is written **before** cleanup runs, so if a run does hang here, the evidence of *why it failed* survives on disk. The hang itself still has to be killed by hand.

## Scope

Small and deliberately dull. Do not refactor `ClickHandler`.

1. **Cap the loop.** Roughly 30 iterations, then log a warning naming the cap and return. The exact number matters less than its existence; at `~1s` per iteration, 30 is about half a minute.
2. **Check `cancel_flag` at the top of each iteration** and raise `CancellationException`, matching what `click_image` already does.
3. **Do not catch `CancellationException` in `back_to_bastion()`.** Either re-raise it ahead of the bare `except Exception`, or narrow the handler. This is the load-bearing half — a cap alone still leaves F2 broken for up to 30 seconds.
4. **Consider `delete_popup()` as the model.** It already does the right thing: `max_attempts = 5`, a counter, and a warning when the cap is hit. Copy that shape rather than inventing one.

## Out of scope

- Making `press_key` and `_locate_image` check `cancel_flag` generally. That would change behaviour for all eight v1 commands and belongs in its own change, if anywhere. Checking in the `back_to_bastion()` loop is local and sufficient.
- Any other v1 bug found while in here, including `TaskScheduler.remove_schedule` calling `config_handler.remove_setting`, which does not exist (`ConfigHandler` defines `delete_setting`). Note it and move on.
- Changing the confidence threshold, the region, or the ESC timing.

## Acceptance

1. With the game in a state where the quit prompt never appears, `back_to_bastion()` returns within the cap and logs a warning saying it gave up. It does not hang.
2. Pressing **F2** while `back_to_bastion()` is spinning stops it promptly, and the `CancellationException` reaches the caller rather than being logged and dropped.
3. A normal `back_to_bastion()` — quit prompt appears as usual — behaves exactly as it does today. This is the regression that matters, because all eight v1 commands call it before they run.
4. Unit-testable without the game: the loop's exit conditions are decidable against a fake. `tests/fakes.py` already has `FakeClickHandler`; a test for this needs a fake of the *inside* of `ClickHandler`, which does not exist yet and is most of the work. If that turns out to be disproportionate, say so and verify it live instead — but say so explicitly rather than shipping it untested by default.

## Notes for whoever picks this up

The epic's guardrails made `utils/` effectively read-only for Phases 1–3, which is why this was flagged rather than fixed. That reasoning has expired: Phase 4 already touches shared code, and this specific bug is now in the path of every v2 failure. It still deserves its own PR with its own live check, not a line in someone else's.
