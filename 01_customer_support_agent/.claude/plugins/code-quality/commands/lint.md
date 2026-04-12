# /lint Command

When the user runs /lint, perform these steps:

1. Detect the project type by checking for:
   - package.json (Node.js) -> run `npx eslint .`
   - pyproject.toml or setup.py (Python) -> run `ruff check .`
   - Cargo.toml (Rust) -> run `cargo clippy`
   - go.mod (Go) -> run `golangci-lint run`

2. Parse the linter output and categorize issues:
   - **Errors**: Must be fixed before merge
   - **Warnings**: Should be addressed
   - **Style**: Nice to have

3. Present a summary table with file, line, severity,
   and description for each issue.

4. Offer to auto-fix what can be auto-fixed.