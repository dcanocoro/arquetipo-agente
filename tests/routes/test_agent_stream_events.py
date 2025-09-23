"""Unit tests for the streaming utilities in ``app.routes.agent``."""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("qgdiag_lib_arquitectura")

from app.routes.agent import _event_to_wire


def test_event_to_wire_stream_includes_tool_debug_snapshot():
    chunk_payload = {
        "content": [{"type": "text", "text": "partial"}],
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search", "arguments": "{\"query\": \"python\"}"},
            }
        ],
        "additional_kwargs": {
            "function_call": {"name": "search", "arguments": "{\"query\": \"python\"}"},
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": "{\"query\": \"python\"}"},
                }
            ],
        },
    }

    event = {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "run_id": "run-123",
        "data": {"chunk": chunk_payload},
    }

    wire_event = _event_to_wire(event)

    assert wire_event["type"] == "token"
    payload = wire_event["data"]

    # The delta should be derived from the textual content
    assert payload["delta"] == "partial"

    # Tool call information must be exposed both as a delta and in the debug block
    tool_deltas = payload.get("tool_calls_delta")
    assert tool_deltas and tool_deltas[0]["function"]["name"] == "search"

    debug_block = payload.get("debug")
    assert "chunk_tool_calls" in debug_block
    assert debug_block["chunk_tool_calls"][0]["function"]["name"] == "search"
    assert debug_block["additional_kwargs"]["function_call"]["name"] == "search"


def test_event_to_wire_chat_model_end_exposes_tool_calls():
    event = {
        "event": "on_chat_model_end",
        "name": "ChatOpenAI",
        "run_id": "run-456",
        "data": {
            "output": {
                "tool_calls": [
                    {
                        "id": "call_42",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": "{\"id\": 42}"},
                    }
                ]
            }
        },
    }

    wire_event = _event_to_wire(event)

    assert wire_event["type"] == "chat_model_end"
    payload = wire_event["data"]

    # raw_output should be serialisable to JSON for logging/streaming purposes
    json.dumps(payload["raw_output"])

    tool_calls = payload.get("tool_calls")
    assert tool_calls and tool_calls[0]["function"]["name"] == "lookup"
