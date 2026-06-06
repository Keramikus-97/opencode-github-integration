"""Tests for opencode_github.comment_parser."""

from __future__ import annotations

from opencode_github.comment_parser import (
    extract_commands,
    is_command_comment,
    split_arguments,
)

TRIGGERS = ["/oc", "/opencode"]


class TestExtractCommands:
    def test_single_command(self) -> None:
        cmds = extract_commands("/oc fix typo", TRIGGERS)
        assert len(cmds) == 1
        assert cmds[0].trigger == "/oc"
        assert cmds[0].arguments == "fix typo"

    def test_multiple_commands(self) -> None:
        body = "/oc first\nsome text\n/opencode second"
        cmds = extract_commands(body, TRIGGERS)
        assert len(cmds) == 2
        assert cmds[0].trigger == "/oc"
        assert cmds[0].arguments == "first"
        assert cmds[1].trigger == "/opencode"
        assert cmds[1].arguments == "second"

    def test_leading_whitespace(self) -> None:
        cmds = extract_commands("   /oc do something", TRIGGERS)
        assert len(cmds) == 1
        assert cmds[0].arguments == "do something"

    def test_no_match(self) -> None:
        assert extract_commands("just a regular comment", TRIGGERS) == []

    def test_empty_body(self) -> None:
        assert extract_commands("", TRIGGERS) == []

    def test_empty_triggers(self) -> None:
        assert extract_commands("/oc hello", []) == []

    def test_command_without_arguments(self) -> None:
        cmds = extract_commands("/oc", TRIGGERS)
        assert len(cmds) == 1
        assert cmds[0].arguments == ""

    def test_mid_line_trigger_not_matched(self) -> None:
        """Triggers must be at the start of a line."""
        assert extract_commands("please /oc fix it", TRIGGERS) == []

    def test_raw_body_preserved(self) -> None:
        body = "/oc hello world"
        cmds = extract_commands(body, TRIGGERS)
        assert cmds[0].raw_body is body

    def test_longer_trigger_matched_first(self) -> None:
        body = "/opencode run"
        cmds = extract_commands(body, TRIGGERS)
        assert cmds[0].trigger == "/opencode"

    def test_trigger_prefix_not_partial_word(self) -> None:
        """/ocean should NOT match /oc."""
        assert extract_commands("/ocean voyage", TRIGGERS) == []


class TestIsCommandComment:
    def test_true_for_matching(self) -> None:
        assert is_command_comment("/oc hi", TRIGGERS) is True

    def test_false_for_no_match(self) -> None:
        assert is_command_comment("nothing here", TRIGGERS) is False

    def test_false_for_empty(self) -> None:
        assert is_command_comment("", TRIGGERS) is False


class TestSplitArguments:
    def test_simple_tokens(self) -> None:
        assert split_arguments("fix bug --verbose") == ["fix", "bug", "--verbose"]

    def test_quoted_group(self) -> None:
        assert split_arguments('fix "hello world" --fast') == ["fix", "hello world", "--fast"]

    def test_empty_string(self) -> None:
        assert split_arguments("") == []

    def test_only_spaces(self) -> None:
        assert split_arguments("   ") == []

    def test_adjacent_quotes(self) -> None:
        assert split_arguments('"a b" "c d"') == ["a b", "c d"]

    def test_no_quotes(self) -> None:
        assert split_arguments("a b c") == ["a", "b", "c"]
