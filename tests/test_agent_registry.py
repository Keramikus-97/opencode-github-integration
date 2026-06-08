"""Tests for the Agent Registry module."""

from __future__ import annotations

import time

import pytest

from opencode_github.acp import (
    ACPCapability,
    ACPRegistration,
    AgentStatus,
    build_opencode_registration,
)
from opencode_github.agent_registry import (
    AgentRegistry,
    RegisteredAgent,
)

# --- Fixtures ---


@pytest.fixture
def registry() -> AgentRegistry:
    return AgentRegistry(heartbeat_timeout=5.0)


@pytest.fixture
def opencode_reg() -> ACPRegistration:
    return build_opencode_registration(agent_id="opencode-1")


@pytest.fixture
def codex_reg() -> ACPRegistration:
    return ACPRegistration(
        agent_id="codex-1",
        agent_name="Codex Agent",
        agent_type="codex",
        capabilities=[
            ACPCapability(name="code_generation", version="1.0", description="Generate code"),
        ],
    )


@pytest.fixture
def claude_reg() -> ACPRegistration:
    return ACPRegistration(
        agent_id="claude-1",
        agent_name="Claude Agent",
        agent_type="claude",
        capabilities=[
            ACPCapability(name="code_review", version="1.0", description="Review code"),
            ACPCapability(name="reasoning", version="1.0", description="Complex reasoning"),
        ],
    )


# --- RegisteredAgent Tests ---


class TestRegisteredAgent:
    def test_is_healthy(self) -> None:
        agent = RegisteredAgent(
            agent_id="a-1",
            agent_name="Test",
            agent_type="test",
            status=AgentStatus.IDLE,
            capabilities=[],
            registered_at=time.time(),
            last_heartbeat=time.time(),
        )
        assert agent.is_healthy(timeout_seconds=60.0) is True

    def test_is_unhealthy(self) -> None:
        agent = RegisteredAgent(
            agent_id="a-1",
            agent_name="Test",
            agent_type="test",
            status=AgentStatus.IDLE,
            capabilities=[],
            registered_at=time.time(),
            last_heartbeat=time.time() - 120,
        )
        assert agent.is_healthy(timeout_seconds=60.0) is False

    def test_has_capability(self) -> None:
        cap = ACPCapability(name="review", version="1.0", description="Code review")
        agent = RegisteredAgent(
            agent_id="a-1",
            agent_name="Test",
            agent_type="test",
            status=AgentStatus.IDLE,
            capabilities=[cap],
            registered_at=time.time(),
            last_heartbeat=time.time(),
        )
        assert agent.has_capability("review") is True
        assert agent.has_capability("deploy") is False

    def test_to_dict(self) -> None:
        agent = RegisteredAgent(
            agent_id="a-1",
            agent_name="Test",
            agent_type="test",
            status=AgentStatus.BUSY,
            capabilities=[],
            registered_at=1000.0,
            last_heartbeat=2000.0,
            current_task="Working on PR",
            space_ids=["space-1"],
        )
        d = agent.to_dict()
        assert d["agent_id"] == "a-1"
        assert d["status"] == "busy"
        assert d["current_task"] == "Working on PR"
        assert d["space_ids"] == ["space-1"]

    def test_to_dict_includes_capability_parameters(self) -> None:
        cap = ACPCapability(
            name="slash_commands",
            version="1.0",
            description="Handle slash commands",
            parameters={"triggers": "/oc,/opencode"},
        )
        agent = RegisteredAgent(
            agent_id="a-1",
            agent_name="Test",
            agent_type="test",
            status=AgentStatus.IDLE,
            capabilities=[cap],
            registered_at=1000.0,
            last_heartbeat=2000.0,
        )
        d = agent.to_dict()
        assert d["capabilities"][0]["parameters"] == {"triggers": "/oc,/opencode"}


# --- Registry Registration Tests ---


