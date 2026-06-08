"""Spaces – shared context containers for multi-agent collaboration.

A Space groups sessions, PRs, files, and arbitrary context items so that
multiple agents can share a common understanding of a task.  Agents can
publish context into a Space and subscribe to updates from other agents.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContextItemType(Enum):
    """Types of context that can be shared within a Space."""

    FILE = "file"
    PR = "pull_request"
    ISSUE = "issue"
    SESSION = "session"
    SNIPPET = "snippet"
    NOTE = "note"
    METADATA = "metadata"


class SpaceVisibility(Enum):
    """Visibility levels for a Space."""

    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


@dataclass(frozen=True)
class ContextItem:
    """A single piece of context shared within a Space."""

    item_id: str
    item_type: ContextItemType
    title: str
    content: str
    source_agent_id: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type.value,
            "title": self.title,
            "content": self.content,
            "source_agent_id": self.source_agent_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "tags": self.tags,
        }


@dataclass
class Space:
    """A shared context container for grouping related work."""

    space_id: str
    name: str
    description: str
    visibility: SpaceVisibility = SpaceVisibility.PRIVATE
    owner_id: str = ""
    members: list[str] = field(default_factory=list)
    context_items: list[ContextItem] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)

    def add_member(self, agent_id: str) -> bool:
        """Add an agent to this Space.  Returns ``False`` if already a member."""
        if agent_id in self.members:
            return False
        self.members.append(agent_id)
        return True

    def remove_member(self, agent_id: str) -> bool:
        """Remove an agent from this Space.  Returns ``False`` if not found."""
        if agent_id not in self.members:
            return False
        self.members.remove(agent_id)
        return True

    def add_context(self, item: ContextItem) -> None:
        """Publish a context item into this Space."""
        self.context_items.append(item)

    def get_context_by_type(self, item_type: ContextItemType) -> list[ContextItem]:
        """Retrieve all context items of a given type."""
        return [ci for ci in self.context_items if ci.item_type == item_type]

    def get_context_by_agent(self, agent_id: str) -> list[ContextItem]:
        """Retrieve all context items published by a specific agent."""
        return [ci for ci in self.context_items if ci.source_agent_id == agent_id]

    def get_context_by_tag(self, tag: str) -> list[ContextItem]:
        """Retrieve all context items with a specific tag."""
        return [ci for ci in self.context_items if tag in ci.tags]

    def search_context(self, query: str) -> list[ContextItem]:
        """Simple substring search across titles and content."""
        q = query.lower()
        return [ci for ci in self.context_items if q in ci.title.lower() or q in ci.content.lower()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "space_id": self.space_id,
            "name": self.name,
            "description": self.description,
            "visibility": self.visibility.value,
            "owner_id": self.owner_id,
            "members": self.members,
            "context_items": [ci.to_dict() for ci in self.context_items],
            "created_at": self.created_at,
            "tags": self.tags,
        }


def create_space(
    name: str,
    description: str = "",
    owner_id: str = "",
    visibility: SpaceVisibility = SpaceVisibility.PRIVATE,
    tags: list[str] | None = None,
) -> Space:
    """Create a new Space with defaults."""
    space_id = f"space-{uuid.uuid4().hex[:8]}"
    members = [owner_id] if owner_id else []
    return Space(
        space_id=space_id,
        name=name,
        description=description,
        visibility=visibility,
        owner_id=owner_id,
        members=members,
        tags=tags or [],
    )


def create_context_item(
    item_type: ContextItemType,
    title: str,
    content: str,
    source_agent_id: str,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> ContextItem:
    """Create a new context item with a generated ID and timestamp."""
    return ContextItem(
        item_id=f"ctx-{uuid.uuid4().hex[:8]}",
        item_type=item_type,
        title=title,
        content=content,
        source_agent_id=source_agent_id,
        created_at=time.time(),
        metadata=metadata or {},
        tags=tags or [],
    )


def merge_spaces(target: Space, source: Space) -> int:
    """Copy all context items from *source* into *target*.

    Returns the number of items added (duplicates by ``item_id`` are skipped).
    """
    existing_ids = {ci.item_id for ci in target.context_items}
    added = 0
    for item in source.context_items:
        if item.item_id not in existing_ids:
            target.add_context(item)
            existing_ids.add(item.item_id)
            added += 1

    for member in source.members:
        target.add_member(member)

    existing_tags = set(target.tags)
    for tag in source.tags:
        if tag not in existing_tags:
            target.tags.append(tag)
            existing_tags.add(tag)

    return added


def filter_context_since(space: Space, since_timestamp: float) -> list[ContextItem]:
    """Return context items created after *since_timestamp*."""
    return [ci for ci in space.context_items if ci.created_at > since_timestamp]


def summarize_space(space: Space) -> dict[str, Any]:
    """Return a lightweight summary of a Space suitable for display."""
    type_counts: dict[str, int] = {}
    for ci in space.context_items:
        key = ci.item_type.value
        type_counts[key] = type_counts.get(key, 0) + 1

    return {
        "space_id": space.space_id,
        "name": space.name,
        "member_count": len(space.members),
        "context_item_count": len(space.context_items),
        "context_by_type": type_counts,
        "tags": space.tags,
    }
