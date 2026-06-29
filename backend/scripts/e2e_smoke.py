#!/usr/bin/env python3
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:8000"


class SmokeFailure(Exception):
    pass


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            if response.status != 200:
                raise SmokeFailure(f"{method} {path}: expected 200, got {response.status}: {body}")
            return json.loads(body)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeFailure(f"{method} {path}: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeFailure(f"{method} {path}: backend not reachable at {BASE_URL}: {exc}") from exc


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def contains_tran_minh_tien(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False)
    return "Trần Minh Tiến" in serialized or "Tran Minh Tien" in serialized


def main() -> int:
    failures: list[str] = []

    def run(name: str, fn) -> None:
        try:
            fn()
            print(f"[PASS] {name}")
        except SmokeFailure as exc:
            failures.append(f"{name}: {exc}")
            print(f"[FAIL] {name}: {exc}")

    def test_health() -> None:
        payload = request_json("GET", "/health")
        assert_true(payload.get("status") == "ok", f"unexpected health payload: {payload}")
        print(
            "       models:",
            payload.get("model_primary"),
            payload.get("model_fallback"),
            "available:",
            payload.get("primary_available"),
            payload.get("fallback_available"),
        )

    def test_chat_hello() -> None:
        payload = request_json("POST", "/chat", {"query": "hello"})
        assert_true(payload.get("route") == "fixed", f"expected fixed route, got {payload}")

    def test_member_chat() -> None:
        payload = request_json("POST", "/chat", {"query": "giám đốc trung tâm vật lý lý thuyết là ai"})
        assert_true(payload.get("route") == "member", f"expected member route, got {payload.get('route')}")
        assert_true(contains_tran_minh_tien(payload), "expected Trần Minh Tiến in answer or metadata")

    def test_rag_chat() -> None:
        payload = request_json("POST", "/chat", {"query": "trung tâm vật lý lý thuyết nghiên cứu gì"})
        assert_true(payload.get("route") == "rag", f"expected rag route, got {payload.get('route')}")
        assert_true("answer" in payload, "missing answer")
        assert_true(isinstance(payload.get("warnings", []), list), "warnings must be a list")

    def test_thu_truong_not_time() -> None:
        payload = request_json("POST", "/chat", {"query": "Thứ trưởng Bộ Khoa học là ai"})
        assert_true(payload.get("route") != "time", f"unexpected time route: {payload}")

    def test_member_lookup() -> None:
        payload = request_json("POST", "/members/lookup", {"query": "giám đốc trung tâm vật lý lý thuyết"})
        assert_true("status" in payload, f"invalid member lookup payload: {payload}")

    def test_vision_unknown() -> None:
        payload = request_json("POST", "/vision/recognize", {"image_path": "/tmp/ivastbot_missing_image.jpg"})
        assert_true(payload.get("status") in {"unknown", "error"}, f"expected handled unknown/error, got {payload}")

    run("GET /health", test_health)
    run('POST /chat "hello"', test_chat_hello)
    run("POST /chat member director", test_member_chat)
    run("POST /chat RAG research", test_rag_chat)
    run("POST /chat Thu truong not time", test_thu_truong_not_time)
    run("POST /members/lookup", test_member_lookup)
    run("POST /vision/recognize unknown", test_vision_unknown)

    if failures:
        print("\nE2E SMOKE RESULT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nE2E SMOKE RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

