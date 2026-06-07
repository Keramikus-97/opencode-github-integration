"""Gamified learning module for critical analysis of technical documentation.

Provides tools to identify hidden assumptions in text, score analysis quality,
and wrap the experience in a gamified progression system with XP and levels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class DifficultyLevel(Enum):
    """Challenge difficulty tiers."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class AssumptionCategory(Enum):
    """Categories for identified assumptions."""

    TECHNICAL = "technical"
    IMPLICIT_COMPARISON = "implicit_comparison"
    AUDIENCE = "audience"
    CAUSAL = "causal"
    SCOPE = "scope"
    AUTHORITY = "authority"


@dataclass(frozen=True)
class Assumption:
    """A single assumption identified in a text passage."""

    statement: str
    category: AssumptionCategory
    evidence: str
    impact_on_argument: str
    confidence: float  # 0.0 to 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            object.__setattr__(self, "confidence", max(0.0, min(1.0, self.confidence)))


@dataclass(frozen=True)
class AnalysisResult:
    """Complete analysis result with scoring."""

    source_text: str
    assumptions: list[Assumption]
    total_score: int
    evidence_quality_score: int
    impact_assessment_score: int
    categorization_score: int
    feedback: str


@dataclass
class LearnerProfile:
    """Tracks a learner's progress through the gamified system."""

    user_id: str
    xp: int = 0
    level: int = 1
    challenges_completed: int = 0
    streak: int = 0
    badges: list[str] = field(default_factory=list)

    @property
    def xp_for_next_level(self) -> int:
        """XP required to reach the next level."""
        return self.level * 100

    @property
    def xp_progress(self) -> float:
        """Progress toward the next level as a fraction (0.0 to 1.0)."""
        required = self.xp_for_next_level
        current_level_xp = self.xp - sum(i * 100 for i in range(1, self.level))
        return min(1.0, max(0.0, current_level_xp / required))

    def add_xp(self, amount: int) -> list[str]:
        """Award XP and return any newly earned badges/level-ups."""
        events: list[str] = []
        self.xp += amount

        xp_threshold = sum(i * 100 for i in range(1, self.level + 1))
        while self.xp >= xp_threshold:
            self.level += 1
            events.append(f"level_up:{self.level}")
            xp_threshold += self.level * 100

        return events


@dataclass(frozen=True)
class LearningChallenge:
    """A gamified challenge wrapping a text analysis task."""

    challenge_id: str
    title: str
    description: str
    source_text: str
    difficulty: DifficultyLevel
    xp_reward: int
    hints: list[str] = field(default_factory=list)
    time_limit_seconds: int | None = None


# --- Scoring Constants ---

_CATEGORY_WEIGHTS: dict[AssumptionCategory, int] = {
    AssumptionCategory.TECHNICAL: 15,
    AssumptionCategory.IMPLICIT_COMPARISON: 20,
    AssumptionCategory.AUDIENCE: 10,
    AssumptionCategory.CAUSAL: 25,
    AssumptionCategory.SCOPE: 15,
    AssumptionCategory.AUTHORITY: 15,
}

_DIFFICULTY_XP: dict[DifficultyLevel, int] = {
    DifficultyLevel.BEGINNER: 25,
    DifficultyLevel.INTERMEDIATE: 50,
    DifficultyLevel.ADVANCED: 100,
    DifficultyLevel.EXPERT: 200,
}

_BADGE_THRESHOLDS: dict[str, int] = {
    "first_analysis": 1,
    "assumption_hunter": 10,
    "critical_thinker": 25,
    "master_analyst": 50,
    "documentation_sage": 100,
}


def estimate_difficulty(text: str) -> DifficultyLevel:
    """Estimate the difficulty of analyzing a text passage.

    Heuristics based on text length, sentence complexity, and technical
    vocabulary density.
    """
    words = text.split()
    word_count = len(words)
    sentence_count = max(1, len(re.findall(r"[.!?]+", text)))
    avg_sentence_length = word_count / sentence_count

    technical_pattern = re.compile(
        r"\b(api|sdk|plugin|framework|runtime|async|protocol|"
        r"architecture|implementation|integration|configuration)\b",
        re.IGNORECASE,
    )
    technical_density = len(technical_pattern.findall(text)) / max(1, word_count) * 100

    score = 0
    if word_count > 500:
        score += 2
    elif word_count > 200:
        score += 1

    if avg_sentence_length > 25:
        score += 2
    elif avg_sentence_length > 15:
        score += 1

    if technical_density > 5:
        score += 2
    elif technical_density > 2:
        score += 1

    if score >= 5:
        return DifficultyLevel.EXPERT
    elif score >= 3:
        return DifficultyLevel.ADVANCED
    elif score >= 2:
        return DifficultyLevel.INTERMEDIATE
    return DifficultyLevel.BEGINNER


