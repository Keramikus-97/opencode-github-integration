"""Tests for the Agent Client Protocol module."""

from __future__ import annotations

import time

import pytest

from opencode_github.acp import (
    ACPCapability,
    ACPMessage,
    ACPMessageType,
    ACPRegistration,
    ACPVersion,
    AgentStatus,
    build_opencode_registration,
    create_error_message,
    create_heartbeat,
    create_registration_message,
    create_status_update,
    create_task_response,
    negotiate_version,
    validate_message,
)

# --- ACPMessage Tests ---


class TestACPMessage:
    def test_create(self) -> None:
        msg = ACPMessage.create(
            message_type=ACPMessageType.HEARTBEAT,
            sender_id="agent-1",
            recipient_id="editor-1",
            payload={"status": "idle"},
        )
        assert msg.message_type == ACPMessageType.HEARTBEAT
        assert msg.sender_id == "agent-1"
        assert msg.recipient_id == "editor-1"
        assert msg.payload == {"status": "idle"}
        assert msg.protocol_version == ACPVersion.V1.value
        assert msg.message_id  # non-empty

    def test_create_with_correlation(self) -> None:
        msg = ACPMessage.create(
            message_type=ACPMessageType.TASK_RESPONSE,
            sender_id="a",
            recipient_id="b",
            correlation_id="corr-123",
        )
        assert msg.correlation_id == "corr-123"

    def test_create_with_custom_version(self) -> None:
        msg = ACPMessage.create(
            message_type=ACPMessageType.REGISTER,
            sender_id="a",
            recipient_id="b",
            protocol_version=ACPVersion.V1_1.value,
        )
        assert msg.protocol_version == "1.1"

    def test_create_empty_payload(self) -> None:
        msg = ACPMessage.create(
            message_type=ACPMessageType.SHUTDOWN,
            sender_id="a",
            recipient_id="b",
        )
        assert msg.payload == {}

    def test_to_dict(self) -> None:
        msg = ACPMessage.create(
            message_type=ACPMessageType.HEARTBEAT,
            sender_id="agent-1",
            recipient_id="editor-1",
            payload={"status": "idle"},
        )
        d = msg.to_dict()
        assert d["message_type"] == "heartbeat"
        assert d["sender_id"] == "agent-1"
        assert d["recipient_id"] == "editor-1"
        assert d["payload"] == {"status": "idle"}
        assert "message_id" in d
        assert "timestamp" in d

    def test_frozen(self) -> None:
        msg = ACPMessage.create(
            message_type=ACPMessageType.HEARTBEAT,
            sender_id="a",
            recipient_id="b",
        )
        with pytest.raises(AttributeError):
            msg.sender_id = "changed"  # type: ignore[misc]


# --- Validate Message Tests ---


class TestValidateMessage:
    def test_valid_message(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "heartbeat",
            "sender_id": "agent-1",
            "recipient_id": "editor-1",
            "payload": {"status": "idle"},
            "timestamp": time.time(),
        }
        msg = validate_message(data)
        assert msg is not None
        assert msg.message_type == ACPMessageType.HEARTBEAT
        assert msg.sender_id == "agent-1"

    def test_missing_required_field(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "heartbeat",
            "sender_id": "agent-1",
            # missing recipient_id, payload, timestamp
        }
        assert validate_message(data) is None

    def test_invalid_message_type(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "invalid_type",
            "sender_id": "a",
            "recipient_id": "b",
            "payload": {},
            "timestamp": time.time(),
        }
        assert validate_message(data) is None

    def test_invalid_payload_type(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "heartbeat",
            "sender_id": "a",
            "recipient_id": "b",
            "payload": "not a dict",
            "timestamp": time.time(),
        }
        assert validate_message(data) is None

    def test_invalid_timestamp_type(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "heartbeat",
            "sender_id": "a",
            "recipient_id": "b",
            "payload": {},
            "timestamp": "not a number",
        }
        assert validate_message(data) is None

    def test_invalid_correlation_id_type(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "heartbeat",
            "sender_id": "a",
            "recipient_id": "b",
            "payload": {},
            "timestamp": time.time(),
            "correlation_id": 12345,
        }
        assert validate_message(data) is None

    def test_with_optional_fields(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "task_response",
            "sender_id": "a",
            "recipient_id": "b",
            "payload": {"result": "ok"},
            "timestamp": 1234567890.0,
            "protocol_version": "1.1",
            "correlation_id": "corr-42",
        }
        msg = validate_message(data)
        assert msg is not None
        assert msg.protocol_version == "1.1"
        assert msg.correlation_id == "corr-42"

    def test_default_protocol_version(self) -> None:
        data = {
            "message_id": "msg-1",
            "message_type": "heartbeat",
            "sender_id": "a",
            "recipient_id": "b",
            "payload": {},
            "timestamp": 1234567890.0,
        }
        msg = validate_message(data)
        assert msg is not None
        assert msg.protocol_version == ACPVersion.V1.value


# --- ACPRegistration Tests ---


