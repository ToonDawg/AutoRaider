# Phase 3: Human-In-The-Loop (HITL) Authoring UI

**Goal**: Build a standalone tool to fix failed configs visually.

## PR 3.1: The Crash Viewer UI

- Create a new independent `CustomTkinter` window.
- It should load a list of recent crash dumps from `logs/dumps/`.
- When a dump is selected, display the full-resolution screenshot in the UI, along with the JSON context (e.g., "Failed looking for assets/victory.png at node check_victory_screen").

## PR 3.2: Visual Bounding Box & Cropping

- Implement mouse drag-and-drop on the displayed screenshot to draw a rectangle (bounding box).
- Add a "Save Target" button. When clicked, crop the image inside the bounding box and save it to `assets/dynamic/{uuid}.png`.

## PR 3.3: Config Mutation (`ruamel.yaml`)

- Once the new image is cropped, programmatically open the original YAML file (e.g., `arena_v2.yaml`) using `ruamel.yaml`.
- Find the exact node that failed (using the context JSON).
- Update its `target` field with the new path `assets/dynamic/{uuid}.png`.
- Save the YAML file (preserving all comments).
