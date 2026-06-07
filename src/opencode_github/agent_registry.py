"""Agent Registry — discovery and lifecycle management for ACP agents.

Maintains a registry of connected agents, tracks their health via
heartbeats, and provides lookup/filtering for the Agent Command Center
Kanban view described by Devin Desktop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from opencode_github.acp import (
    ACPCapability,
    ACPRegistration,
    AgentStatus,
)


@dataclass
class RegisteredAgent:
    """An agent entry in the registry with health tracking."""

    agent_id: str
    agent_name: str
    agent_type: str
    status: AgentStatus
    capabilities: list[ACPCapability]
    registered_at: float
    last_heartbeat: float
    metadata: dict[str, str] = field(default_factory=dict)
    current_task: str | None = None
    space_ids: list[str] = field(default_factory=list)

    def is_healthy(self, timeout_seconds: float = 60.0) -> bool:
        """Return ``True`` if a heartbeat arrived within *timeout_seconds*."""
        return (time.time() - self.last_heartbeat) < timeout_seconds

    def has_capability(self, capability_name: str) -> bool:
        """Check whether this agent advertises a capability by name."""
        return any(c.name == capability_name for c in self.capabilities)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "capabilities": [
                {"name": c.name, "version": c.version, "description": c.description}
                for c in self.capabilities
            ],
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
            "current_task": self.current_task,
            "space_ids": self.space_ids,
        }


class AgentRegistry:
    """In-memory registry of ACP-connected agents."""

    def __init__(self, heartbeat_timeout: float = 60.0) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._heartbeat_timeout = heartbeat_timeout

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    def register(self, registration: ACPRegistration) -> RegisteredAgent:
        """Add or re-register an agent.  Returns the ``RegisteredAgent``."""
        now = time.time()
        agent = RegisteredAgent(
            agent_id=registration.agent_id,
            agent_name=registration.agent_name,
            agent_type=registration.agent_type,
            status=AgentStatus.IDLE,
            capabilities=list(registration.capabilities),
            registered_at=now,
            last_heartbeat=now,
            metadata=dict(registration.metadata),
        )
        self._agents[registration.agent_id] = agent
        return agent

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent.  Returns ``False`` when the ID is not found."""
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        return True

    def get(self, agent_id: str) -> RegisteredAgent | None:
        """Look up an agent by ID."""
        return self._agents.get(agent_id)

    def update_heartbeat(self, agent_id: str, status: AgentStatus | None = None) -> bool:
        """Record a heartbeat.  Optionally update status.  Returns ``False`` if unknown."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.last_heartbeat = time.time()
        if status is not None:
            agent.status = status
        return True

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Update an agent's status.  Returns ``False`` if unknown."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.status = status
        return True

    def assign_task(self, agent_id: str, task_description: str) -> bool:
        """Mark an agent as busy with a task.  Returns ``False`` if unknown."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.status = AgentStatus.BUSY
        agent.current_task = task_description
        return True

    def complete_task(self, agent_id: str) -> bool:
        """Mark an agent's current task as done.  Returns ``False`` if unknown."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.status = AgentStatus.IDLE
        agent.current_task = None
        return True

    def list_agents(self) -> list[RegisteredAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def list_healthy(self) -> list[RegisteredAgent]:
        """Return agents whose last heartbeat is within the timeout."""
        return [a for a in self._agents.values() if a.is_healthy(self._heartbeat_timeout)]

    def list_by_status(self, status: AgentStatus) -> list[RegisteredAgent]:
        """Return agents matching a given status."""
        return [a for a in self._agents.values() if a.status == status]

    def list_by_type(self, agent_type: str) -> list[RegisteredAgent]:
        """Return agents matching a given type."""
        return [a for a in self._agents.values() if a.agent_type == agent_type]

    def find_by_capability(self, capability_name: str) -> list[RegisteredAgent]:
        """Return agents that advertise a specific capability."""
        return [a for a in self._agents.values() if a.has_capability(capability_name)]

    def add_to_space(self, agent_id: str, space_id: str) -> bool:
        """Associate an agent with a Space.  Returns ``False`` if unknown."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        if space_id not in agent.space_ids:
            agent.space_ids.append(space_id)
        return True

    def remove_from_space(self, agent_id: str, space_id: str) -> bool:
        """Disassociate an agent from a Space.  Returns ``False`` if unknown."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        if space_id in agent.space_ids:
            agent.space_ids.remove(space_id)
        return True

    def prune_stale(self) -> list[str]:
        """Remove agents that have not sent a heartbeat within the timeout.

        Returns the IDs of pruned agents.
        """
        stale: list[str] = []
        for agent_id, agent in list(self._agents.items()):
            if not agent.is_healthy(self._heartbeat_timeout):
                stale.append(agent_id)
                del self._agents[agent_id]
        return stale

    def to_kanban(self) -> dict[str, list[dict[str, Any]]]:
        """Return agents grouped by status for a Kanban board view."""
        board: dict[str, list[dict[str, Any]]] = {status.value: [] for status in AgentStatus}
        for agent in self._agents.values():
            board[agent.status.value].append(agent.to_dict())
        return board
