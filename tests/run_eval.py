"""
tests/run_eval.py — Evaluation harness for the SmartToyStore Support Assistant.

Reads tests/golden_test_suite.csv (60 labelled cases).
Runs each through the same pipeline the app uses.
Writes tests/results.csv.
Prints: containment, false-answer rate, placeholder leak count,
        false-escalation rate, Level 3 recall/precision, 3x3 confusion matrix.

TC-50 requires a multi-turn session: "Hi" → "4" → "4.2" → safety report.

Run as a STANDALONE script (not wired into the app):
  python tests/run_eval.py
"""

from __future__ import annotations
import csv
import sys
import os
import uuid
from pathlib import Path
from collections import defaultdict

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Validate API key
if not os.getenv("LLM_API_KEY"):
    print("ERROR: LLM_API_KEY not set. Fill in .env before running eval.")
    sys.exit(1)

# Initialise DB and index
from pipeline.db import init_db
from pipeline.indexer import load_default_kb
from pipeline.retriever import build_index
from pipeline.responder import process_turn

init_db()
print("[eval] Building vector index…")
chunks = load_default_kb()
build_index(chunks)
print(f"[eval] {len(chunks)} chunks indexed.\n")

TEST_CSV = ROOT / "tests" / "golden_test_suite.csv"
RESULTS_CSV = ROOT / "tests" / "results.csv"

# --------------------------------------------------------------------------
# Load test cases
# --------------------------------------------------------------------------

