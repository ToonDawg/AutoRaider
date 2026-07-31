# Phase 2: Telemetry & Crash Dumps

**Goal**: When the bot gets lost, it shouldn't just crash. It should take a picture of what went wrong so we can fix it later.

## PR 2.1: The Crash Dump Generator

- Modify the `SequenceRunner`. If a node fails, and its `on_failure` is set to a critical error state (or is missing), catch the exception.
- Use PyAutoGUI or Pillow to take a full-screen screenshot.
- Save the image to `logs/dumps/YYYY-MM-DD_HH-MM-SS.png`.
- Save a companion file `logs/dumps/YYYY-MM-DD_HH-MM-SS.json` containing the failed node's name, action, and expected target.

## PR 2.2: Global Bastion Recovery

- Ensure that after generating a crash dump, the runner automatically triggers your existing `back_to_bastion()` recovery method to reset the game to the home screen so the next scheduled sequence can start cleanly.
