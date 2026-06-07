"""Tests for the gamified learning module."""

from __future__ import annotations

import pytest

from opencode_github.gamified_learning import (
    Assumption,
    AssumptionCategory,
    DifficultyLevel,
    LearnerProfile,
    complete_challenge,
    create_challenge,
    estimate_difficulty,
    format_analysis_markdown,
    format_progress_markdown,
    identify_assumption_indicators,
    score_analysis,
    score_assumption,
)

# --- Fixtures ---


@pytest.fixture
def sample_assumption() -> Assumption:
    return Assumption(
        statement="The native editor offers superior AI capabilities",
        category=AssumptionCategory.TECHNICAL,
        evidence="The text claims 'advanced agentic AI capabilities' without benchmarks.",
        impact_on_argument="Central to justifying the recommendation for specific tools.",
        confidence=0.8,
    )


@pytest.fixture
def sample_assumptions() -> list[Assumption]:
    return [
        Assumption(
            statement="The native editor offers superior AI capabilities",
            category=AssumptionCategory.TECHNICAL,
            evidence="The text claims 'advanced agentic AI capabilities' without benchmarks.",
            impact_on_argument="Central to justifying the recommendation for specific tools.",
            confidence=0.8,
        ),
        Assumption(
            statement="Local plugins receive all updates while remote does not",
            category=AssumptionCategory.IMPLICIT_COMPARISON,
            evidence="Text mentions local gets 'latest models, compatibility updates' "
            "but remote only gets 'latest models'.",
            impact_on_argument="Supports the distinction between remote and local plugins.",
            confidence=0.7,
        ),
        Assumption(
            statement="The Remote Development plugin is exclusively for remote environments",
            category=AssumptionCategory.SCOPE,
            evidence="Text instructs: 'For remote development environments, "
            "use the separate plugin'.",
            impact_on_argument="Necessary to separate installation guides by context.",
            confidence=0.9,
        ),
        Assumption(
            statement="'Agentic AI capabilities' is a clear term for the audience",
            category=AssumptionCategory.AUDIENCE,
            evidence="No definition or examples provided for what 'agentic AI' means.",
            impact_on_argument="If the audience doesn't understand the term, "
            "the recommendation loses persuasive power.",
            confidence=0.6,
        ),
    ]


@pytest.fixture
def simple_text() -> str:
    return "This is a simple text with basic words."


@pytest.fixture
def technical_text() -> str:
    return (
        "We strongly recommend using the native Windsurf Editor or the JetBrains "
        "local plugin for their advanced agentic AI capabilities and cutting-edge features. "
        "The plugins below are in maintenance mode. For remote development environments, "
        "you need to use the separate 'Windsurf (Remote Development)' plugin. "
        "This plugin continues to receive the latest models, compatibility updates, "
        "and bug fixes, but does not include newer features exclusive to the Windsurf Editor. "
        "The native editor provides superior integration with API services, SDK tooling, "
        "and framework support through its runtime architecture. The async protocol "
        "implementation enables real-time configuration of the development environment."
    )


@pytest.fixture
def learner_profile() -> LearnerProfile:
    return LearnerProfile(user_id="test-user-123")


# --- Assumption Tests ---


class TestAssumption:
    def test_creation(self, sample_assumption: Assumption) -> None:
        assert sample_assumption.statement == "The native editor offers superior AI capabilities"
        assert sample_assumption.category == AssumptionCategory.TECHNICAL
        assert sample_assumption.confidence == 0.8

    def test_confidence_clamping_high(self) -> None:
        a = Assumption(
            statement="test",
            category=AssumptionCategory.TECHNICAL,
            evidence="evidence",
            impact_on_argument="impact",
            confidence=1.5,
        )
        assert a.confidence == 1.0

    def test_confidence_clamping_low(self) -> None:
        a = Assumption(
            statement="test",
            category=AssumptionCategory.TECHNICAL,
            evidence="evidence",
            impact_on_argument="impact",
            confidence=-0.5,
        )
        assert a.confidence == 0.0

    def test_confidence_valid_range(self) -> None:
        a = Assumption(
            statement="test",
            category=AssumptionCategory.CAUSAL,
            evidence="ev",
            impact_on_argument="imp",
            confidence=0.5,
        )
        assert a.confidence == 0.5

    def test_frozen(self, sample_assumption: Assumption) -> None:
        with pytest.raises(AttributeError):
            sample_assumption.statement = "changed"  # type: ignore[misc]


