#!/bin/bash
# Check formatting after each edit
FILE_PATH="$1"

if [[ "$FILE_PATH" == *.py ]]; then
  ruff format --check "$FILE_PATH" 2>/dev/null
elif [[ "$FILE_PATH" == *.ts ]] || [[ "$FILE_PATH" == *.tsx ]]; then
  npx prettier --check "$FILE_PATH" 2>/dev/null
fi