def load_test_cases() -> list[dict]:
    cases = []
    with open(TEST_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
    return cases


# --------------------------------------------------------------------------
# Run a single test case
# --------------------------------------------------------------------------

def run_case(case: dict, tc50_session: str | None = None) -> dict:
    test_id = case["test_id"]
    query = case["query"]
    expected_action = case.get("expected_action", "").strip().upper()
    expected_level_str = case.get("expected_level", "").strip()
    expected_level = int(expected_level_str) if expected_level_str.isdigit() else None

    # TC-50 is multi-turn: special handling
    if test_id == "TC-50":
        sid = tc50_session or str(uuid.uuid4())
        # Turn 1: "Hi"
        process_turn("Hi", sid, channel="web")
        # Turn 2: "4"
        process_turn("4", sid, channel="web")
        # Turn 3: "4.2"
        process_turn("4.2", sid, channel="web")
        # Turn 4: safety report
        result = process_turn(query, sid, channel="web")
        session_id = sid
    else:
        session_id = str(uuid.uuid4())
        result = process_turn(query, session_id, channel="web")

    assigned_action = result.get("action", "UNKNOWN").upper()
    # Infer level from action
    if assigned_action in ("SAFETY_HANDOFF",):
        assigned_level = 3
    elif assigned_action == "ESCALATE":
        assigned_level = 2
    else:
        assigned_level = 1

    return {
        "test_id": test_id,
        "query": query,
        "expected_action": expected_action,
        "expected_level": expected_level,
        "assigned_action": assigned_action,
        "assigned_level": assigned_level,
        "reply_snippet": result.get("text", "")[:120].replace("\n", " "),
        "ticket_id": result.get("ticket_id", ""),
    }


# --------------------------------------------------------------------------
# Metrics computation
# --------------------------------------------------------------------------

def compute_metrics(results: list[dict]) -> None:
    total = len(results)
    if total == 0:
        print("No results.")
        return

    # Containment: actions that did NOT produce an escalation email
    contained = sum(1 for r in results if r["assigned_action"] in
                    ("ANSWER", "CONSOLE", "CLARIFY", "MENU", "DECLINE_SCOPE"))

    # False-answer rate: assigned ANSWER but expected ESCALATE or SAFETY_HANDOFF
    false_answers = sum(1 for r in results
                        if r["assigned_action"] == "ANSWER"
                        and r["expected_action"] in ("ESCALATE", "SAFETY_HANDOFF"))

    # Placeholder leak: reply contains a bracketed pattern
    import re
    placeholder_re = re.compile(r"\[[^\]]{3,}\]")
    placeholder_leaks = [r for r in results if placeholder_re.search(r["reply_snippet"])]

    # Cases with expected_level set
    levelled = [r for r in results if r["expected_level"] is not None]

    # False escalation: assigned level > expected level (when expected is 1 or 2)
    false_escalations = sum(1 for r in levelled
                            if r["assigned_level"] > (r["expected_level"] or 0)
                            and (r["expected_level"] or 0) < 3)

    # Level 3 recall/precision
    expected_l3 = [r for r in levelled if r["expected_level"] == 3]
    assigned_l3 = [r for r in levelled if r["assigned_level"] == 3]
    true_positive_l3 = [r for r in levelled if r["expected_level"] == 3 and r["assigned_level"] == 3]

    recall_l3 = len(true_positive_l3) / len(expected_l3) if expected_l3 else float("nan")
    precision_l3 = len(true_positive_l3) / len(assigned_l3) if assigned_l3 else float("nan")

    # Confusion matrix (3x3): rows = expected level, cols = assigned level
    matrix = defaultdict(lambda: defaultdict(int))
    for r in levelled:
        exp = r["expected_level"] or 1
        asgn = r["assigned_level"]
        matrix[exp][asgn] += 1

    # Critical cells: assigned L1 or L2 when expected L3
    assigned_l1_expected_l3 = sum(1 for r in levelled
                                   if r["expected_level"] == 3 and r["assigned_level"] == 1)
    assigned_l2_expected_l3 = sum(1 for r in levelled
                                   if r["expected_level"] == 3 and r["assigned_level"] == 2)

    # Print
    print("=" * 60)
    print("  SMART TOY STORE — EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Total cases:          {total}")
    print(f"  Containment rate:     {contained}/{total} = {contained/total*100:.1f}%")
    print(f"  False-answer rate:    {false_answers}/{total} = {false_answers/total*100:.1f}%")
    print(f"  Placeholder leaks:    {len(placeholder_leaks)}")
    print(f"  False escalations:    {false_escalations}")
    print()
    if expected_l3:
        print(f"  Level 3 recall:       {recall_l3:.2f}")
        print(f"  Level 3 precision:    {precision_l3:.2f}")
    print()
    print(f"  ⚠  Assigned L1, Expected L3:  {assigned_l1_expected_l3}  (must be 0)")
    print(f"  ⚠  Assigned L2, Expected L3:  {assigned_l2_expected_l3}  (must be 0)")
    print()

    # Confusion matrix
    print("  3×3 CONFUSION MATRIX (rows=expected, cols=assigned)")
    print(f"  {'':12} {'L1':>6} {'L2':>6} {'L3':>6}")
    for exp in [1, 2, 3]:
        row_data = [matrix[exp][asgn] for asgn in [1, 2, 3]]
        total_row = sum(row_data)
        if total_row == 0:
            continue
        print(f"  Expected L{exp}  {row_data[0]:>6} {row_data[1]:>6} {row_data[2]:>6}")

    print("=" * 60)

    if placeholder_leaks:
        print("\n  PLACEHOLDER LEAKS:")
        for r in placeholder_leaks:
            print(f"    [{r['test_id']}] {r['reply_snippet'][:80]}")

    if assigned_l1_expected_l3 > 0 or assigned_l2_expected_l3 > 0:
        print("\n  ⚠  CRITICAL FAILURES — L3 misses:")
        for r in levelled:
            if r["expected_level"] == 3 and r["assigned_level"] < 3:
                print(f"    [{r['test_id']}] assigned=L{r['assigned_level']} | {r['query']}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    cases = load_test_cases()
    print(f"[eval] Running {len(cases)} test cases…\n")

    results = []
    tc50_session = str(uuid.uuid4())

    for i, case in enumerate(cases, 1):
        try:
            result = run_case(case, tc50_session=tc50_session if case["test_id"] == "TC-50" else None)
            results.append(result)
            status = "✓" if (
                not result["expected_level"] or
                result["assigned_level"] == result["expected_level"]
            ) else "✗"
            print(f"  [{i:02d}/{len(cases)}] {result['test_id']} {status}  "
                  f"action={result['assigned_action']} level=L{result['assigned_level']}")
        except Exception as e:
            print(f"  [{i:02d}/{len(cases)}] {case.get('test_id','?')} ERROR: {e}")
            results.append({
                "test_id": case.get("test_id"),
                "query": case.get("query"),
                "expected_action": case.get("expected_action"),
                "expected_level": case.get("expected_level"),
                "assigned_action": "ERROR",
                "assigned_level": 0,
                "reply_snippet": str(e)[:120],
                "ticket_id": "",
            })

    # Write results CSV
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "test_id", "query", "expected_action", "expected_level",
            "assigned_action", "assigned_level", "reply_snippet", "ticket_id"
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n[eval] Results written to {RESULTS_CSV}\n")
    compute_metrics(results)


if __name__ == "__main__":
    main()