# --- DifficultyLevel Tests ---


class TestEstimateDifficulty:
    def test_short_simple_text(self, simple_text: str) -> None:
        difficulty = estimate_difficulty(simple_text)
        assert difficulty == DifficultyLevel.BEGINNER

    def test_long_technical_text(self, technical_text: str) -> None:
        difficulty = estimate_difficulty(technical_text)
        assert difficulty in (
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        )

    def test_medium_text(self) -> None:
        text = " ".join(["The system uses an API to integrate plugins."] * 15)
        difficulty = estimate_difficulty(text)
        assert difficulty in (
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
        )

    def test_empty_text(self) -> None:
        difficulty = estimate_difficulty("")
        assert difficulty == DifficultyLevel.BEGINNER

    def test_very_long_complex_text(self) -> None:
        text = (
            "The framework architecture relies on async protocol implementation "
            "with SDK integration and runtime configuration and the API plugin "
            "requires the async protocol for advanced framework integration. "
        ) * 50
        difficulty = estimate_difficulty(text)
        assert difficulty == DifficultyLevel.EXPERT


# --- Indicator Detection Tests ---


class TestIdentifyAssumptionIndicators:
    def test_finds_recommendation(self) -> None:
        text = "We strongly recommend using the native editor."
        indicators = identify_assumption_indicators(text)
        assert len(indicators) >= 1
        assert any("recommendation" in i for i in indicators)

    def test_finds_comparative(self) -> None:
        text = "The plugin offers superior capabilities compared to others."
        indicators = identify_assumption_indicators(text)
        assert len(indicators) >= 1
        assert any("comparative" in i for i in indicators)

    def test_finds_prescriptive(self) -> None:
        text = "You must use the remote plugin for this setup."
        indicators = identify_assumption_indicators(text)
        assert len(indicators) >= 1
        assert any("prescriptive" in i for i in indicators)

    def test_finds_exclusion(self) -> None:
        text = "This version does not include newer features."
        indicators = identify_assumption_indicators(text)
        assert len(indicators) >= 1
        assert any("exclusion" in i for i in indicators)

    def test_finds_maintenance_mode(self) -> None:
        text = "The plugins below are in maintenance mode."
        indicators = identify_assumption_indicators(text)
        assert len(indicators) >= 1
        assert any("deprecation" in i for i in indicators)

    def test_empty_text(self) -> None:
        indicators = identify_assumption_indicators("")
        assert indicators == []

    def test_no_indicators(self) -> None:
        text = "The sky is blue today."
        indicators = identify_assumption_indicators(text)
        assert indicators == []

    def test_multiple_indicators(self, technical_text: str) -> None:
        indicators = identify_assumption_indicators(technical_text)
        assert len(indicators) >= 3


# --- Scoring Tests ---


class TestScoreAssumption:
    def test_high_quality_assumption(self, sample_assumption: Assumption) -> None:
        score = score_assumption(sample_assumption)
        assert score > 30

    def test_minimal_assumption(self) -> None:
        a = Assumption(
            statement="test",
            category=AssumptionCategory.TECHNICAL,
            evidence="",
            impact_on_argument="",
            confidence=0.0,
        )
        score = score_assumption(a)
        assert score == 15  # just category weight

    def test_high_confidence_bonus(self) -> None:
        a = Assumption(
            statement="test",
            category=AssumptionCategory.TECHNICAL,
            evidence="detailed evidence with explanation",
            impact_on_argument="significant impact on the conclusion",
            confidence=1.0,
        )
        score = score_assumption(a)
        assert score >= 55

    def test_category_weights_differ(self) -> None:
        base = dict(
            statement="test",
            evidence="long evidence for scoring",
            impact_on_argument="long impact assessment",
            confidence=0.5,
        )
        causal = score_assumption(Assumption(category=AssumptionCategory.CAUSAL, **base))
        audience = score_assumption(Assumption(category=AssumptionCategory.AUDIENCE, **base))
        assert causal > audience


