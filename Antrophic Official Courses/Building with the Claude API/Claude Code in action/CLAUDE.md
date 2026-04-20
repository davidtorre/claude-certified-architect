# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project layout

The actual Python project lives in `app_starter/`. Run all `uv` / `pytest` commands from that directory. A zipped copy (`app_starter.zip`) is the pristine course starter — do not edit it.

## Commands

All commands are run from `app_starter/` with `uv` (Python >=3.10):

```bash
uv venv && source .venv/bin/activate   # create & activate venv
uv pip install -e .                    # install package in editable mode
uv run main.py                         # start the MCP server (stdio)
uv run pytest                          # run all tests
uv run pytest tests/test_document.py::TestBinaryDocumentToMarkdown::test_binary_document_to_markdown_with_pdf   # single test
```

## Architecture

This is an **MCP (Model Context Protocol) server** built on `FastMCP` that exposes document/utility tools to an AI assistant over stdio.

- `main.py` — instantiates `FastMCP("docs")`, registers each tool via `mcp.tool()(fn)`, and calls `mcp.run()`. Adding a new tool means importing the function and adding one registration line here.
- `tools/` — plain Python functions, one module per tool family (`math.py`, `document.py`). Functions use `pydantic.Field(description=...)` on parameters so the MCP schema carries rich descriptions to the client.
- `tools/document.py` uses `markitdown` (with `[docx,pdf]` extras) to convert binary document bytes → markdown via `BytesIO` + `StreamInfo(extension=...)`.
- `tests/` — pytest tests. Binary fixtures live in `tests/fixtures/` (e.g. `mcp_docs.docx`, `mcp_docs.pdf`) and are referenced with paths relative to `__file__`.

## Tool-authoring conventions (from README)

When adding a tool, the docstring is the LLM-visible spec. It should contain:

1. A one-line summary.
2. A detailed explanation.
3. A "When to use" section (and when not to).
4. Usage examples with expected input/output.

Every parameter gets a `pydantic.Field(description=...)`. Register the function in `main.py` with `mcp.tool()(fn)`.
