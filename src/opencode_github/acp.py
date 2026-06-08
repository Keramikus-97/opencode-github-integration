"""Agent Client Protocol (ACP) implementation.

Provides the protocol layer for agents to communicate with ACP-compatible
editors such as Devin Desktop.  Handles capability negotiation, message
routing, and lifecycle management according to the ACP specification.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ACPMessageType(Enum):
    """Message types defined by the Agent Client Protocol."""

    REGISTER = "register"
    HEARTBEAT = "heartbeat"
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    CONTEXT_SYNC = "context_sync"
    STATUS_UPDATE = "status_update"
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentStatus(Enum):
    """Runtime status of an ACP-connected agent."""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    STARTING = "starting"
    SHUTTING_DOWN = "shutting_down"


class ACPVersion(Enum):
    """Supported ACP protocol versions."""

    V1 = "1.0"
    V1_1 = "1.1"


@dataclass(frozen=True)
class ACPCapability:
    """A capability that an agent advertises to the editor."""

    name: str
    version: str
    description: str
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ACPMessage:
    """A single ACP protocol message."""

    message_id: str
    message_type: ACPMessageType
    sender_id: str
    recipient_id: str
    payload: dict[str, Any]
    timestamp: float
    protocol_version: str = ACPVersion.V1.value
    correlation_id: str | None = None

    @classmethod
    def create(
        cls,
        message_type: ACPMessageType,
        sender_id: str,
        recipient_id: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        protocol_version: str = ACPVersion.V1.value,
    ) -> ACPMessage:
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=message_type,
            sender_id=sender_id,
            recipient_id=recipient_id,
            payload=payload or {},
            timestamp=time.time(),
            protocol_version=protocol_version,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version,
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True)
class ACPRegistration:
    """Registration payload sent by an agent to join the ACP network."""

    agent_id: str
    agent_name: str
    agent_type: str
    capabilities: list[ACPCapability]
    protocol_version: str = ACPVersion.V1.value
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "capabilities": [
                {
                    "name": c.name,
                    "version": c.version,
                    "description": c.description,
                    "parameters": c.parameters,
                }
                for c in self.capabilities
            ],
            "protocol_version": self.protocol_version,
            "metadata": self.metadata,
        }


def validate_message(data: dict[str, Any]) -> ACPMessage | None:
    """Parse and validate a raw dictionary into an ``ACPMessage``.

    Returns ``None`` when the payload is malformed or missing required fields.
    """
    required = {"message_id", "message_type", "sender_id", "recipient_id", "payload", "timestamp"}
    if not required.issubset(data.keys()):
        return None

    try:
        msg_type = ACPMessageType(data["message_type"])
    except ValueError:
        return None

    if not isinstance(data["payload"], dict):
        return None

    for str_field in ("message_id", "sender_id", "recipient_id"):
        if not isinstance(data[str_field], str):
            return None

    if not isinstance(data["timestamp"], (int, float)):
        return None

    correlation_id = data.get("correlation_id")
    if correlation_id is not None and not isinstance(correlation_id, str):
        return None

    raw_version = data.get("protocol_version", ACPVersion.V1.value)
    if not isinstance(raw_version, str):
        return None

    return ACPMessage(
        message_id=data["message_id"],
        message_type=msg_type,
        sender_id=data["sender_id"],
        recipient_id=data["recipient_id"],
        payload=data["payload"],
        timestamp=float(data["timestamp"]),
        protocol_version=raw_version,
        correlation_id=correlation_id,
    )


def create_registration_message(
    registration: ACPRegistration,
    editor_id: str,
) -> ACPMessage:
    """Build a REGISTER message from an ``ACPRegistration``."""
    return ACPMessage.create(
        message_type=ACPMessageType.REGISTER,
        sender_id=registration.agent_id,
        recipient_id=editor_id,
        payload=registration.to_dict(),
        protocol_version=registration.protocol_version,
    )


def create_heartbeat(agent_id: str, editor_id: str, status: AgentStatus) -> ACPMessage:
    """Build a HEARTBEAT message reporting current agent status."""
    return ACPMessage.create(
        message_type=ACPMessageType.HEARTBEAT,
        sender_id=agent_id,
        recipient_id=editor_id,
        payload={"status": status.value},
    )


def create_task_response(
    agent_id: str,
    editor_id: str,
    task_id: str,
    result: dict[str, Any],
    success: bool = True,
    correlation_id: str | None = None,
) -> ACPMessage:
    """Build a TASK_RESPONSE message for a completed task."""
    return ACPMessage.create(
        message_type=ACPMessageType.TASK_RESPONSE,
        sender_id=agent_id,
        recipient_id=editor_id,
        payload={"task_id": task_id, "result": result, "success": success},
        correlation_id=correlation_id,
    )


def create_error_message(
    sender_id: str,
    recipient_id: str,
    error_code: str,
    error_detail: str,
    correlation_id: str | None = None,
) -> ACPMessage:
    """Build an ERROR message."""
    return ACPMessage.create(
        message_type=ACPMessageType.ERROR,
        sender_id=sender_id,
        recipient_id=recipient_id,
        payload={"error_code": error_code, "detail": error_detail},
        correlation_id=correlation_id,
    )


def create_status_update(
    agent_id: str,
    editor_id: str,
    status: AgentStatus,
    detail: str = "",
) -> ACPMessage:
    """Build a STATUS_UPDATE message."""
    return ACPMessage.create(
        message_type=ACPMessageType.STATUS_UPDATE,
        sender_id=agent_id,
        recipient_id=editor_id,
        payload={"status": status.value, "detail": detail},
    )


def negotiate_version(
    client_versions: list[str],
    server_versions: list[str] | None = None,
) -> str | None:
    """Determine the highest mutually supported ACP version.

    Returns ``None`` when there is no overlap.
    """
    supported = {v.value for v in ACPVersion}
    if server_versions is not None:
        supported = supported & set(server_versions)
    overlap = supported & set(client_versions)
    if not overlap:
        return None
    return max(overlap, key=lambda v: tuple(int(p) for p in v.split(".")))


def build_opencode_registration(
    agent_id: str | None = None,
    extra_metadata: dict[str, str] | None = None,
) -> ACPRegistration:
    """Create an ACP registration for the OpenCode GitHub integration agent."""
    capabilities = [
        ACPCapability(
            name="code_review",
            version="1.0",
            description="Review pull requests and suggest improvements",
        ),
        ACPCapability(
            name="issue_response",
            version="1.0",
            description="Analyze and respond to GitHub issues",
        ),
        ACPCapability(
            name="slash_commands",
            version="1.0",
            description="Process /oc and /opencode slash commands",
            parameters={"triggers": "/oc,/opencode"},
        ),
        ACPCapability(
            name="assumption_analysis",
            version="1.0",
            description="Gamified critical analysis of documentation assumptions",
        ),
    ]

    metadata = {"runtime": "python", "platform": "github"}
    if extra_metadata:
        metadata.update(extra_metadata)

    return ACPRegistration(
        agent_id=agent_id or f"opencode-{uuid.uuid4().hex[:8]}",
        agent_name="OpenCode GitHub Integration",
        agent_type="opencode",
        capabilities=capabilities,
        metadata=metadata,
    )
