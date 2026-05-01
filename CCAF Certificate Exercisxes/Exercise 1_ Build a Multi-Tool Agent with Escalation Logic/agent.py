"""
============================================================================
 Exercise 1 — Build a Multi-Tool Agent with Escalation Logic
============================================================================

This single file implements all 5 steps of the exercise. Read top to bottom;
every step is wrapped in a banner comment.

    Step 1 — Define 3-4 MCP tools with detailed differentiating descriptions.
             Two tools (get_customer_info / lookup_order) are deliberately
             similar so we have to disambiguate them by description.
    Step 2 — Implement the agentic loop using the SDK: handle
             stop_reason='tool_use' by executing tools and appending
             results, terminate on stop_reason='end_turn'.
    Step 3 — Structured error responses (errorCategory, isRetryable,
             description). Categories: INVALID_INPUT, TEMPORARY_FAILURE,
             NOT_FOUND.
    Step 4 — Programmatic hook that blocks process_refund when the amount
             exceeds $500 and forces escalation instead.
    Step 5 — Multi-concern user message decomposed into multiple tool calls.

Run with:
    python agent.py                 # runs every demo in order
    python agent.py 5                # runs only demo 5
    python agent.py 1 4              # runs demos 1 and 4

Requires:
    ANTHROPIC_API_KEY environment variable
    `pip install anthropic`
============================================================================
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import anthropic


# ============================================================================
# STEP 1 — MCP tool definitions (4 tools; 2 with similar functionality)
# ============================================================================
# The exam guide explicitly requires us to differentiate two similar tools by
# description. Here, get_customer_info and lookup_order both "look up data
# about a customer's situation" — but they answer different questions:
#
#   get_customer_info  — ACCOUNT-level data: tier, email, total spend
#   lookup_order       — ORDER-level data:   status, amount, items
#
# A vague description like "get info about a customer" would let the model
# call either one for either question. We make the descriptions explicit
# about INPUT (customer_id vs order_id) and OUTPUT (account fields vs order
# fields), and add a "USE THIS WHEN..." line that's the deciding signal.
# ============================================================================

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_customer_info",
        "description": (
            "Retrieve ACCOUNT-LEVEL information about a customer: their "
            "membership tier, contact email, lifetime spend, and signup date. "
            "USE THIS WHEN: the user asks who they are, what tier they're on, "
            "or anything about their account as a whole — NOT about a "
            "specific purchase."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID, e.g. 'CUS-12345' (must start with 'CUS-').",
                },
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "lookup_order",
        "description": (
            "Retrieve ORDER-LEVEL information about a SPECIFIC order: its "
            "status (shipped, processing, delivered), the items, the total "
            "amount, and timestamps. USE THIS WHEN: the user asks about a "
            "specific purchase — NOT about their account in general."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID, e.g. 'ORD-789' (must start with 'ORD-').",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": (
            "Issue a refund against a specific order. The agent may approve "
            "refunds autonomously up to $500. Above that, the request is "
            "blocked by policy and must be escalated to a human."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order to refund."},
                "amount":   {"type": "number", "description": "Refund amount in USD."},
                "reason":   {"type": "string", "description": "Why the refund is being issued."},
            },
            "required": ["order_id", "amount", "reason"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Hand the conversation off to a human agent. Use this when the "
            "user explicitly asks for a human, when a request exceeds your "
            "policy limits (e.g. a refund over $500), or when you can't "
            "make progress with the available tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason":  {"type": "string", "description": "Why we're escalating."},
                "summary": {"type": "string", "description": "Brief context for the human."},
            },
            "required": ["reason", "summary"],
        },
    },
]


# ============================================================================
# STEP 3 — Structured error responses
# ============================================================================
# Every tool error must include errorCategory, isRetryable, and a
# human-readable description. The agent can use isRetryable to decide
# whether to try again or to escalate / give up.
#
# Three categories the exam guide names:
#   INVALID_INPUT      — the call itself was wrong (bad ID format, etc.).
#                        Retrying with the same args won't help. isRetryable=False.
#   TEMPORARY_FAILURE  — transient issue (timeout, rate limit). Retry might
#                        succeed. isRetryable=True.
#   NOT_FOUND          — resource truly doesn't exist. isRetryable=False.
# ============================================================================

def _structured_error(category: str, retryable: bool, message: str) -> dict[str, Any]:
    """Build the standard error payload returned by every failing tool."""
    return {
        "errorCategory": category,
        "isRetryable": retryable,
        "description": message,
    }


# ============================================================================
# Tool IMPLEMENTATIONS (fake but illustrative)
# ============================================================================
# In a real system these would hit a database / payments API. Here they
# return canned responses + the structured errors from Step 3, triggered
# by special "magic" IDs so the demos are deterministic.
# ============================================================================

def _do_get_customer_info(customer_id: str) -> dict[str, Any]:
    if not customer_id.startswith("CUS-"):
        return _structured_error(
            "INVALID_INPUT", False,
            f"customer_id must start with 'CUS-', got {customer_id!r}.",
        )
    if customer_id == "CUS-FLAKY":
        return _structured_error(
            "TEMPORARY_FAILURE", True,
            "Database read timed out. Retry in a moment.",
        )
    if customer_id == "CUS-MISSING":
        return _structured_error(
            "NOT_FOUND", False,
            f"No customer found with id {customer_id}.",
        )
    return {
        "customer_id":  customer_id,
        "name":         "Sample Customer",
        "tier":         "gold",
        "email":        "sample@example.com",
        "total_spend":  4231.50,
        "signup_date":  "2022-04-12",
    }


def _do_lookup_order(order_id: str) -> dict[str, Any]:
    if not order_id.startswith("ORD-"):
        return _structured_error(
            "INVALID_INPUT", False,
            f"order_id must start with 'ORD-', got {order_id!r}.",
        )
    if order_id == "ORD-MISSING":
        return _structured_error(
            "NOT_FOUND", False, f"No order found with id {order_id}.",
        )
    return {
        "order_id":   order_id,
        "status":     "delivered",
        "items":      ["Widget", "Gadget"],
        "amount":     45.20,
        "ordered_at": "2024-08-15",
    }


def _do_process_refund(order_id: str, amount: float, reason: str) -> dict[str, Any]:
    # Note: the $500 limit is enforced by the HOOK (Step 4), not here. By
    # the time this code runs, the hook has already approved the call.
    return {
        "refund_id":  "REF-" + order_id.split("-")[-1],
        "order_id":   order_id,
        "amount":     amount,
        "reason":     reason,
        "status":     "issued",
    }


def _do_escalate_to_human(reason: str, summary: str) -> dict[str, Any]:
    return {
        "ticket_id":  "TKT-9001",
        "queue":      "human-agents",
        "reason":     reason,
        "summary":    summary,
        "status":     "queued",
    }


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call to its handler. Catches uncaught exceptions
    and wraps them in a structured error so the agent never sees a
    bare traceback in tool_result content."""
    try:
        if name == "get_customer_info":  return _do_get_customer_info(**args)
        if name == "lookup_order":       return _do_lookup_order(**args)
        if name == "process_refund":     return _do_process_refund(**args)
        if name == "escalate_to_human":  return _do_escalate_to_human(**args)
        return _structured_error(
            "INVALID_INPUT", False, f"Unknown tool: {name}",
        )
    except TypeError as e:
        # Wrong arguments — the SDK should have validated against the
        # schema, but defense in depth never hurts.
        return _structured_error("INVALID_INPUT", False, str(e))
    except Exception as e:
        return _structured_error("TEMPORARY_FAILURE", True, f"{type(e).__name__}: {e}")


