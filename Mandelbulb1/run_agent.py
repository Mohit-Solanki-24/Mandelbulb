"""
run_agent.py
------------
Responsibility:
    Expose the single public entry point of the AI agent:

        run_agent(question: str) -> str

    This module is the ORCHESTRATION layer. It wires the three inner layers
    together in a fixed, linear pipeline:

        question (str)
            │
            ▼
        planner.plan(question)
            │   returns: list[dict]  — ordered tool-call steps
            ▼
        dispatcher.execute_plan(plan)
            │   returns: list[dict]  — per-step execution results
            ▼
        response_builder.build_response(results)
            │   returns: str         — customer-friendly response
            ▼
        caller

    Design principles:
      - Each layer has a single, well-defined responsibility (see its own module).
      - This file contains NO business logic — only composition and error handling.
      - Unexpected exceptions at any layer are caught here and converted to a
        safe, user-facing message; stack traces are NEVER exposed to callers.
      - Optional structured logging is included so failures can be diagnosed
        in production without leaking details to end users.
"""

import logging
import traceback
from typing import Optional

from planner import plan
from dispatcher import execute_plan
from response_builder import build_response

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
# Uses the standard Python logging hierarchy. In production, configure
# handlers (e.g. file handler, cloud sink) at the application level.
# By default this logger is silent unless a handler is attached by the caller.

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback message shown to the customer when an unrecoverable error occurs.
# It is intentionally vague — no internal details are exposed.
# ---------------------------------------------------------------------------
_FALLBACK_ERROR_MESSAGE: str = (
    "⚠️  I'm sorry, I encountered an unexpected problem while processing your "
    "request.\n\n"
    "Please try again in a moment. If the issue persists, our support team is "
    "happy to help."
)

# Shown when the caller passes a blank or non-string question.
_EMPTY_QUESTION_MESSAGE: str = (
    "🤔  It looks like your message was empty. "
    "Could you please rephrase your question?\n\n"
    "For example:\n"
    "  • \"Where is my order ORD-10021?\"\n"
    "  • \"Find me wireless headphones\"\n"
    "  • \"Tell me about the Sony WH-1000XM5\""
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(question: str) -> str:
    """
    Process a customer question and return a customer-friendly response string.

    Orchestrates the full agent pipeline:
        planner  →  dispatcher  →  response_builder

    Args:
        question (str): The raw customer question as entered in the chat or
                        API request. May be any natural-language string.

    Returns:
        str: A polished, human-readable response. This function is guaranteed
             to always return a non-empty string — it NEVER raises an exception
             and NEVER returns None.

    Guarantees:
        - Never raises any exception (all paths are caught).
        - Never exposes stack traces, internal error messages, or raw data
          to the caller.
        - Never returns an empty string.
        - Logs all unexpected failures at ERROR level with a full traceback
          for internal diagnostics (invisible to end users).

    Examples:
        >>> run_agent("Where is my order ORD-10021?")
        '📦  Order ORD-10021\\n...'

        >>> run_agent("Find me wireless headphones under $300")
        '🔍  Found 3 products...'

        >>> run_agent("Show me cheaper alternatives to the Sony WH-1000XM5")
        '🔎  Looking for alternatives...'

        >>> run_agent("")
        '🤔  It looks like your message was empty...'

        >>> run_agent("What is the meaning of life?")
        '🤔  I\\'m sorry, I wasn\\'t able to understand your request...'
    """
    # ------------------------------------------------------------------
    # Guard: reject blank or non-string input immediately
    # ------------------------------------------------------------------
    if not isinstance(question, str) or not question.strip():
        logger.debug("run_agent received an empty or non-string question.")
        return _EMPTY_QUESTION_MESSAGE

    sanitised_question = question.strip()
    logger.debug("run_agent received question: %r", sanitised_question)

    # ------------------------------------------------------------------
    # Step 1: Planning
    # Analyse the question and produce an ordered list of tool-call steps.
    # ------------------------------------------------------------------
    try:
        execution_plan = plan(sanitised_question)
        logger.debug(
            "Planner produced %d step(s): %s",
            len(execution_plan),
            [s.get("tool") for s in execution_plan],
        )
    except Exception:
        logger.error(
            "Unexpected error in planner.plan() for question %r:\n%s",
            sanitised_question,
            traceback.format_exc(),
        )
        return _FALLBACK_ERROR_MESSAGE

    # ------------------------------------------------------------------
    # Step 2: Dispatching
    # Execute each step in the plan and collect structured results.
    # ------------------------------------------------------------------
    try:
        results = execute_plan(execution_plan)
        logger.debug(
            "Dispatcher completed %d step(s). Successes: %d / %d",
            len(results),
            sum(1 for r in results if r.get("success")),
            len(results),
        )
    except Exception:
        logger.error(
            "Unexpected error in dispatcher.execute_plan() for question %r:\n%s",
            sanitised_question,
            traceback.format_exc(),
        )
        return _FALLBACK_ERROR_MESSAGE

    # ------------------------------------------------------------------
    # Step 3: Response Building
    # Convert raw results into a customer-friendly string.
    # ------------------------------------------------------------------
    try:
        response = build_response(results)
        logger.debug(
            "Response built successfully (%d characters).",
            len(response),
        )
    except Exception:
        logger.error(
            "Unexpected error in response_builder.build_response() "
            "for question %r:\n%s",
            sanitised_question,
            traceback.format_exc(),
        )
        return _FALLBACK_ERROR_MESSAGE

    # ------------------------------------------------------------------
    # Final guard: ensure we never return an empty string
    # ------------------------------------------------------------------
    return response if response and response.strip() else _FALLBACK_ERROR_MESSAGE


# ---------------------------------------------------------------------------
# Script entry point (manual smoke-test convenience)
# ---------------------------------------------------------------------------
# Running `python run_agent.py` directly launches an interactive REPL loop
# so the agent can be tested without any test framework or UI.

if __name__ == "__main__":
    import sys

    # Configure a minimal console logger for interactive use only
    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    print("=" * 60)
    print("  AI Store Agent — Interactive Mode")
    print("  Type your question and press Enter.")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C or piped input ending gracefully
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        print()
        print("Agent:", run_agent(user_input))
        print()