class TestRegistryRegistration:
    def test_register(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        agent = registry.register(opencode_reg)
        assert agent.agent_id == "opencode-1"
        assert agent.status == AgentStatus.IDLE
        assert registry.agent_count == 1

    def test_register_multiple(
        self,
        registry: AgentRegistry,
        opencode_reg: ACPRegistration,
        codex_reg: ACPRegistration,
        claude_reg: ACPRegistration,
    ) -> None:
        registry.register(opencode_reg)
        registry.register(codex_reg)
        registry.register(claude_reg)
        assert registry.agent_count == 3

    def test_re_register_overwrites(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        agent = registry.register(opencode_reg)
        assert registry.agent_count == 1
        assert agent.status == AgentStatus.IDLE

    def test_unregister(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        assert registry.unregister("opencode-1") is True
        assert registry.agent_count == 0

    def test_unregister_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.unregister("nonexistent") is False

    def test_get(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        agent = registry.get("opencode-1")
        assert agent is not None
        assert agent.agent_name == "OpenCode GitHub Integration"

    def test_get_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.get("nonexistent") is None


# --- Heartbeat & Status Tests ---


class TestHeartbeatAndStatus:
    def test_update_heartbeat(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        assert registry.update_heartbeat("opencode-1") is True

    def test_update_heartbeat_with_status(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        registry.update_heartbeat("opencode-1", status=AgentStatus.BUSY)
        agent = registry.get("opencode-1")
        assert agent is not None
        assert agent.status == AgentStatus.BUSY

    def test_update_heartbeat_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.update_heartbeat("nonexistent") is False

    def test_update_status(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        assert registry.update_status("opencode-1", AgentStatus.ERROR) is True
        agent = registry.get("opencode-1")
        assert agent is not None
        assert agent.status == AgentStatus.ERROR

    def test_update_status_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.update_status("nonexistent", AgentStatus.IDLE) is False


# --- Task Management Tests ---


class TestTaskManagement:
    def test_assign_task(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        assert registry.assign_task("opencode-1", "Review PR #5") is True
        agent = registry.get("opencode-1")
        assert agent is not None
        assert agent.status == AgentStatus.BUSY
        assert agent.current_task == "Review PR #5"

    def test_assign_task_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.assign_task("nonexistent", "task") is False

    def test_assign_task_rejects_error_agent(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        registry.update_status("opencode-1", AgentStatus.ERROR)
        assert registry.assign_task("opencode-1", "task") is False

    def test_assign_task_rejects_offline_agent(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        registry.update_status("opencode-1", AgentStatus.OFFLINE)
        assert registry.assign_task("opencode-1", "task") is False

    def test_assign_task_rejects_shutting_down_agent(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        registry.update_status("opencode-1", AgentStatus.SHUTTING_DOWN)
        assert registry.assign_task("opencode-1", "task") is False

    def test_complete_task(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        registry.assign_task("opencode-1", "Review PR #5")
        assert registry.complete_task("opencode-1") is True
        agent = registry.get("opencode-1")
        assert agent is not None
        assert agent.status == AgentStatus.IDLE
        assert agent.current_task is None

    def test_complete_task_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.complete_task("nonexistent") is False


# --- Listing & Filtering Tests ---


class TestListingAndFiltering:
    def test_list_agents(
        self,
        registry: AgentRegistry,
        opencode_reg: ACPRegistration,
        codex_reg: ACPRegistration,
    ) -> None:
        registry.register(opencode_reg)
        registry.register(codex_reg)
        agents = registry.list_agents()
        assert len(agents) == 2

    def test_list_healthy(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        healthy = registry.list_healthy()
        assert len(healthy) == 1

    def test_list_by_status(
        self,
        registry: AgentRegistry,
        opencode_reg: ACPRegistration,
        codex_reg: ACPRegistration,
    ) -> None:
        registry.register(opencode_reg)
        registry.register(codex_reg)
        registry.assign_task("opencode-1", "work")
        busy = registry.list_by_status(AgentStatus.BUSY)
        idle = registry.list_by_status(AgentStatus.IDLE)
        assert len(busy) == 1
        assert len(idle) == 1

    def test_list_by_type(
        self,
        registry: AgentRegistry,
        opencode_reg: ACPRegistration,
        codex_reg: ACPRegistration,
        claude_reg: ACPRegistration,
    ) -> None:
        registry.register(opencode_reg)
        registry.register(codex_reg)
        registry.register(claude_reg)
        opencode_agents = registry.list_by_type("opencode")
        assert len(opencode_agents) == 1
        assert opencode_agents[0].agent_id == "opencode-1"

    def test_find_by_capability(
        self,
        registry: AgentRegistry,
        opencode_reg: ACPRegistration,
        codex_reg: ACPRegistration,
        claude_reg: ACPRegistration,
    ) -> None:
        registry.register(opencode_reg)
        registry.register(codex_reg)
        registry.register(claude_reg)
        reviewers = registry.find_by_capability("code_review")
        assert len(reviewers) == 2
        ids = {a.agent_id for a in reviewers}
        assert "opencode-1" in ids
        assert "claude-1" in ids

    def test_find_by_capability_no_match(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        result = registry.find_by_capability("deploy_to_prod")
        assert result == []


# --- Space Association Tests ---


class TestSpaceAssociation:
    def test_add_to_space(self, registry: AgentRegistry, opencode_reg: ACPRegistration) -> None:
        registry.register(opencode_reg)
        assert registry.add_to_space("opencode-1", "space-1") is True
        agent = registry.get("opencode-1")
        assert agent is not None
        assert "space-1" in agent.space_ids

    def test_add_to_space_duplicate(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        registry.add_to_space("opencode-1", "space-1")
        registry.add_to_space("opencode-1", "space-1")
        agent = registry.get("opencode-1")
        assert agent is not None
        assert agent.space_ids.count("space-1") == 1

    def test_add_to_space_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.add_to_space("nonexistent", "space-1") is False

    def test_remove_from_space(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        registry.add_to_space("opencode-1", "space-1")
        assert registry.remove_from_space("opencode-1", "space-1") is True
        agent = registry.get("opencode-1")
        assert agent is not None
        assert "space-1" not in agent.space_ids

    def test_remove_from_space_not_in(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        assert registry.remove_from_space("opencode-1", "space-99") is False

    def test_remove_from_space_nonexistent(self, registry: AgentRegistry) -> None:
        assert registry.remove_from_space("nonexistent", "space-1") is False


# --- Pruning Tests ---


class TestPruning:
    def test_prune_stale(self, registry: AgentRegistry) -> None:
        reg = ACPRegistration(
            agent_id="stale-1",
            agent_name="Stale",
            agent_type="test",
            capabilities=[],
        )
        agent = registry.register(reg)
        # Make the heartbeat stale (timeout is 5s)
        agent.last_heartbeat = time.time() - 10
        pruned = registry.prune_stale()
        assert "stale-1" in pruned
        assert registry.agent_count == 0

    def test_prune_keeps_healthy(
        self, registry: AgentRegistry, opencode_reg: ACPRegistration
    ) -> None:
        registry.register(opencode_reg)
        pruned = registry.prune_stale()
        assert pruned == []
        assert registry.agent_count == 1


# --- Kanban View Tests ---


class TestKanbanView:
    def test_kanban_groups_by_status(
        self,
        registry: AgentRegistry,
        opencode_reg: ACPRegistration,
        codex_reg: ACPRegistration,
        claude_reg: ACPRegistration,
    ) -> None:
        registry.register(opencode_reg)
        registry.register(codex_reg)
        registry.register(claude_reg)
        registry.assign_task("opencode-1", "Review")
        registry.update_status("claude-1", AgentStatus.ERROR)

        board = registry.to_kanban()
        assert len(board["busy"]) == 1
        assert len(board["idle"]) == 1
        assert len(board["error"]) == 1
        assert board["busy"][0]["agent_id"] == "opencode-1"

    def test_kanban_all_statuses_present(self, registry: AgentRegistry) -> None:
        board = registry.to_kanban()
        for status in AgentStatus:
            assert status.value in board

    def test_kanban_empty(self, registry: AgentRegistry) -> None:
        board = registry.to_kanban()
        for column in board.values():
            assert column == []


# --- Integration Tests ---


class TestIntegration:
    def test_full_agent_lifecycle(self, registry: AgentRegistry) -> None:
        """Simulate a complete agent lifecycle: register → task → complete → unregister."""
        reg = build_opencode_registration(agent_id="lifecycle-agent")
        agent = registry.register(reg)
        assert agent.status == AgentStatus.IDLE
        assert registry.agent_count == 1

        registry.update_heartbeat("lifecycle-agent")
        assert registry.list_healthy() == [agent]

        registry.assign_task("lifecycle-agent", "Analyze PR #10")
        assert agent.status == AgentStatus.BUSY
        assert agent.current_task == "Analyze PR #10"

        registry.add_to_space("lifecycle-agent", "space-pr10")
        assert "space-pr10" in agent.space_ids

        registry.complete_task("lifecycle-agent")
        assert agent.status == AgentStatus.IDLE
        assert agent.current_task is None

        registry.unregister("lifecycle-agent")
        assert registry.agent_count == 0

    def test_multi_agent_collaboration(self, registry: AgentRegistry) -> None:
        """Simulate multiple agents collaborating in a shared space."""
        agents = [
            build_opencode_registration(agent_id="oc-1"),
            ACPRegistration(
                agent_id="codex-1",
                agent_name="Codex",
                agent_type="codex",
                capabilities=[
                    ACPCapability(name="code_generation", version="1.0", description="Generate"),
                ],
            ),
            ACPRegistration(
                agent_id="claude-1",
                agent_name="Claude",
                agent_type="claude",
                capabilities=[
                    ACPCapability(name="reasoning", version="1.0", description="Reason"),
                ],
            ),
        ]

        for reg in agents:
            registry.register(reg)

        assert registry.agent_count == 3

        for agent_id in ["oc-1", "codex-1", "claude-1"]:
            registry.add_to_space(agent_id, "space-collab")

        registry.assign_task("oc-1", "Review")
        registry.assign_task("codex-1", "Generate tests")

        busy = registry.list_by_status(AgentStatus.BUSY)
        assert len(busy) == 2

        code_reviewers = registry.find_by_capability("code_review")
        assert len(code_reviewers) == 1
        assert code_reviewers[0].agent_id == "oc-1"