# ============================================================================
# STEP 4 — Programmatic hook for the refund threshold
# ============================================================================
# The hook runs BEFORE every tool call. If it returns None, the call
# proceeds. If it returns a dict, that dict is sent back to the model as
# the tool_result with is_error=True — short-circuiting the actual tool.
#
# Per the exam guide: "when the refund amount exceeds $500, block the
# tool execution and force the agent to call escalate_to_human instead."
# We tell the model exactly what to do next so it doesn't have to guess.
# ============================================================================

AUTONOMOUS_REFUND_LIMIT = 500.0


def pre_tool_hook(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any] | None:
    """Returns None → tool may run. Returns a dict → tool is blocked and the
    dict becomes the tool_result content."""
    if tool_name == "process_refund":
        amount = float(tool_args.get("amount", 0))
        if amount > AUTONOMOUS_REFUND_LIMIT:
            return _structured_error(
                "POLICY_BLOCKED", False,
                f"Refund of ${amount:.2f} exceeds the autonomous limit of "
                f"${AUTONOMOUS_REFUND_LIMIT:.2f}. Do not retry — instead, "
                f"call escalate_to_human with reason='refund_above_limit' "
                f"and a summary of the refund request.",
            )
    return None


# ============================================================================
# STEP 2 — Agentic loop with stop_reason dispatch
# ============================================================================
# Standard pattern:
#   1. Send the conversation to the model with tools=[...].
#   2. If stop_reason == "end_turn"  → done, return.
#   3. If stop_reason == "tool_use"  → for each tool_use block, run the
#                                      hook + tool, append a tool_result.
#   4. Loop.
#   5. Cap iterations to avoid runaway loops.
# ============================================================================

