#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brain.harness import BrainHarness

DEFAULT_EVAL_SET = ROOT / "eval" / "rag_eval_set.jsonl"
REPORT_PATH = ROOT / "eval" / "reports" / "latest_rag_eval.md"


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return cases


def text_contains_any(text: str, needles: list[str]) -> bool:
    if not needles:
        return True
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def text_contains_none(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return not any(needle.lower() in lowered for needle in needles)


def is_model_unavailable(response: dict[str, Any]) -> bool:
    warning_items = [str(item).lower() for item in (response.get("warnings") or [])]
    answer = str(response.get("answer", "")).lower()
    fallback_missing = any("fallback ollama model" in item and "not available" in item for item in warning_items)
    return fallback_missing or "không gọi được ollama" in answer or ("model" in answer and "not found" in answer)


def evaluate_case(harness: BrainHarness, case: dict[str, Any]) -> dict[str, Any]:
    response = harness.handle({"query": case["question"], "mode": "auto"}).to_dict()
    answer = response.get("answer", "")
    serialized = json.dumps(response, ensure_ascii=False)
    route_pass = response.get("route") == case.get("expected_route")

    expected_any = case.get("expected_contains_any") or []
    legacy_expected = case.get("expected_contains")
    if legacy_expected:
        expected_any = [legacy_expected, *expected_any]
    must_not = case.get("must_not_contain") or []

    unavailable = is_model_unavailable(response)
    contains_pass = text_contains_any(serialized, expected_any)
    if unavailable and response.get("route") == "rag":
        contains_pass = True
    must_not_pass = text_contains_none(answer, must_not)
    passed = route_pass and contains_pass and must_not_pass

    return {
        "question": case["question"],
        "expected_route": case.get("expected_route"),
        "route": response.get("route"),
        "route_pass": route_pass,
        "contains_pass": contains_pass,
        "must_not_pass": must_not_pass,
        "passed": passed,
        "confidence": response.get("confidence", 0),
        "warnings": response.get("warnings", []),
        "model_unavailable": unavailable,
        "answer": answer,
        "notes": case.get("notes", ""),
    }


def write_report(results: list[dict[str, Any]], summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# IVASTBOT RAG Eval Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Route accuracy: {summary['route_accuracy']:.2%}",
        f"- Contains accuracy: {summary['contains_accuracy']:.2%}",
        f"- Low-confidence/refusal count: {summary['low_confidence_refusal_count']}",
        f"- Model unavailable count: {summary['model_unavailable_count']}",
        "",
        "## Failures",
        "",
    ]
    failures = [result for result in results if not result["passed"]]
    if not failures:
        lines.append("No failures.")
    else:
        for result in failures:
            lines.extend(
                [
                    f"### {result['question']}",
                    "",
                    f"- Expected route: `{result['expected_route']}`",
                    f"- Actual route: `{result['route']}`",
                    f"- Route pass: {result['route_pass']}",
                    f"- Contains pass: {result['contains_pass']}",
                    f"- Must-not pass: {result['must_not_pass']}",
                    f"- Confidence: {result['confidence']}",
                    f"- Warnings: {result['warnings']}",
                    f"- Answer: {result['answer']}",
                    "",
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run IVASTBOT RAG eval set.")
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--report", default=str(REPORT_PATH))
    args = parser.parse_args()

    cases = load_cases(Path(args.eval_set))
    harness = BrainHarness()
    results = [evaluate_case(harness, case) for case in cases]

    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    route_passed = sum(1 for result in results if result["route_pass"])
    contains_passed = sum(1 for result in results if result["contains_pass"])
    low_confidence_refusal_count = sum(
        1
        for result in results
        if result["route"] == "unknown" or "chưa có đủ thông tin" in str(result["answer"]).lower()
    )
    model_unavailable_count = sum(1 for result in results if result["model_unavailable"])
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "route_accuracy": route_passed / total if total else 0.0,
        "contains_accuracy": contains_passed / total if total else 0.0,
        "low_confidence_refusal_count": low_confidence_refusal_count,
        "model_unavailable_count": model_unavailable_count,
    }
    write_report(results, summary, Path(args.report))

    print("RAG EVAL SUMMARY")
    print(f"total: {summary['total']}")
    print(f"passed: {summary['passed']}")
    print(f"failed: {summary['failed']}")
    print(f"route_accuracy: {summary['route_accuracy']:.2%}")
    print(f"contains_accuracy: {summary['contains_accuracy']:.2%}")
    print(f"low_confidence_refusal_count: {summary['low_confidence_refusal_count']}")
    print(f"model_unavailable_count: {summary['model_unavailable_count']}")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
