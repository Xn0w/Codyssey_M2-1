# -*- coding: utf-8 -*-
"""Gemini 어댑터 (feat/demo-ground): OpenAI Responses 모양으로 감싸 LlmPlanner 가 그대로 쓰는지 확인."""
import json

from orchestrator.llm import GeminiResponses, OUTPUT_SCHEMA


def _ok(text):
    return 200, {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_schema_and_instructions_are_sent():
    seen = {}

    def http(url, headers, body, timeout):
        seen.update(url=url, body=body, timeout=timeout)
        return _ok('{"state_version": 3, "groups": []}')

    r = GeminiResponses("k", http=http).responses.create(
        model="gemini-2.5-flash", instructions="SYS", input='{"a":1}',
        text={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}}, timeout=12)
    assert json.loads(r.output_text)["state_version"] == 3
    assert "gemini-2.5-flash:generateContent" in seen["url"]
    g = seen["body"]["generationConfig"]
    assert g["responseMimeType"] == "application/json" and g["responseJsonSchema"] == OUTPUT_SCHEMA
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert 11 < seen["timeout"] <= 12


def test_schema_rejected_falls_back_to_plain_json():
    calls = []

    def http(url, headers, body, timeout):
        calls.append(json.loads(json.dumps(body)))
        return (400, {"error": {"message": "bad schema"}}) if len(calls) == 1 else _ok("{}")

    r = GeminiResponses("k", http=http).create(model="m", instructions="S", input="X",
                                               text={"format": {"schema": OUTPUT_SCHEMA}})
    assert r.output_text == "{}"
    assert "responseJsonSchema" not in calls[1]["generationConfig"]
    assert "출력 JSON 스키마" in calls[1]["contents"][0]["parts"][0]["text"]


def test_http_error_raises_without_key_in_message():
    def http(url, headers, body, timeout):
        return 403, {"error": {"message": "API key not valid"}}

    try:
        GeminiResponses("secret-key", http=http).create(model="m", instructions="S", input="X")
    except RuntimeError as e:
        assert "GEMINI_HTTP_403" in str(e) and "secret-key" not in str(e)
    else:
        raise AssertionError("오류가 나야 한다")


def test_overload_is_retried(monkeypatch):
    import orchestrator.llm as m
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    calls = []

    def http(url, headers, body, timeout):
        calls.append(1)
        return (503, {"error": {"message": "high demand"}}) if len(calls) < 3 else _ok("{}")

    r = GeminiResponses("k", http=http).create(model="m", instructions="S", input="X")
    assert r.output_text == "{}" and len(calls) == 3