def identify_assumption_indicators(text: str) -> list[str]:
    """Find textual indicators that suggest hidden assumptions.

    Returns phrases/sentences that contain assumption signals such as
    comparatives without evidence, implicit recommendations, or
    unsubstantiated claims.
    """
    indicators: list[str] = []

    patterns = [
        (r"(?:strongly\s+)?recommend", "recommendation without comparison data"),
        (r"(?:superior|better|best|advanced|cutting-edge)", "comparative/superlative claim"),
        (r"(?:must|need to|required|should)\s+use", "prescriptive requirement"),
        (r"(?:does not|doesn't|won't|will not)\s+(?:include|support|receive)", "exclusion claim"),
        (r"maintenance\s+mode", "deprecation/status assumption"),
        (r"(?:all|every|always|never|none)", "universal quantifier"),
    ]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        for pattern, label in patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                indicators.append(f"[{label}] {sentence.strip()}")
                break

    return indicators


def score_assumption(assumption: Assumption) -> int:
    """Score a single assumption based on quality metrics."""
    score = 0

    category_weight = _CATEGORY_WEIGHTS.get(assumption.category, 10)
    score += category_weight

    if assumption.evidence and len(assumption.evidence) > 20:
        score += 15
    elif assumption.evidence:
        score += 5

    if assumption.impact_on_argument and len(assumption.impact_on_argument) > 20:
        score += 15
    elif assumption.impact_on_argument:
        score += 5

    confidence_bonus = int(assumption.confidence * 10)
    score += confidence_bonus

    return score


def score_analysis(assumptions: list[Assumption], source_text: str) -> AnalysisResult:
    """Score a complete set of assumptions identified in a text.

    Returns an AnalysisResult with detailed scoring breakdown.
    """
    if not assumptions:
        return AnalysisResult(
            source_text=source_text,
            assumptions=[],
            total_score=0,
            evidence_quality_score=0,
            impact_assessment_score=0,
            categorization_score=0,
            feedback="No assumptions were identified. Try looking for implicit claims, "
            "unstated comparisons, or prescriptive language.",
        )

    evidence_scores: list[int] = []
    impact_scores: list[int] = []
    category_scores: list[int] = []

    for assumption in assumptions:
        if assumption.evidence and len(assumption.evidence) > 20:
            evidence_scores.append(20)
        elif assumption.evidence:
            evidence_scores.append(10)
        else:
            evidence_scores.append(0)

        if assumption.impact_on_argument and len(assumption.impact_on_argument) > 20:
            impact_scores.append(20)
        elif assumption.impact_on_argument:
            impact_scores.append(10)
        else:
            impact_scores.append(0)

        category_scores.append(_CATEGORY_WEIGHTS.get(assumption.category, 10))

    evidence_quality = sum(evidence_scores) // max(1, len(evidence_scores))
    impact_assessment = sum(impact_scores) // max(1, len(impact_scores))
    categorization = sum(category_scores) // max(1, len(category_scores))
    total = sum(score_assumption(a) for a in assumptions)

    categories_used = {a.category for a in assumptions}
    diversity_bonus = len(categories_used) * 5
    total += diversity_bonus

    if len(assumptions) >= 4:
        feedback = "Excellent analysis! You identified multiple assumptions across categories."
    elif len(assumptions) >= 2:
        feedback = "Good work! Consider looking for additional assumption types."
    else:
        feedback = "Solid start. Try identifying more implicit claims and hidden comparisons."

    return AnalysisResult(
        source_text=source_text,
        assumptions=assumptions,
        total_score=total,
        evidence_quality_score=evidence_quality,
        impact_assessment_score=impact_assessment,
        categorization_score=categorization,
        feedback=feedback,
    )