DEFAULT_SYSTEM_PROMPT = """\
You are a customer service agent. You have four tools:

  - get_customer_info   — ACCOUNT-level info (tier, email, spend)
  - lookup_order        — ORDER-level info (status, items, amount)
  - process_refund      — issue a refund (autonomous up to $500)
  - escalate_to_human   — hand off to a human agent

Pick the most specific tool for each user concern. When a user message has
multiple concerns, address each one with the appropriate tool call(s) —
issuing them in the same response is fine. If a tool returns an error,
inspect errorCategory and isRetryable: retry only if isRetryable=True;
otherwise, explain the situation to the user or escalate.
"""

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
MAX_ITERATIONS = 10


def run_agent(user_message: str, *, verbose: bool = True) -> list[dict[str, Any]]:
    """Run the agent loop until end_turn or max iterations.

    Returns the full message history so callers (or demos) can inspect
    every assistant turn, every tool call, and every result.
    """
    client = anthropic.Anthropic()
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_message},
    ]

    if verbose:
        print(f"\n┃ USER: {user_message}\n")

    for iteration in range(1, MAX_ITERATIONS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=DEFAULT_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        # Append the assistant turn so the next API call has full context.
        messages.append({"role": "assistant", "content": response.content})

        # Surface assistant text to the user in real time.
        for block in response.content:
            if getattr(block, "type", None) == "text" and verbose:
                print(f"┃ ASSISTANT: {block.text}\n")

        # ── stop_reason dispatch ──────────────────────────────────────
        if response.stop_reason == "end_turn":
            if verbose:
                print(f"  (loop ended after {iteration} iteration(s); stop_reason=end_turn)")
            break

        if response.stop_reason != "tool_use":
            # max_tokens, stop_sequence, etc. — bail defensively.
            if verbose:
                print(f"  (loop ended unexpectedly; stop_reason={response.stop_reason})")
            break

        # ── Process every tool_use block in this assistant turn ──────
        # Multiple tool_use blocks in ONE response = parallel tool calls.
        # We handle them all and return a SINGLE user message with all
        # the tool_result blocks. (Step 5 — multi-concern decomposition
        # naturally lands here.)
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_name = block.name
            tool_args = dict(block.input or {})
            if verbose:
                print(f"  → tool_use: {tool_name}({tool_args})")

            # ── Hook check (Step 4) ──────────────────────────────────
            blocked = pre_tool_hook(tool_name, tool_args)
            if blocked is not None:
                if verbose:
                    print(f"    ⛔ blocked by hook: {blocked['description'][:80]}…")
                tool_results.append({
                    "type":         "tool_result",
                    "tool_use_id":  block.id,
                    "content":      json.dumps(blocked),
                    "is_error":     True,
                })
                continue

            # ── Actual execution ─────────────────────────────────────
            result = execute_tool(tool_name, tool_args)
            is_error = isinstance(result, dict) and "errorCategory" in result
            if verbose:
                if is_error:
                    print(f"    ✗ {result['errorCategory']} (retryable={result['isRetryable']})")
                else:
                    print(f"    ✓ ok")

            tool_results.append({
                "type":         "tool_result",
                "tool_use_id":  block.id,
                "content":      json.dumps(result),
                "is_error":     is_error,
            })

        messages.append({"role": "user", "content": tool_results})

    else:
        if verbose:
            print(f"  (loop hit MAX_ITERATIONS={MAX_ITERATIONS} without ending)")

    return messages


# ============================================================================
# DEMOS — one per concept the exercise calls out
# ============================================================================

def demo_1_tool_selection():
    """Step 1 — model picks the RIGHT one of the two similar tools."""
    print("\n" + "=" * 70)
    print(" Demo 1 — Tool selection (Step 1)")
    print(" Question is about an ACCOUNT → model should pick get_customer_info")
    print("=" * 70)
    run_agent("What tier is customer CUS-12345?")


def demo_2_invalid_input():
    """Step 3 — INVALID_INPUT → model does NOT retry."""
    print("\n" + "=" * 70)
    print(" Demo 2 — INVALID_INPUT error (Step 3)")
    print(" Bad customer_id format. Tool returns isRetryable=False;")
    print(" model should explain rather than retry.")
    print("=" * 70)
    run_agent("Look up customer 99999.")


def demo_3_temporary_failure():
    """Step 3 — TEMPORARY_FAILURE → model retries."""
    print("\n" + "=" * 70)
    print(" Demo 3 — TEMPORARY_FAILURE error (Step 3)")
    print(" CUS-FLAKY returns a transient error. Model should retry.")
    print(" (The fake handler always returns the error, so retry will")
    print(" fail again — but you'll see the agent attempt the retry.)")
    print("=" * 70)
    run_agent("Look up customer CUS-FLAKY.")


def demo_4_not_found():
    """Step 3 — NOT_FOUND → model reports gracefully."""
    print("\n" + "=" * 70)
    print(" Demo 4 — NOT_FOUND error (Step 3)")
    print(" CUS-MISSING doesn't exist. Model should explain, not retry.")
    print("=" * 70)
    run_agent("Look up customer CUS-MISSING.")


def demo_5_refund_under_limit():
    """Step 4 — refund < $500: hook lets it through."""
    print("\n" + "=" * 70)
    print(" Demo 5 — Refund under limit (Step 4)")
    print(" $50 refund is below the $500 threshold; hook does nothing,")
    print(" process_refund executes normally.")
    print("=" * 70)
    run_agent("Please refund $50 on order ORD-789 — wrong color shipped.")


def demo_6_refund_over_limit():
    """Step 4 — refund > $500: hook blocks, model escalates."""
    print("\n" + "=" * 70)
    print(" Demo 6 — Refund OVER limit (Step 4)")
    print(" $750 exceeds the $500 limit. Hook blocks the call and tells")
    print(" the model to escalate. Watch the trace: process_refund is")
    print(" attempted → blocked → escalate_to_human is called next.")
    print("=" * 70)
    run_agent("Please refund $750 on order ORD-789 — defective merchandise.")


def demo_7_multi_concern():
    """Step 5 — one message asking 3 things → multiple tool calls."""
    print("\n" + "=" * 70)
    print(" Demo 7 — Multi-concern message (Step 5)")
    print(" One user message contains THREE separate concerns. The agent")
    print(" should decompose into multiple tool calls (likely all in the")
    print(" same response — watch for 'tool_use' lines bunched together).")
    print("=" * 70)
    run_agent(
        "Hi! Three things: (1) check my account CUS-12345, "
        "(2) look up my order ORD-789, and "
        "(3) process a $30 refund on that order — wrong size."
    )


DEMOS: dict[str, callable] = {
    "1": demo_1_tool_selection,
    "2": demo_2_invalid_input,
    "3": demo_3_temporary_failure,
    "4": demo_4_not_found,
    "5": demo_5_refund_under_limit,
    "6": demo_6_refund_over_limit,
    "7": demo_7_multi_concern,
}


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ERROR: set ANTHROPIC_API_KEY first (see HOW_TO_RUN.md).")

    args = sys.argv[1:]
    if args:
        for arg in args:
            if arg not in DEMOS:
                sys.exit(f"Unknown demo {arg!r}. Choose from: {list(DEMOS)}")
            DEMOS[arg]()
    else:
        for fn in DEMOS.values():
            fn()


if __name__ == "__main__":
    main()