class TestScoreAnalysis:
    def test_empty_assumptions(self, simple_text: str) -> None:
        result = score_analysis([], simple_text)
        assert result.total_score == 0
        assert "No assumptions" in result.feedback

    def test_single_assumption(self, sample_assumption: Assumption) -> None:
        result = score_analysis([sample_assumption], "source text")
        assert result.total_score > 0
        assert len(result.assumptions) == 1

    def test_multiple_assumptions(self, sample_assumptions: list[Assumption]) -> None:
        result = score_analysis(sample_assumptions, "source text")
        assert result.total_score > 0
        assert len(result.assumptions) == 4
        assert "Excellent" in result.feedback

    def test_diversity_bonus(self) -> None:
        assumptions = [
            Assumption(
                statement="a",
                category=AssumptionCategory.TECHNICAL,
                evidence="long evidence text here",
                impact_on_argument="long impact text here",
                confidence=0.8,
            ),
            Assumption(
                statement="b",
                category=AssumptionCategory.CAUSAL,
                evidence="long evidence text here",
                impact_on_argument="long impact text here",
                confidence=0.8,
            ),
        ]
        result = score_analysis(assumptions, "text")
        # With 2 categories, diversity bonus = 10
        single_result = score_analysis([assumptions[0]], "text")
        # Single category diversity bonus = 5
        assert result.total_score > single_result.total_score

    def test_evidence_quality_score(self, sample_assumptions: list[Assumption]) -> None:
        result = score_analysis(sample_assumptions, "text")
        assert result.evidence_quality_score > 0

    def test_two_assumptions_feedback(self) -> None:
        assumptions = [
            Assumption(
                statement="a",
                category=AssumptionCategory.TECHNICAL,
                evidence="ev",
                impact_on_argument="imp",
                confidence=0.5,
            ),
            Assumption(
                statement="b",
                category=AssumptionCategory.SCOPE,
                evidence="ev",
                impact_on_argument="imp",
                confidence=0.5,
            ),
        ]
        result = score_analysis(assumptions, "text")
        assert "Good work" in result.feedback


# --- Challenge Tests ---


class TestCreateChallenge:
    def test_basic_creation(self, simple_text: str) -> None:
        challenge = create_challenge(
            challenge_id="ch-001",
            title="Analyze Plugin Docs",
            source_text=simple_text,
        )
        assert challenge.challenge_id == "ch-001"
        assert challenge.title == "Analyze Plugin Docs"
        assert challenge.difficulty == DifficultyLevel.BEGINNER
        assert challenge.xp_reward == 25

    def test_technical_text_difficulty(self, technical_text: str) -> None:
        challenge = create_challenge(
            challenge_id="ch-002",
            title="Advanced Analysis",
            source_text=technical_text,
        )
        assert challenge.difficulty in (
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        )
        assert challenge.xp_reward >= 100

    def test_custom_description(self, simple_text: str) -> None:
        challenge = create_challenge(
            challenge_id="ch-003",
            title="Custom",
            source_text=simple_text,
            description="Custom description here.",
        )
        assert challenge.description == "Custom description here."

    def test_with_hints(self, simple_text: str) -> None:
        hints = ["Look for comparatives", "Check for implicit claims"]
        challenge = create_challenge(
            challenge_id="ch-004",
            title="Hints Test",
            source_text=simple_text,
            hints=hints,
        )
        assert challenge.hints == hints

    def test_with_time_limit(self, simple_text: str) -> None:
        challenge = create_challenge(
            challenge_id="ch-005",
            title="Timed",
            source_text=simple_text,
            time_limit_seconds=300,
        )
        assert challenge.time_limit_seconds == 300


