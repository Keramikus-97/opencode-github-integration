"""Tests for the Spaces module."""

from __future__ import annotations

import time

import pytest

from opencode_github.spaces import (
    ContextItem,
    ContextItemType,
    Space,
    SpaceVisibility,
    create_context_item,
    create_space,
    filter_context_since,
    merge_spaces,
    summarize_space,
)

# --- Fixtures ---


@pytest.fixture
def empty_space() -> Space:
    return create_space("Test Space", description="A test space", owner_id="agent-1")


@pytest.fixture
def sample_item() -> ContextItem:
    return create_context_item(
        item_type=ContextItemType.FILE,
        title="main.py",
        content="print('hello')",
        source_agent_id="agent-1",
        tags=["python", "entry"],
    )


@pytest.fixture
def populated_space() -> Space:
    space = create_space("Populated", owner_id="agent-1")
    items = [
        create_context_item(ContextItemType.FILE, "app.py", "code", "agent-1", tags=["code"]),
        create_context_item(ContextItemType.PR, "PR #5", "Fix bug", "agent-2", tags=["bugfix"]),
        create_context_item(ContextItemType.ISSUE, "Issue #3", "Crash on load", "agent-1"),
        create_context_item(
            ContextItemType.NOTE, "Architecture", "Uses async patterns", "agent-3", tags=["docs"]
        ),
    ]
    for item in items:
        space.add_context(item)
    return space


# --- ContextItem Tests ---


class TestContextItem:
    def test_creation(self, sample_item: ContextItem) -> None:
        assert sample_item.item_type == ContextItemType.FILE
        assert sample_item.title == "main.py"
        assert sample_item.source_agent_id == "agent-1"
        assert "python" in sample_item.tags
        assert sample_item.item_id.startswith("ctx-")

    def test_to_dict(self, sample_item: ContextItem) -> None:
        d = sample_item.to_dict()
        assert d["item_type"] == "file"
        assert d["title"] == "main.py"
        assert d["source_agent_id"] == "agent-1"
        assert "tags" in d

    def test_frozen(self, sample_item: ContextItem) -> None:
        with pytest.raises(AttributeError):
            sample_item.title = "changed"  # type: ignore[misc]

    def test_with_metadata(self) -> None:
        item = create_context_item(
            ContextItemType.SNIPPET,
            "snippet-1",
            "x = 1",
            "agent-1",
            metadata={"language": "python", "line": "42"},
        )
        assert item.metadata["language"] == "python"


# --- Space Creation Tests ---


class TestCreateSpace:
    def test_defaults(self, empty_space: Space) -> None:
        assert empty_space.name == "Test Space"
        assert empty_space.visibility == SpaceVisibility.PRIVATE
        assert empty_space.owner_id == "agent-1"
        assert "agent-1" in empty_space.members
        assert empty_space.space_id.startswith("space-")

    def test_custom_visibility(self) -> None:
        space = create_space("Public", visibility=SpaceVisibility.PUBLIC)
        assert space.visibility == SpaceVisibility.PUBLIC

    def test_with_tags(self) -> None:
        space = create_space("Tagged", tags=["backend", "api"])
        assert space.tags == ["backend", "api"]

    def test_no_owner(self) -> None:
        space = create_space("Orphan")
        assert space.owner_id == ""
        assert space.members == []


# --- Space Membership Tests ---


class TestSpaceMembership:
    def test_add_member(self, empty_space: Space) -> None:
        assert empty_space.add_member("agent-2") is True
        assert "agent-2" in empty_space.members

    def test_add_duplicate_member(self, empty_space: Space) -> None:
        assert empty_space.add_member("agent-1") is False

    def test_remove_member(self, empty_space: Space) -> None:
        empty_space.add_member("agent-2")
        assert empty_space.remove_member("agent-2") is True
        assert "agent-2" not in empty_space.members

    def test_remove_nonexistent_member(self, empty_space: Space) -> None:
        assert empty_space.remove_member("agent-99") is False


# --- Context Management Tests ---


