"""Tests for the comment parser module."""

from __future__ import annotations

from opencode_github.comment_parser import ParsedCommand, is_trigger, parse_command


class TestParseCommand:
    def test_oc_trigger(self) -> None:
        result = parse_command("/oc fix the bug")
        assert result == ParsedCommand(trigger="/oc", arguments="fix the bug")

    def test_opencode_trigger(self) -> None:
        result = parse_command("/opencode refactor this")
        assert result == ParsedCommand(trigger="/opencode", arguments="refactor this")

    def test_trigger_without_args(self) -> None:
        result = parse_command("/oc")
        assert result == ParsedCommand(trigger="/oc", arguments="")

    def test_trigger_in_multiline(self) -> None:
        body = "Some context\n/oc do something\nmore text"
        result = parse_command(body)
        assert result is not None
        assert result.trigger == "/oc"
        assert result.arguments == "do something"

    def test_no_trigger(self) -> None:
        assert parse_command("just a normal comment") is None

    def test_empty_body(self) -> None:
        assert parse_command("") is None
        assert parse_command("   ") is None

    def test_trigger_not_at_start_of_line(self) -> None:
        assert parse_command("inline /oc command") is None

    def test_partial_trigger_rejected(self) -> None:
        assert parse_command("/ocean is not a command") is None


class TestIsTrigger:
    def test_true_for_valid(self) -> None:
        assert is_trigger("/oc hello") is True

    def test_false_for_invalid(self) -> None:
        assert is_trigger("no command here") is False