# --- Learner Profile Tests ---


class TestLearnerProfile:
    def test_initial_state(self, learner_profile: LearnerProfile) -> None:
        assert learner_profile.xp == 0
        assert learner_profile.level == 1
        assert learner_profile.challenges_completed == 0
        assert learner_profile.streak == 0
        assert learner_profile.badges == []

    def test_xp_for_next_level(self, learner_profile: LearnerProfile) -> None:
        assert learner_profile.xp_for_next_level == 100

    def test_xp_progress_zero(self, learner_profile: LearnerProfile) -> None:
        assert learner_profile.xp_progress == 0.0

    def test_add_xp_no_level_up(self, learner_profile: LearnerProfile) -> None:
        events = learner_profile.add_xp(50)
        assert learner_profile.xp == 50
        assert learner_profile.level == 1
        assert events == []

    def test_add_xp_level_up(self, learner_profile: LearnerProfile) -> None:
        events = learner_profile.add_xp(100)
        assert learner_profile.level == 2
        assert "level_up:2" in events

    def test_add_xp_multiple_level_ups(self, learner_profile: LearnerProfile) -> None:
        events = learner_profile.add_xp(300)
        assert learner_profile.level == 3
        assert "level_up:2" in events
        assert "level_up:3" in events

    def test_xp_progress_partial(self, learner_profile: LearnerProfile) -> None:
        learner_profile.add_xp(50)
        assert 0.0 < learner_profile.xp_progress < 1.0


# --- Complete Challenge Tests ---


class TestCompleteChallenge:
    def test_basic_completion(
        self,
        learner_profile: LearnerProfile,
        sample_assumptions: list[Assumption],
        simple_text: str,
    ) -> None:
        challenge = create_challenge("ch-001", "Test", simple_text)
        result = score_analysis(sample_assumptions, simple_text)
        profile, events = complete_challenge(learner_profile, challenge, result)
        assert profile.xp > 0
        assert profile.challenges_completed == 1
        assert profile.streak == 1

    def test_first_analysis_badge(
        self,
        learner_profile: LearnerProfile,
        sample_assumption: Assumption,
        simple_text: str,
    ) -> None:
        challenge = create_challenge("ch-001", "Test", simple_text)
        result = score_analysis([sample_assumption], simple_text)
        profile, events = complete_challenge(learner_profile, challenge, result)
        assert "badge:first_analysis" in events
        assert "first_analysis" in profile.badges

    def test_streak_badge(self, simple_text: str) -> None:
        profile = LearnerProfile(user_id="streaker", streak=4)
        challenge = create_challenge("ch-001", "Test", simple_text)
        assumption = Assumption(
            statement="test",
            category=AssumptionCategory.TECHNICAL,
            evidence="some evidence here for scoring",
            impact_on_argument="some impact here",
            confidence=0.5,
        )
        result = score_analysis([assumption], simple_text)
        profile, events = complete_challenge(profile, challenge, result)
        assert profile.streak == 5
        assert "badge:streak_5" in events

    def test_xp_quality_multiplier(
        self,
        learner_profile: LearnerProfile,
        sample_assumptions: list[Assumption],
        simple_text: str,
    ) -> None:
        challenge = create_challenge("ch-001", "Test", simple_text)
        high_result = score_analysis(sample_assumptions, simple_text)
        low_result = score_analysis([], simple_text)

        profile_high = LearnerProfile(user_id="high")
        profile_low = LearnerProfile(user_id="low")

        complete_challenge(profile_high, challenge, high_result)
        complete_challenge(profile_low, challenge, low_result)

        assert profile_high.xp > profile_low.xp


# --- Markdown Formatting Tests ---


