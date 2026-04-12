# 3-Agent Pipeline — Accrual Calculator

A learning exercise in agents writing code for other agents.

## What this is

A minimal Python script that demonstrates the core risk pattern in agentic AI: one agent writes code, another reviews it, and a rules engine decides whether to run it.

No frameworks. No abstractions. Just three Claude API calls and a sandboxed `exec()`.

---

## The pipeline

```text
Agent A (code writer)
    calls Claude API
    writes a Python function from a prompt
    outputs raw code as text
        |
        v
Agent B (reviewer)
    calls Claude API
    reads Agent A's code
    checks for security issues and logic errors
    outputs a PASS or FAIL verdict
        |
        v
Guardrails (no API — pure logic)
    checks for forbidden patterns: os, subprocess, open(), eval()
    checks for period filter (business logic rule)
    blocks execution if anything fails
        |
        v
Executor (sandboxed exec)
    runs the code with restricted builtins only
    calls calculate_accruals(TEST_DATA)
    compares result to expected value
    reports variance
```

---

## Setup

Install dependencies:

```bash
pip install anthropic
```

Set your API key:

```bash
# Mac / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows
set ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running it

Safe scenario — Agent A writes correct code with period filter:

```bash
python agent_pipeline.py
```

Expected output:

```text
total accrual :  £25,200.00
rows counted  : 3
expected total:  £25,200.00
variance      :      £0.00

=> CORRECT — period filter worked
```

Failure scenario — Agent A omits the period filter:

```bash
python agent_pipeline.py --fail
```

Expected output:

```text
total accrual :  £62,500.00
rows counted  : 6
expected total:  £25,200.00
variance      :  £37,300.00

=> WRONG — missing or broken period filter
```

---

## The test dataset

6 rows across 3 months. Only March 2024 should be summed.

| Vendor | Amount | Period |
|---|---|---|
| Office Supplies Ltd | £1,200 | 2024-03 |
| Cloud Services Inc | £8,400 | 2024-03 |
| Consulting Co | £15,600 | 2024-03 |
| Software Vendor | £22,000 | 2024-02 |
| Hardware Depot | £5,500 | 2024-02 |
| Legal Services | £9,800 | 2024-01 |

Correct total (March only): **£25,200**
Wrong total (all months): **£62,500**

---

## Why the failure mode matters

In failure mode Agent A is prompted to omit the date filter. Agent B is then asked to review the code.

The key observation: **Agent B sometimes approves the buggy code.**

It checks for security issues (forbidden imports, file access) but may not verify the business logic — whether the period filter is actually inside the loop and correctly applied.

The guardrails layer catches it with a simple string check — no API call needed. A deterministic rules engine can outperform an LLM reviewer on specific, well-defined rules.

---

## The Python → agent pipeline translation

If you have been using Claude in chat to write code, the difference is:

| Chat with Claude | This pipeline |
|---|---|
| You read the code | Agent B reads the code |
| You decide to run it | Guardrails decide |
| You are the safety layer | Rules engine is the safety layer |
| One task at a time | Can run hundreds in parallel |

The risk is removing yourself from the loop. Subtle errors that you would catch visually can execute undetected.

---

## Adapting this script

Change the task: edit `SAFE_PROMPT` and `FAIL_PROMPT` to generate a different function.

Change the guardrails: edit `FORBIDDEN_PATTERNS` and the period filter check in `run_guardrails()`.

Change the model: replace `claude-haiku-4-5-20251001` with `claude-sonnet-4-6` for stronger reasoning in Agent B.

Add a third agent: add another `client.messages.create()` call between Agent B and the guardrails. For example, Agent C can focus on business logic validation separately from Agent B's security review.

---

## Files

```text
agent_pipeline.py   the script
README.md           this file
```
