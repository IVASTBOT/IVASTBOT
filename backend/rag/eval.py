from dataclasses import dataclass

from .generator import UNKNOWN_ANSWER, generate
from .retriever import retrieve


@dataclass
class EvalCase:
    query: str
    expected_contains: str


DEFAULT_EVAL_SET = [
    EvalCase("Viện trưởng Viện Vật lý là ai?", "Đinh Văn Trung"),
    EvalCase("Trung tâm Vật lý lý thuyết nghiên cứu gì?", "Vật lý lý thuyết"),
]


def run_eval(cases: list[EvalCase] | None = None) -> list[dict]:
    results = []
    for case in cases or DEFAULT_EVAL_SET:
        chunks = retrieve(case.query)
        answer = generate(case.query, chunks)
        results.append(
            {
                "query": case.query,
                "answer": answer,
                "expected_contains": case.expected_contains,
                "passed": case.expected_contains.lower() in answer.lower() and answer != UNKNOWN_ANSWER,
            }
        )
    return results