class TestFormatAnalysisMarkdown:
    def test_english_format(self, sample_assumptions: list[Assumption]) -> None:
        result = score_analysis(sample_assumptions, "source text")
        md = format_analysis_markdown(result, locale="en")
        assert "| Assumption | Detailed Analysis |" in md
        assert "| :--- | :--- |" in md
        assert "Total Score" in md
        assert "Feedback" in md

    def test_german_format(self, sample_assumptions: list[Assumption]) -> None:
        result = score_analysis(sample_assumptions, "source text")
        md = format_analysis_markdown(result, locale="de")
        assert "| Annahme | Detaillierte Analyse |" in md
        assert "Gesamtpunktzahl" in md
        assert "Rückmeldung" in md

    def test_empty_result(self) -> None:
        result = score_analysis([], "text")
        md = format_analysis_markdown(result, locale="en")
        assert "Total Score" in md
        assert "0" in md

    def test_contains_assumption_text(self, sample_assumptions: list[Assumption]) -> None:
        result = score_analysis(sample_assumptions, "source text")
        md = format_analysis_markdown(result, locale="en")
        assert "native editor offers superior AI capabilities" in md


class TestFormatProgressMarkdown:
    def test_english_format(self, learner_profile: LearnerProfile) -> None:
        md = format_progress_markdown(learner_profile, locale="en")
        assert "## Learning Progress: test-user-123" in md
        assert "**Level:** 1" in md
        assert "**XP:** 0" in md

    def test_german_format(self, learner_profile: LearnerProfile) -> None:
        md = format_progress_markdown(learner_profile, locale="de")
        assert "## Lernfortschritt: test-user-123" in md
        assert "**Level:** 1" in md

    def test_with_badges(self) -> None:
        profile = LearnerProfile(user_id="badger", badges=["first_analysis", "streak_5"])
        md = format_progress_markdown(profile, locale="en")
        assert "Badges" in md
        assert "first_analysis" in md
        assert "streak_5" in md

    def test_german_with_badges(self) -> None:
        profile = LearnerProfile(user_id="badger", badges=["first_analysis"])
        md = format_progress_markdown(profile, locale="de")
        assert "Abzeichen" in md


# --- Integration / End-to-End Tests ---


class TestEndToEnd:
    def test_full_workflow(self, technical_text: str) -> None:
        """Simulate a complete gamified learning workflow."""
        # 1. Create a challenge
        challenge = create_challenge(
            challenge_id="e2e-001",
            title="Analyze Windsurf Plugin Documentation",
            source_text=technical_text,
            hints=["Look for words like 'superior', 'recommend'"],
        )
        assert challenge.difficulty in (
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        )

        # 2. Identify indicators
        indicators = identify_assumption_indicators(technical_text)
        assert len(indicators) > 0

        # 3. Create assumptions based on analysis
        assumptions = [
            Assumption(
                statement="The native editor provides superior capabilities",
                category=AssumptionCategory.IMPLICIT_COMPARISON,
                evidence="Text uses 'superior' and 'advanced' without comparative data.",
                impact_on_argument="Justifies the recommendation hierarchy.",
                confidence=0.85,
            ),
            Assumption(
                statement="Remote plugin is incomplete compared to local",
                category=AssumptionCategory.TECHNICAL,
                evidence="Text says remote 'does not include newer features'.",
                impact_on_argument="Creates urgency to use local plugins.",
                confidence=0.9,
            ),
        ]

        # 4. Score the analysis
        result = score_analysis(assumptions, technical_text)
        assert result.total_score > 0
        assert result.evidence_quality_score > 0

        # 5. Complete the challenge
        profile = LearnerProfile(user_id="e2e-tester")
        profile, events = complete_challenge(profile, challenge, result)
        assert profile.xp > 0
        assert profile.challenges_completed == 1
        assert "badge:first_analysis" in events

        # 6. Format output
        md = format_analysis_markdown(result, locale="de")
        assert "Annahme" in md
        assert "Detaillierte Analyse" in md

        progress_md = format_progress_markdown(profile, locale="de")
        assert "Lernfortschritt" in progress_md