def create_challenge(
    challenge_id: str,
    title: str,
    source_text: str,
    description: str = "",
    hints: list[str] | None = None,
    time_limit_seconds: int | None = None,
) -> LearningChallenge:
    """Create a new gamified learning challenge from source text."""
    difficulty = estimate_difficulty(source_text)
    xp_reward = _DIFFICULTY_XP[difficulty]

    if not description:
        description = (
            f"Analyze the following text and identify hidden assumptions. "
            f"Difficulty: {difficulty.value}. "
            f"XP Reward: {xp_reward} points."
        )

    return LearningChallenge(
        challenge_id=challenge_id,
        title=title,
        description=description,
        source_text=source_text,
        difficulty=difficulty,
        xp_reward=xp_reward,
        hints=hints or [],
        time_limit_seconds=time_limit_seconds,
    )


def complete_challenge(
    profile: LearnerProfile,
    challenge: LearningChallenge,
    result: AnalysisResult,
) -> tuple[LearnerProfile, list[str]]:
    """Process challenge completion: award XP, check badges, update profile.

    Returns the updated profile and a list of events (level-ups, badges).
    """
    events: list[str] = []

    quality_multiplier = min(2.0, max(0.5, result.total_score / 50.0))
    xp_earned = int(challenge.xp_reward * quality_multiplier)

    level_events = profile.add_xp(xp_earned)
    events.extend(level_events)

    profile.challenges_completed += 1
    profile.streak += 1

    for badge_name, threshold in _BADGE_THRESHOLDS.items():
        if profile.challenges_completed >= threshold and badge_name not in profile.badges:
            profile.badges.append(badge_name)
            events.append(f"badge:{badge_name}")

    if profile.streak >= 5 and "streak_5" not in profile.badges:
        profile.badges.append("streak_5")
        events.append("badge:streak_5")

    return profile, events


def format_analysis_markdown(result: AnalysisResult, locale: str = "en") -> str:
    """Format an analysis result as a markdown table.

    Supports 'en' (English) and 'de' (German) locales for headers.
    """
    if locale == "de":
        headers = ("Annahme", "Detaillierte Analyse")
        evidence_label = "Begründung und unterstützende Beweise"
        impact_label = "Auswirkung auf das Argument"
        score_label = "Gesamtpunktzahl"
        feedback_label = "Rückmeldung"
    else:
        headers = ("Assumption", "Detailed Analysis")
        evidence_label = "Evidence and supporting reasoning"
        impact_label = "Impact on argument"
        score_label = "Total Score"
        feedback_label = "Feedback"

    lines: list[str] = []
    lines.append(f"| {headers[0]} | {headers[1]} |")
    lines.append("| :--- | :--- |")

    for assumption in result.assumptions:
        statement = f"**{assumption.statement}**"
        analysis_parts = [
            f"**{impact_label}:** {assumption.impact_on_argument}",
            f"**{evidence_label}:** {assumption.evidence}",
        ]
        analysis = " ".join(analysis_parts)
        lines.append(f"| {statement} | {analysis} |")

    lines.append("")
    lines.append(f"**{score_label}:** {result.total_score}")
    lines.append(f"**{feedback_label}:** {result.feedback}")

    return "\n".join(lines)


def format_progress_markdown(profile: LearnerProfile, locale: str = "en") -> str:
    """Format learner progress as markdown."""
    if locale == "de":
        lines = [
            f"## Lernfortschritt: {profile.user_id}",
            f"- **Level:** {profile.level}",
            f"- **XP:** {profile.xp}",
            f"- **Abgeschlossene Herausforderungen:** {profile.challenges_completed}",
            f"- **Serie:** {profile.streak}",
        ]
        if profile.badges:
            lines.append(f"- **Abzeichen:** {', '.join(profile.badges)}")
    else:
        lines = [
            f"## Learning Progress: {profile.user_id}",
            f"- **Level:** {profile.level}",
            f"- **XP:** {profile.xp}",
            f"- **Challenges Completed:** {profile.challenges_completed}",
            f"- **Streak:** {profile.streak}",
        ]
        if profile.badges:
            lines.append(f"- **Badges:** {', '.join(profile.badges)}")

    return "\n".join(lines)