class TestACPRegistration:
    def test_creation(self) -> None:
        cap = ACPCapability(name="review", version="1.0", description="Code review")
        reg = ACPRegistration(
            agent_id="agent-1",
            agent_name="Test Agent",
            agent_type="test",
            capabilities=[cap],
        )
        assert reg.agent_id == "agent-1"
        assert len(reg.capabilities) == 1

    def test_to_dict(self) -> None:
        cap = ACPCapability(
            name="review",
            version="1.0",
            description="Review code",
            parameters={"lang": "python"},
        )
        reg = ACPRegistration(
            agent_id="agent-1",
            agent_name="Test",
            agent_type="test",
            capabilities=[cap],
            metadata={"env": "prod"},
        )
        d = reg.to_dict()
        assert d["agent_id"] == "agent-1"
        assert d["capabilities"][0]["name"] == "review"
        assert d["capabilities"][0]["parameters"] == {"lang": "python"}
        assert d["metadata"] == {"env": "prod"}


# --- Factory Function Tests ---


class TestFactoryFunctions:
    def test_create_registration_message(self) -> None:
        reg = ACPRegistration(
            agent_id="agent-1",
            agent_name="Test",
            agent_type="test",
            capabilities=[],
        )
        msg = create_registration_message(reg, "editor-1")
        assert msg.message_type == ACPMessageType.REGISTER
        assert msg.sender_id == "agent-1"
        assert msg.recipient_id == "editor-1"
        assert msg.payload["agent_id"] == "agent-1"

    def test_create_heartbeat(self) -> None:
        msg = create_heartbeat("agent-1", "editor-1", AgentStatus.IDLE)
        assert msg.message_type == ACPMessageType.HEARTBEAT
        assert msg.payload["status"] == "idle"

    def test_create_task_response(self) -> None:
        msg = create_task_response(
            agent_id="agent-1",
            editor_id="editor-1",
            task_id="task-42",
            result={"output": "done"},
            success=True,
            correlation_id="corr-1",
        )
        assert msg.message_type == ACPMessageType.TASK_RESPONSE
        assert msg.payload["task_id"] == "task-42"
        assert msg.payload["success"] is True
        assert msg.correlation_id == "corr-1"

    def test_create_task_response_failure(self) -> None:
        msg = create_task_response(
            agent_id="a",
            editor_id="b",
            task_id="t-1",
            result={"error": "timeout"},
            success=False,
        )
        assert msg.payload["success"] is False

    def test_create_error_message(self) -> None:
        msg = create_error_message("a", "b", "E001", "Something went wrong", "corr-1")
        assert msg.message_type == ACPMessageType.ERROR
        assert msg.payload["error_code"] == "E001"
        assert msg.payload["detail"] == "Something went wrong"
        assert msg.correlation_id == "corr-1"

    def test_create_status_update(self) -> None:
        msg = create_status_update("agent-1", "editor-1", AgentStatus.BUSY, "Processing PR #5")
        assert msg.message_type == ACPMessageType.STATUS_UPDATE
        assert msg.payload["status"] == "busy"
        assert msg.payload["detail"] == "Processing PR #5"


# --- Version Negotiation Tests ---


class TestNegotiateVersion:
    def test_matching_version(self) -> None:
        result = negotiate_version(["1.0"])
        assert result == "1.0"

    def test_highest_version(self) -> None:
        result = negotiate_version(["1.0", "1.1"])
        assert result == "1.1"

    def test_no_overlap(self) -> None:
        result = negotiate_version(["2.0"], server_versions=["1.0"])
        assert result is None

    def test_with_server_versions(self) -> None:
        result = negotiate_version(["1.0", "1.1"], server_versions=["1.0"])
        assert result == "1.0"

    def test_empty_client_versions(self) -> None:
        result = negotiate_version([])
        assert result is None


# --- OpenCode Registration Tests ---


class TestBuildOpenCodeRegistration:
    def test_default(self) -> None:
        reg = build_opencode_registration()
        assert reg.agent_name == "OpenCode GitHub Integration"
        assert reg.agent_type == "opencode"
        assert reg.agent_id.startswith("opencode-")
        assert len(reg.capabilities) == 4
        cap_names = {c.name for c in reg.capabilities}
        assert "code_review" in cap_names
        assert "slash_commands" in cap_names
        assert "assumption_analysis" in cap_names

    def test_custom_id(self) -> None:
        reg = build_opencode_registration(agent_id="my-agent")
        assert reg.agent_id == "my-agent"

    def test_extra_metadata(self) -> None:
        reg = build_opencode_registration(extra_metadata={"region": "eu"})
        assert reg.metadata["region"] == "eu"
        assert reg.metadata["runtime"] == "python"


# --- Enum Coverage ---


class TestEnums:
    def test_all_message_types(self) -> None:
        assert len(ACPMessageType) == 10

    def test_all_agent_statuses(self) -> None:
        assert len(AgentStatus) == 6

    def test_acp_versions(self) -> None:
        assert ACPVersion.V1.value == "1.0"
        assert ACPVersion.V1_1.value == "1.1"