class TestContextManagement:
    def test_add_context(self, empty_space: Space, sample_item: ContextItem) -> None:
        empty_space.add_context(sample_item)
        assert len(empty_space.context_items) == 1

    def test_get_by_type(self, populated_space: Space) -> None:
        files = populated_space.get_context_by_type(ContextItemType.FILE)
        assert len(files) == 1
        assert files[0].title == "app.py"

    def test_get_by_type_no_match(self, populated_space: Space) -> None:
        sessions = populated_space.get_context_by_type(ContextItemType.SESSION)
        assert sessions == []

    def test_get_by_agent(self, populated_space: Space) -> None:
        items = populated_space.get_context_by_agent("agent-1")
        assert len(items) == 2

    def test_get_by_agent_no_match(self, populated_space: Space) -> None:
        items = populated_space.get_context_by_agent("agent-99")
        assert items == []

    def test_get_by_tag(self, populated_space: Space) -> None:
        items = populated_space.get_context_by_tag("bugfix")
        assert len(items) == 1
        assert items[0].title == "PR #5"

    def test_get_by_tag_no_match(self, populated_space: Space) -> None:
        items = populated_space.get_context_by_tag("nonexistent")
        assert items == []

    def test_search_context_title(self, populated_space: Space) -> None:
        results = populated_space.search_context("PR #5")
        assert len(results) == 1

    def test_search_context_content(self, populated_space: Space) -> None:
        results = populated_space.search_context("async")
        assert len(results) == 1
        assert results[0].title == "Architecture"

    def test_search_case_insensitive(self, populated_space: Space) -> None:
        results = populated_space.search_context("crash")
        assert len(results) == 1

    def test_search_no_results(self, populated_space: Space) -> None:
        results = populated_space.search_context("zzzzz")
        assert results == []


# --- Space Serialization Tests ---


class TestSpaceSerialization:
    def test_to_dict(self, populated_space: Space) -> None:
        d = populated_space.to_dict()
        assert d["name"] == "Populated"
        assert d["visibility"] == "private"
        assert len(d["context_items"]) == 4
        assert d["owner_id"] == "agent-1"

    def test_to_dict_empty(self, empty_space: Space) -> None:
        d = empty_space.to_dict()
        assert d["context_items"] == []


# --- Merge Tests ---


class TestMergeSpaces:
    def test_merge_adds_items(self) -> None:
        target = create_space("Target", owner_id="a-1")
        source = create_space("Source", owner_id="a-2")
        item = create_context_item(ContextItemType.NOTE, "Note", "text", "a-2")
        source.add_context(item)

        added = merge_spaces(target, source)
        assert added == 1
        assert len(target.context_items) == 1

    def test_merge_skips_duplicates(self) -> None:
        target = create_space("Target")
        source = create_space("Source")
        item = create_context_item(ContextItemType.NOTE, "Note", "text", "a-1")
        target.add_context(item)
        source.add_context(item)

        added = merge_spaces(target, source)
        assert added == 0
        assert len(target.context_items) == 1

    def test_merge_adds_members(self) -> None:
        target = create_space("Target", owner_id="a-1")
        source = create_space("Source", owner_id="a-2")

        merge_spaces(target, source)
        assert "a-2" in target.members

    def test_merge_no_duplicate_members(self) -> None:
        target = create_space("Target", owner_id="a-1")
        source = create_space("Source", owner_id="a-1")

        merge_spaces(target, source)
        assert target.members.count("a-1") == 1


# --- Filter Tests ---


class TestFilterContextSince:
    def test_filters_by_time(self) -> None:
        space = create_space("Test")
        before = time.time()
        old_item = ContextItem(
            item_id="old-1",
            item_type=ContextItemType.NOTE,
            title="Old",
            content="old",
            source_agent_id="a-1",
            created_at=before - 100,
        )
        new_item = create_context_item(ContextItemType.NOTE, "New", "new", "a-1")
        space.add_context(old_item)
        space.add_context(new_item)

        recent = filter_context_since(space, before - 1)
        assert len(recent) == 1
        assert recent[0].title == "New"


# --- Summarize Tests ---


class TestSummarizeSpace:
    def test_summary(self, populated_space: Space) -> None:
        summary = summarize_space(populated_space)
        assert summary["name"] == "Populated"
        assert summary["context_item_count"] == 4
        assert summary["member_count"] >= 1
        assert "file" in summary["context_by_type"]
        assert summary["context_by_type"]["file"] == 1
        assert summary["context_by_type"]["pull_request"] == 1

    def test_summary_empty(self, empty_space: Space) -> None:
        summary = summarize_space(empty_space)
        assert summary["context_item_count"] == 0
        assert summary["context_by_type"] == {}


# --- Enum Coverage ---


class TestEnums:
    def test_context_item_types(self) -> None:
        assert len(ContextItemType) == 7

    def test_space_visibility(self) -> None:
        assert SpaceVisibility.PRIVATE.value == "private"
        assert SpaceVisibility.TEAM.value == "team"
        assert SpaceVisibility.PUBLIC.value == "public"
