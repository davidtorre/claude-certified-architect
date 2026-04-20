#!/bin/bash
# Stop hook: check if all phases are complete

STATE_FILE=".jumpstarter-state.json"

# If no state file, allow stop
if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

# Read state values
CURRENT=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['current_phase'])")
TOTAL=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['total_phases'])")
ITERATION=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['iteration_count'])")
MAX_ITER=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['max_iterations'])")

# Safety: always stop if max iterations reached
if [ "$ITERATION" -ge "$MAX_ITER" ]; then
  echo "Max iterations reached ($ITERATION/$MAX_ITER). Allowing stop."
  exit 0
fi

# If more phases remain, keep going
if [ "$CURRENT" -lt "$TOTAL" ]; then
  echo "Phase $CURRENT of $TOTAL complete. Continue to next phase." >&2
  exit 1
fi

# All phases complete
echo "All $TOTAL phases complete!"
exit 0