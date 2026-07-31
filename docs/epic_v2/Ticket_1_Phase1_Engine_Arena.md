# Phase 1: The Engine & The Arena Staging Ground

**Goal**: Build the YAML parser, the state machine runner, and successfully execute an Arena run using zero hardcoded game logic.

## PR 1.1: Schema Definition & Parsing

**Task**: Create the data structures that map YAML to Python objects.

- Create a YAML file `configs/arena_v2.yaml`.
- Create a Pydantic model `ActionNode` and `Sequence`.
- Write a Python script to load the YAML, validate it via Pydantic, and print the parsed dictionary to the console.

**Example YAML Structure:**
```yaml
# configs/arena_v2.yaml
name: "Arena Classic Battles"
start_node: "click_battle_button"

nodes:
  click_battle_button:
    action_type: "CLICK_IMAGE"
    target: "assets/arena_battle_button.png"
    timeout_seconds: 5
    on_success: "wait_for_loading"
    on_failure: "bastion_fallback"

  wait_for_loading:
    action_type: "WAIT_UNTIL_DISAPPEARS"
    target: "assets/loading_screen.png"
    timeout_seconds: 30
    on_success: "verify_in_combat"
    on_failure: "bastion_fallback"
```

**Example Pydantic Models:**
```python
from pydantic import BaseModel
from typing import Optional, Dict

class ActionNode(BaseModel):
    action_type: str  # e.g., CLICK_IMAGE, WAIT_UNTIL_DISAPPEARS
    target: str 
    timeout_seconds: int = 10
    on_success: Optional[str]
    on_failure: Optional[str]

class SequenceConfig(BaseModel):
    name: str
    start_node: str
    nodes: Dict[str, ActionNode]
```

## PR 1.2: The State Machine Engine ("The Dumb Runner")

**Task**: Build the loop that executes the parsed sequence.

- Create a `SequenceRunner` class.
- It should take a `SequenceConfig` object.
- Write a `run()` method containing a while loop that processes the current node, calls the relevant method in `utils/click_handler.py`, and updates the `current_node` based on the outcome.

**Pseudo-code for the Runner:**
```python
current_node_key = config.start_node

while current_node_key:
    node = config.nodes[current_node_key]
    
    try:
        if node.action_type == "CLICK_IMAGE":
            click_handler.click_image(node.target, timeout=node.timeout_seconds)
            
        elif node.action_type == "WAIT_UNTIL_DISAPPEARS":
            click_handler.wait_until_disappears(node.target, timeout=node.timeout_seconds)
            
        # If no exception was raised, action succeeded!
        current_node_key = node.on_success
        
    except Exception: # (Or a custom TimeoutException)
        # Action failed. Follow the failure path.
        current_node_key = node.on_failure
```

## PR 1.3: The Full Arena Migration

**Task**: Prove the engine works end-to-end.

- Fully flesh out `arena_v2.yaml` to represent a complete Arena battle loop.
- Run it via the `SequenceRunner`.
- **Definition of Done**: The bot successfully enters the arena, fights a battle, returns to the menu, and handles a basic failure without using the old `Modules/arena` python code.
