#!/bin/bash
# Don't let Claude stop until tests pass
npm test --silent 2>/dev/null
if [ $? -ne 0 ]; then
  echo "Tests are still failing. Keep working." >&2
  exit 1
fi

exit 0