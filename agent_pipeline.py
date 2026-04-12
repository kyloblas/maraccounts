#!/usr/bin/env python3
"""3-agent pipeline demo for accrual calculation.

Pipeline:
1) Agent A writes Python code.
2) Agent B reviews it and returns PASS/FAIL.
3) Guardrails run deterministic checks before execution.
4) Sandboxed exec runs calculate_accruals(TEST_DATA).
"""

from __future__ import annotations

import argparse
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Any

import anthropic

MODEL_WRITER = "claude-haiku-4-5-20251001"
MODEL_REVIEWER = "claude-haiku-4-5-20251001"
TARGET_PERIOD = "2024-03"
EXPECTED_TOTAL = 25_200.0
FORBIDDEN_PATTERNS = (
    "import os",
    "from os",
    "import subprocess",
    "from subprocess",
    "open(",
    "eval(",
)

TEST_DATA = [
    {"vendor": "Office Supplies Ltd", "amount": 1200.0, "period": "2024-03"},
    {"vendor": "Cloud Services Inc", "amount": 8400.0, "period": "2024-03"},
    {"vendor": "Consulting Co", "amount": 15600.0, "period": "2024-03"},
    {"vendor": "Software Vendor", "amount": 22000.0, "period": "2024-02"},
    {"vendor": "Hardware Depot", "amount": 5500.0, "period": "2024-02"},
    {"vendor": "Legal Services", "amount": 9800.0, "period": "2024-01"},
]

SAFE_PROMPT = textwrap.dedent(
    f"""
    Write ONLY Python code for a function named calculate_accruals(rows).

    Requirements:
    - rows is a list of dicts with keys: vendor, amount, period.
    - Sum ONLY rows where period == "{TARGET_PERIOD}".
    - Return a dict with keys: total_accrual (float), rows_counted (int).
    - Do not import any modules.
    - Output only valid Python code (no markdown fences, no explanation).
    """
).strip()

FAIL_PROMPT = textwrap.dedent(
    """
    Write ONLY Python code for a function named calculate_accruals(rows).

    Requirements:
    - rows is a list of dicts with keys: vendor, amount, period.
    - Sum all rows regardless of period.
    - Return a dict with keys: total_accrual (float), rows_counted (int).
    - Do not import any modules.
    - Output only valid Python code (no markdown fences, no explanation).
    """
).strip()

REVIEW_PROMPT = textwrap.dedent(
    """
    You are Agent B reviewing generated Python code.

    Check:
    1) Security issues (dangerous imports, open/eval usage, command execution).
    2) Logic quality for accrual calculations.

    Respond with exactly:
    - PASS: <brief reason>
    or
    - FAIL: <brief reason>

    Code to review:
    {code}
    """
).strip()


@dataclass
class GuardrailResult:
    passed: bool
    reason: str


def call_agent(client: anthropic.Anthropic, model: str, prompt: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=600,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    return "\n".join(text_parts).strip()


def parse_verdict(review_text: str) -> tuple[str, str]:
    first_line = review_text.strip().splitlines()[0] if review_text.strip() else ""
    if first_line.upper().startswith("PASS:"):
        return "PASS", first_line[5:].strip()
    if first_line.upper().startswith("FAIL:"):
        return "FAIL", first_line[5:].strip()
    return "FAIL", "Reviewer output malformed"


def run_guardrails(code: str) -> GuardrailResult:
    lowered = code.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in lowered:
            return GuardrailResult(False, f"Forbidden pattern found: {pattern}")

    if not re.search(rf"period\s*['\"]?\]?\s*==\s*['\"]{TARGET_PERIOD}['\"]", code):
        return GuardrailResult(False, f"Missing required period filter for {TARGET_PERIOD}")

    return GuardrailResult(True, "Passed static guardrails")


def execute_sandboxed(code: str) -> dict[str, Any]:
    safe_builtins = {
        "sum": sum,
        "len": len,
        "min": min,
        "max": max,
        "float": float,
        "int": int,
        "dict": dict,
        "list": list,
        "enumerate": enumerate,
        "range": range,
    }
    sandbox_globals: dict[str, Any] = {"__builtins__": safe_builtins}
    sandbox_locals: dict[str, Any] = {}

    exec(code, sandbox_globals, sandbox_locals)

    fn = sandbox_locals.get("calculate_accruals") or sandbox_globals.get("calculate_accruals")
    if not callable(fn):
        raise ValueError("Generated code did not define calculate_accruals(rows)")

    result = fn(TEST_DATA)
    if not isinstance(result, dict):
        raise ValueError("calculate_accruals(rows) must return a dict")

    return result


def format_money(value: float) -> str:
    return f"£{value:,.2f}".rjust(11)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 3-agent accrual calculator pipeline")
    parser.add_argument("--fail", action="store_true", help="Prompt Agent A to omit period filtering")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic()
    writer_prompt = FAIL_PROMPT if args.fail else SAFE_PROMPT

    generated_code = call_agent(client, MODEL_WRITER, writer_prompt)

    review_text = call_agent(client, MODEL_REVIEWER, REVIEW_PROMPT.format(code=generated_code))
    verdict, verdict_reason = parse_verdict(review_text)
    if verdict == "FAIL":
        print(f"blocked by Agent B: {verdict_reason}")
        return 1

    guardrails = run_guardrails(generated_code)
    if not guardrails.passed:
        print(f"blocked by guardrails: {guardrails.reason}")
        return 1

    result = execute_sandboxed(generated_code)
    total = float(result.get("total_accrual", 0.0))
    rows_counted = int(result.get("rows_counted", 0))
    variance = total - EXPECTED_TOTAL

    print(f"total accrual :  {format_money(total)}")
    print(f"rows counted  : {rows_counted}")
    print(f"expected total:  {format_money(EXPECTED_TOTAL)}")
    print(f"variance      :  {format_money(variance)}")
    print()

    if abs(variance) < 0.005:
        print("=> CORRECT — period filter worked")
        return 0

    print("=> WRONG — missing or broken period filter")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
