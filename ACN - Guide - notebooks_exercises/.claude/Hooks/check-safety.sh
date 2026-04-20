#!/bin/bash
# Block dangerous delete operations
TOOL_INPUT="$1"

if echo "$TOOL_INPUT" | grep -qE 'rm\s+(-rf?\s+)?(/prod|/production|/live)'; then
  echo "BLOCKED: Cannot delete production files" >&2
  exit 1
fi

exit 0