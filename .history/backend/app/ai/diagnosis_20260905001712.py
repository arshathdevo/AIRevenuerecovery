"""
AI Revenue Recovery - Customer Diagnosis Engine

This module implements the domain-specific intelligence used by the
Revenue Recovery agent.

Design principles
-----------------
1. Normalize messy customer language before classification.
2. Detect problem type independently from customer intent.
3. Treat willingness and delay as separate signals internally.
4. Handle negation locally instead of using naive keyword matching.
5. Detect contradictions and fail safely.
6. Never process or expose sensitive payment credentials.
7. Use deterministic evidence-based reasoning.
8. Keep recovery recommendations conservative.
9. Return useful explanations for merchant/judge audit trails.

This is intentionally NOT an LLM.
It is a domain-specific AI/rule-based reasoning engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from app.models.revenue import (
    AIDiagnosis,
    CustomerIntent,
    ProblemType,
    RecoveryAction,
)


# ============================================================
# 1. TEXT NORMALIZATION
# ============================================================

CONTRACTIONS = {
    "can't": "cannot",
    "cant": "cannot",
    "won't": "will not",
    "wont": "will not",
    "don't": "do not",
    "dont": "do not",
    "doesn't": "does not",
    "doesnt": "does not",
    "didn't": "did not",
    "didnt": "did not",
    "isn't": "is not",
    "isnt": "is not",
    "wasn't": "was not",
    "wasnt": "was not",
    "weren't": "were not",
    "werent": "were not",
    "couldn't": "could not",
    "couldnt": "could not",
    "wouldn't": "would not",
    "wouldnt": "would not",
    "shouldn't": "should not",
    "shouldnt": "should not",
    "haven't": "have not",
    "havent": "have not",
    "hasn't": "has not",
    "hasnt": "has not",
    "hadn't": "had not",
    "hadnt": "had not",
    "i'm": "i am",
    "im": "i am",
    "i'll": "i will",
    "ill": "i will",
    "i'd": "i would",
    "id": "i would",
    "you're": "you are",
    "youre": "you are",
    "you'll": "you will",
    "youll": "you will",
    "you'd": "you would",
    "youd": "you would",
    "it's": "it is",
    "its": "it is",
    "that's": "that is",
    "thats": "that is",
}


def normalize_text(text: str) -> str:
    """
    Normalize customer text while preserving meaningful words.

    Example:
        "I can't PAY!!!" -> "i cannot pay"
    """

    if not text:
        return ""

    text = text.strip().lower()

    # Normalize contractions before punctuation removal.
    for contraction, expansion in CONTRACTIONS.items():
        text = re.sub(
            rf"\b{re.escape(contraction)}\b",
            expansion,
            text,
        )

    # Keep letters/numbers/spaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize(text: str) -> list[str]:
    """Return normalized word tokens."""
    return normalize_text(text).split()


# ============================================================
# 2. SAFETY / SENSITIVE INFORMATION
# ============================================================

# These patterns detect requests or messages involving sensitive
# payment authentication information.
SENSITIVE_PATTERNS = [
    r"\bupi\s+pin\b",
    r"\bpin\s+(?:number|code)?\b",
    r"\botp\b",
    r"\bone\s*time\s+password\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bsecurity\s+code\b",
    r"\bpassword\b",
    r"\bpasscode\b",
    r"\bfull\s+card\s+number\b",
    r"\bcard\s+number\b",
]


# These patterns detect likely credential values.
# We deliberately do not store/expose the matched value.
CREDENTIAL_VALUE_PATTERNS = [
    r"\b\d{4,8}\b",                  # OTP/PIN-like numeric value
    r"\b(?:\d[ -]?){13,19}\b",       # card-like number
]


def contains_sensitive_information(text: str) -> bool:
    """
    Detect whether a message contains sensitive payment/security
    information or references such information.
    """

    normalized = normalize_text(text)

    if not normalized:
        return False

    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    # Numeric credentials are only treated as sensitive when the
    # surrounding context suggests authentication/payment use.
    credential_context = any(
        keyword in normalized
        for keyword in (
            "pin",
            "otp",
            "password",
            "passcode",
            "cvv",
            "cvc",
            "card",
            "verification",
        )
    )

    if credential_context:
        for pattern in CREDENTIAL_VALUE_PATTERNS:
            if re.search(pattern, normalized):
                return True

    return False


def redact_sensitive_information(text: str) -> str:
    """
    Redact sensitive values before storing text in audit logs.

    Example:
        "My OTP is 123456"
        -> "My OTP is [REDACTED]"
    """

    if not text:
        return ""

    redacted = text

    # Redact long card-like numeric sequences first.
    redacted = re.sub(
        r"\b(?:\d[ -]?){13,19}\b",
        "[REDACTED]",
        redacted,
    )

    # Redact values following sensitive labels.
    redacted = re.sub(
        r"(?i)\b(otp|pin|password|passcode|cvv|cvc)"
        r"(\s*(?:is|:|=)?\s*)"
        r"[a-z0-9-]+",
        r"\1 [REDACTED]",
        redacted,
    )

    return redacted


# ============================================================
# 3. EVIDENCE DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class Pattern:
    """
    A domain phrase associated with a classification.

    weight:
        Strength of the evidence.

    priority:
        Tie-breaking priority when two categories have similar scores.
    """

    phrase: str
    weight: float
    priority: int = 0


@dataclass
class Evidence:
    """Evidence collected for one classification category."""

    category: str
    score: float = 0.0
    matches: list[str] = field(default_factory=list)


@dataclass
class DiagnosisAnalysis:
    """
    Rich internal diagnosis result.

    The public AIDiagnosis model is intentionally kept backward
    compatible, while this object contains additional reasoning signals.
    """

    problem_type: ProblemType
    customer_intent: CustomerIntent
    recommended_action: RecoveryAction
    explanation: str

    willingness_to_pay: bool = False
    delay_signal: bool = False
    refusal_signal: bool = False
    contradiction: bool = False
    sensitive: bool = False

    problem_confidence: float = 0.0
    intent_confidence: float = 0.0
    overall_confidence: float = 0.0

    problem_evidence: list[Evidence] = field(default_factory=list)
    intent_evidence: list[Evidence] = field(default_factory=list)


# ============================================================
# 4. DOMAIN KNOWLEDGE
# ============================================================

PROBLEM_PATTERNS: dict[ProblemType, list[Pattern]] = {

    # --------------------------------------------------------
    # TECHNICAL
    # --------------------------------------------------------

    ProblemType.TECHNICAL: [
        Pattern("bank app", 4.0, 5),
        Pattern("bank server", 5.0, 6),
        Pattern("bank server is down", 6.0, 7),
        Pattern("server is down", 5.0, 6),
        Pattern("bank down", 4.5, 5),
        Pattern("payment app not working", 5.0, 6),
        Pattern("app not working", 4.0, 5),
        Pattern("payment failed", 3.5, 4),
        Pattern("payment failure", 3.5, 4),
        Pattern("transaction failed", 3.5, 4),
        Pattern("network problem", 4.0, 5),
        Pattern("poor network", 4.0, 5),
        Pattern("internet problem", 4.0, 5),
        Pattern("internet is slow", 3.5, 4),
        Pattern("network is slow", 3.5, 4),
        Pattern("connection problem", 4.0, 5),
        Pattern("connection failed", 4.0, 5),
        Pattern("timed out", 4.5, 5),
        Pattern("payment timed out", 5.0, 6),
        Pattern("technical issue", 4.0, 5),
        Pattern("technical problem", 4.0, 5),
        Pattern("system error", 4.0, 5),
        Pattern("server error", 4.5, 5),
        Pattern("error while paying", 4.5, 5),
        Pattern("payment error", 4.0, 5),
        Pattern("gateway error", 4.5, 5),
    ],

    # --------------------------------------------------------
    # CHECKOUT ABANDONMENT
    # --------------------------------------------------------

    ProblemType.CHECKOUT_ABANDONMENT: [
        Pattern("forgot to complete", 6.0, 7),
        Pattern("forgot to finish", 6.0, 7),
        Pattern("did not complete", 5.0, 6),
        Pattern("did not finish", 5.0, 6),
        Pattern("closed the payment page", 6.0, 7),
        Pattern("closed payment page", 6.0, 7),
        Pattern("closed the page", 4.5, 5),
        Pattern("closed payment", 4.5, 5),
        Pattern("left the payment page", 4.5, 5),
        Pattern("left payment page", 4.5, 5),
        Pattern("abandoned checkout", 6.0, 7),
        Pattern("abandoned payment", 5.0, 6),
        Pattern("forgot payment", 4.0, 5),
        Pattern("forgot to pay", 4.0, 5),
        Pattern("payment page closed", 5.5, 6),
        Pattern("did not finish payment", 5.5, 6),
    ],

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    ProblemType.FINANCIAL: [
        Pattern("not enough money", 7.0, 8),
        Pattern("not enough funds", 7.0, 8),
        Pattern("insufficient funds", 7.0, 8),
        Pattern("cannot afford", 7.0, 8),
        Pattern("do not have enough money", 7.0, 8),
        Pattern("do not have enough funds", 7.0, 8),
        Pattern("no money", 5.0, 6),
        Pattern("short on money", 6.0, 7),
        Pattern("financial problem", 7.0, 8),
        Pattern("financial difficulty", 7.0, 8),
        Pattern("money problem", 6.0, 7),
        Pattern("salary comes", 5.5, 6),
        Pattern("salary arrives", 5.5, 6),
        Pattern("waiting for salary", 6.0, 7),
        Pattern("cannot pay right now", 6.0, 7),
        Pattern("do not have the money", 6.5, 7),
        Pattern("cannot afford this payment", 7.0, 8),
    ],

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    ProblemType.TIMING: [
        Pattern("pay tomorrow", 6.0, 7),
        Pattern("payment tomorrow", 6.0, 7),
        Pattern("tomorrow", 4.5, 5),
        Pattern("not today", 7.0, 8),
        Pattern("cannot pay today", 7.0, 8),
        Pattern("do not pay today", 6.0, 7),
        Pattern("can pay later", 7.0, 8),
        Pattern("pay later", 6.5, 7),
        Pattern("payment later", 6.0, 7),
        Pattern("later today", 5.0, 6),
        Pattern("next week", 6.0, 7),
        Pattern("next month", 6.0, 7),
        Pattern("in a few days", 6.0, 7),
        Pattern("in a few hours", 6.0, 7),
        Pattern("after a few days", 6.0, 7),
        Pattern("after salary", 6.0, 7),
        Pattern("busy today", 6.0, 7),
        Pattern("not right now", 5.0, 6),
        Pattern("later", 3.5, 4),
    ],

    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    ProblemType.AUTHENTICATION: [
        Pattern("forgot my upi pin", 8.0, 9),
        Pattern("forgot upi pin", 8.0, 9),
        Pattern("forgot my pin", 7.0, 8),
        Pattern("forgot pin", 7.0, 8),
        Pattern("account locked", 8.0, 9),
        Pattern("locked account", 8.0, 9),
        Pattern("cannot log in", 7.0, 8),
        Pattern("cannot login", 7.0, 8),
        Pattern("cannot sign in", 7.0, 8),
        Pattern("forgot password", 7.0, 8),
        Pattern("password problem", 6.0, 7),
        Pattern("authentication failed", 7.0, 8),
        Pattern("verification failed", 6.0, 7),
        Pattern("verification problem", 6.0, 7),
    ],

    # --------------------------------------------------------
    # SECURITY / ACCESS
    # --------------------------------------------------------

    ProblemType.SECURITY_ACCESS: [
        Pattern("phone was stolen", 9.0, 10),
        Pattern("phone stolen", 9.0, 10),
        Pattern("stolen phone", 9.0, 10),
        Pattern("lost my phone", 8.0, 9),
        Pattern("lost phone", 8.0, 9),
        Pattern("phone is lost", 8.0, 9),
        Pattern("cannot access my payment app", 7.0, 8),
        Pattern("cannot access payment app", 7.0, 8),
        Pattern("cannot access my account", 6.5, 7),
        Pattern("security issue", 7.0, 8),
        Pattern("security concern", 7.0, 8),
        Pattern("someone stole", 7.0, 8),
        Pattern("unauthorized access", 9.0, 10),
    ],

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    ProblemType.DISPUTE: [
        Pattern("wrong vendor", 9.0, 10),
        Pattern("wrong merchant", 9.0, 10),
        Pattern("wrong seller", 8.0, 9),
        Pattern("paid the wrong", 8.0, 9),
        Pattern("charged twice", 9.0, 10),
        Pattern("charged me twice", 9.0, 10),
        Pattern("duplicate charge", 9.0, 10),
        Pattern("duplicate payment", 9.0, 10),
        Pattern("do not recognize this payment", 9.0, 10),
        Pattern("do not recognize payment", 9.0, 10),
        Pattern("unrecognized payment", 9.0, 10),
        Pattern("unknown payment", 8.0, 9),
        Pattern("unauthorized payment", 9.0, 10),
        Pattern("dispute payment", 8.0, 9),
        Pattern("payment dispute", 8.0, 9),
        Pattern("refund this payment", 7.0, 8),
    ],
}


# ============================================================
# 5. INTENT KNOWLEDGE
# ============================================================

INTENT_PATTERNS: dict[CustomerIntent, list[Pattern]] = {

    # --------------------------------------------------------
    # WILLINGNESS
    # --------------------------------------------------------

    CustomerIntent.WILLING_TO_PAY: [
        Pattern("i will pay", 6.0, 8),
        Pattern("will pay", 6.0, 8),
        Pattern("i can pay", 6.0, 8),
        Pattern("can pay", 6.0, 8),
        Pattern("i want to pay", 7.0, 9),
        Pattern("want to pay", 7.0, 9),
        Pattern("i wish to pay", 6.0, 8),
        Pattern("wish to pay", 6.0, 8),
        Pattern("i want to complete", 6.0, 8),
        Pattern("want to complete", 6.0, 8),
        Pattern("i will try again", 6.0, 8),
        Pattern("try again", 5.0, 7),
        Pattern("retry", 5.0, 7),
        Pattern("pay soon", 5.0, 7),
        Pattern("complete the payment", 5.0, 7),
        Pattern("finish the payment", 5.0, 7),
    ],

    # --------------------------------------------------------
    # FINANCIAL DIFFICULTY
    # --------------------------------------------------------

    CustomerIntent.FINANCIAL_DIFFICULTY: [
        Pattern("not enough money", 8.0, 10),
        Pattern("not enough funds", 8.0, 10),
        Pattern("cannot afford", 8.0, 10),
        Pattern("do not have enough money", 8.0, 10),
        Pattern("no money", 7.0, 9),
        Pattern("financial problem", 8.0, 10),
        Pattern("financial difficulty", 8.0, 10),
        Pattern("money problem", 7.0, 9),
        Pattern("cannot pay", 6.0, 8),
        Pattern("do not have the money", 8.0, 10),
        Pattern("waiting for salary", 7.0, 9),
        Pattern("salary comes", 6.0, 8),
    ],

    # --------------------------------------------------------
    # DELAYING PAYMENT
    # --------------------------------------------------------

    CustomerIntent.DELAYING_PAYMENT: [
        Pattern("pay tomorrow", 8.0, 10),
        Pattern("payment tomorrow", 8.0, 10),
        Pattern("not today", 8.0, 10),
        Pattern("can pay later", 8.0, 10),
        Pattern("pay later", 7.0, 9),
        Pattern("payment later", 7.0, 9),
        Pattern("next week", 8.0, 10),
        Pattern("next month", 8.0, 10),
        Pattern("in a few days", 8.0, 10),
        Pattern("in a few hours", 7.0, 9),
        Pattern("after salary", 7.0, 9),
        Pattern("busy today", 7.0, 9),
        Pattern("not right now", 6.0, 8),
        Pattern("later", 4.0, 6),
    ],

    # --------------------------------------------------------
    # SECURITY CONCERN
    # --------------------------------------------------------

    CustomerIntent.SECURITY_CONCERN: [
        Pattern("phone was stolen", 9.0, 10),
        Pattern("phone stolen", 9.0, 10),
        Pattern("lost my phone", 9.0, 10),
        Pattern("lost phone", 9.0, 10),
        Pattern("forgot my upi pin", 9.0, 10),
        Pattern("forgot upi pin", 9.0, 10),
        Pattern("forgot my pin", 8.0, 9),
        Pattern("account locked", 8.0, 9),
        Pattern("security issue", 8.0, 9),
        Pattern("security concern", 8.0, 9),
    ],

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    CustomerIntent.DISPUTE: [
        Pattern("wrong vendor", 10.0, 10),
        Pattern("wrong merchant", 10.0, 10),
        Pattern("paid the wrong", 9.0, 10),
        Pattern("charged twice", 10.0, 10),
        Pattern("duplicate charge", 10.0, 10),
        Pattern("duplicate payment", 10.0, 10),
        Pattern("do not recognize this payment", 10.0, 10),
        Pattern("unrecognized payment", 10.0, 10),
        Pattern("unauthorized payment", 10.0, 10),
        Pattern("payment dispute", 9.0, 10),
    ],
}


# Explicit refusal phrases are deliberately separate from positive
# willingness. This prevents "do not want to pay" from accidentally
# becoming WILLING_TO_PAY.
REFUSAL_PHRASES = [
    "do not want to pay",
    "do not wish to pay",
    "do not want to make the payment",
    "do not wish to make the payment",
    "will not pay",
    "will never pay",
    "refuse to pay",
    "i refuse to pay",
    "not willing to pay",
    "do not want this payment",
]


# ============================================================
# 6. PHRASE MATCHING
# ============================================================

def _find_phrase_occurrences(
    tokens: list[str],
    phrase_tokens: list[str],
) -> list[int]:
    """
    Return starting token indexes where a phrase occurs exactly.
    """

    if not phrase_tokens:
        return []

    occurrences: list[int] = []

    phrase_length = len(phrase_tokens)

    for index in range(len(tokens) - phrase_length + 1):
        if tokens[index:index + phrase_length] == phrase_tokens:
            occurrences.append(index)

    return occurrences


def _is_negated_at(
    tokens: list[str],
    start_index: int,
    window: int = 4,
) -> bool:
    """
    Determine whether evidence immediately before a phrase is negated.

    Example:
        "do not have any problem with my bank app"

    should NOT count "bank app" as technical evidence.
    """

    negations = {
        "not",
        "no",
        "never",
        "without",
        "cannot",
        "cannot",
        "do not",
        "does not",
        "did not",
        "is not",
        "was not",
    }

    start = max(0, start_index - window)

    preceding = tokens[start:start_index]

    if not preceding:
        return False

    # Single-word negations.
    if any(token in negations for token in preceding):
        return True

    # Two-word negation combinations.
    joined = " ".join(preceding)

    for phrase in (
        "do not",
        "does not",
        "did not",
        "is not",
        "was not",
        "will not",
        "cannot",
    ):
        if phrase in joined:
            return True

    return False


def _fuzzy_phrase_match(
    tokens: list[str],
    phrase_tokens: list[str],
    threshold: float = 0.90,
) -> list[int]:
    """
    Conservative fuzzy phrase matching.

    We only use fuzzy matching for phrases with at least two words.
    This prevents short words such as 'pay' or 'later' from producing
    dangerous false positives.
    """

    if len(phrase_tokens) < 2:
        return []

    phrase_text = " ".join(phrase_tokens)
    phrase_length = len(phrase_tokens)

    matches: list[int] = []

    for index in range(len(tokens) - phrase_length + 1):
        candidate = " ".join(
            tokens[index:index + phrase_length]
        )

        similarity = SequenceMatcher(
            None,
            candidate,
            phrase_text,
        ).ratio()

        if similarity >= threshold:
            matches.append(index)

    return matches


# ============================================================
# 7. SCORING
# ============================================================

def _score_group(
    text: str,
    patterns: Iterable[Pattern],
) -> Evidence:
    """
    Score one classification group using exact phrase evidence
    plus conservative fuzzy matching.
    """

    tokens = tokenize(text)

    evidence = Evidence(category="unknown")

    for pattern in patterns:
        phrase_tokens = tokenize(pattern.phrase)

        if not phrase_tokens:
            continue

        occurrences = _find_phrase_occurrences(
            tokens,
            phrase_tokens,
        )

        # Conservative fuzzy fallback.
        if not occurrences:
            occurrences = _fuzzy_phrase_match(
                tokens,
                phrase_tokens,
            )

        for start_index in occurrences:

            # Ignore negated evidence.
            if _is_negated_at(tokens, start_index):
                continue

            evidence.score += pattern.weight

            evidence.matches.append(pattern.phrase)

    return evidence


def score_patterns(
    text: str,
    pattern_groups: dict,
) -> list[Evidence]:
    """
    Score every category in a pattern dictionary.
    """

    results: list[Evidence] = []

    for category, patterns in pattern_groups.items():
        evidence = _score_group(text, patterns)
        evidence.category = category.value
        results.append(evidence)

    return results


def _ranked(
    evidence: list[Evidence],
) -> list[Evidence]:
    """Return evidence sorted by score descending."""

    return sorted(
        evidence,
        key=lambda item: item.score,
        reverse=True,
    )


def get_best_category(
    evidence: list[Evidence],
) -> tuple[str | None, float]:
    """
    Return best category and score.

    If all evidence scores are zero, return None.
    """

    ranked = _ranked(evidence)

    if not ranked or ranked[0].score <= 0:
        return None, 0.0

    return ranked[0].category, ranked[0].score


# ============================================================
# 8. CONFIDENCE
# ============================================================

def _confidence(
    evidence: list[Evidence],
) -> float:
    """
    Convert evidence strength into a bounded confidence value.

    This is not statistical probability.
    It is an interpretable confidence score for the rule engine.
    """

    ranked = _ranked(evidence)

    if not ranked:
        return 0.0

    top = ranked[0].score

    if top <= 0:
        return 0.0

    if top >= 10:
        return 0.98

    if top >= 8:
        return 0.94

    if top >= 6:
        return 0.88

    if top >= 4:
        return 0.78

    if top >= 2:
        return 0.62

    return 0.45


# ============================================================
# 9. SIGNAL DETECTION
# ============================================================

def _contains_any(
    text: str,
    phrases: Iterable[str],
) -> bool:
    """Exact normalized phrase detection."""

    tokens = tokenize(text)

    for phrase in phrases:
        phrase_tokens = tokenize(phrase)

        if not phrase_tokens:
            continue

        occurrences = _find_phrase_occurrences(
            tokens,
            phrase_tokens,
        )

        for start_index in occurrences:
            if not _is_negated_at(tokens, start_index):
                return True

    return False


def _detect_willingness(text: str) -> bool:
    """
    Detect positive willingness independently of delay.
    """

    normalized = normalize_text(text)

    # Explicit refusal must never be treated as willingness.
    if _detect_refusal(normalized):
        # There may still be a contradiction if positive willingness
        # occurs elsewhere. We don't return here because contradiction
        # detection handles that case separately.
        positive_phrases = [
            "i will pay",
            "i can pay",
            "i want to pay",
            "i wish to pay",
            "i will try again",
            "try again",
            "want to complete",
            "want to finish",
        ]

        return _contains_any(normalized, positive_phrases)

    positive_phrases = [
        "i will pay",
        "will pay",
        "i can pay",
        "can pay",
        "i want to pay",
        "want to pay",
        "i wish to pay",
        "wish to pay",
        "i want to complete",
        "want to complete",
        "i will try again",
        "try again",
        "retry",
        "pay soon",
        "complete the payment",
        "finish the payment",
    ]

    return _contains_any(normalized, positive_phrases)


def _detect_delay(text: str) -> bool:
    """
    Detect payment delay independently from willingness.

    This is important because:

        "I will pay tomorrow."

    means both:

        willing = True
        delay = True
    """

    delay_phrases = [
        "pay tomorrow",
        "payment tomorrow",
        "not today",
        "cannot pay today",
        "do not pay today",
        "can pay later",
        "pay later",
        "payment later",
        "later today",
        "next week",
        "next month",
        "in a few days",
        "in a few hours",
        "after a few days",
        "after salary",
        "busy today",
        "not right now",
        "later",
    ]

    return _contains_any(text, delay_phrases)


def _detect_refusal(text: str) -> bool:
    """
    Detect explicit refusal to pay.

    Refusal is intentionally different from financial difficulty.

    Example:

        "I don't want to pay."

    does not tell us that the customer cannot afford it.
    It tells us that willingness is absent/negative.
    """

    normalized = normalize_text(text)

    return _contains_any(
        normalized,
        REFUSAL_PHRASES,
    )


def _detect_contradiction(
    text: str,
    willingness_to_pay: bool,
) -> bool:
    """
    Detect explicit contradictory payment intent.

    Example:

        "I want to pay but I do not want to pay."

    contains both positive and negative intent.
    """

    refusal_signal = _detect_refusal(text)

    return willingness_to_pay and refusal_signal


# ============================================================
# 10. INTENT RESOLUTION
# ============================================================

def _resolve_customer_intent(
    problem_type: ProblemType,
    willingness_to_pay: bool,
    delay_signal: bool,
    refusal_signal: bool,
    intent_evidence: list[Evidence],
) -> CustomerIntent:
    """
    Resolve customer intent using explicit signals first.

    Important:
        willingness and delay are orthogonal internally.

    Public enum remains mutually exclusive, so when both are present,
    DELAYING_PAYMENT wins because it describes the immediate recovery
    state more precisely.

    Safety/problem-specific intents have higher priority.
    """

    # --------------------------------------------------------
    # Dispute has explicit semantic meaning.
    # --------------------------------------------------------

    if problem_type == ProblemType.DISPUTE:
        return CustomerIntent.DISPUTE

    # --------------------------------------------------------
    # Security/access.
    # --------------------------------------------------------

    if problem_type in {
        ProblemType.SECURITY_ACCESS,
        ProblemType.AUTHENTICATION,
    }:
        if problem_type == ProblemType.SECURITY_ACCESS:
            return CustomerIntent.SECURITY_CONCERN

        # Authentication can be either security-related or unknown.
        if any(
            evidence.score > 0
            for evidence in intent_evidence
            if evidence.category == CustomerIntent.SECURITY_CONCERN.value
        ):
            return CustomerIntent.SECURITY_CONCERN

    # --------------------------------------------------------
    # Financial difficulty.
    # --------------------------------------------------------

    if problem_type == ProblemType.FINANCIAL:
        return CustomerIntent.FINANCIAL_DIFFICULTY

    # --------------------------------------------------------
    # Contradictory/refusal state.
    #
    # Contradiction itself is handled by the caller. Here we make
    # explicit refusal remain UNKNOWN rather than pretending the
    # customer is willing.
    # --------------------------------------------------------

    if refusal_signal and not willingness_to_pay:
        return CustomerIntent.UNKNOWN

    # --------------------------------------------------------
    # Delay wins over willingness.
    #
    # "I will pay tomorrow."
    #
    # = willing + delayed
    #
    # Public enum:
    # DELAYING_PAYMENT
    # --------------------------------------------------------

    if delay_signal:
        return CustomerIntent.DELAYING_PAYMENT

    # --------------------------------------------------------
    # Positive willingness.
    # --------------------------------------------------------

    if willingness_to_pay:
        return CustomerIntent.WILLING_TO_PAY

    # --------------------------------------------------------
    # Fall back to strongest explicit intent evidence.
    # --------------------------------------------------------

    ranked = _ranked(intent_evidence)

    if ranked and ranked[0].score > 0:
        try:
            return CustomerIntent(ranked[0].category)
        except ValueError:
            pass

    return CustomerIntent.UNKNOWN


# ============================================================
# 11. RECOVERY POLICY
# ============================================================

def choose_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    *,
    willingness_to_pay: bool = False,
    delay_signal: bool = False,
    contradiction: bool = False,
    sensitive: bool = False,
) -> RecoveryAction:
    """
    Select the safest recovery action.

    Policy order:

        Safety
          ↓
        Dispute
          ↓
        Financial / security
          ↓
        Delay
          ↓
        Technical
          ↓
        Checkout
          ↓
        Willingness
          ↓
        Unknown

    IMPORTANT:
    UNKNOWN does NOT automatically mean HUMAN.

    The problem type provides enough context to safely recover some
    unknown-intent cases.
    """

    # --------------------------------------------------------
    # 1. SAFETY FIRST
    # --------------------------------------------------------

    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    if contradiction:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # 2. DISPUTES
    # --------------------------------------------------------

    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if customer_intent == CustomerIntent.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    # --------------------------------------------------------
    # 3. FINANCIAL DIFFICULTY
    # --------------------------------------------------------

    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.FINANCIAL_DIFFICULTY:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # 4. SECURITY / AUTHENTICATION
    # --------------------------------------------------------

    if problem_type in {
        ProblemType.SECURITY_ACCESS,
        ProblemType.AUTHENTICATION,
    }:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.SECURITY_CONCERN:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # 5. DELAY
    # --------------------------------------------------------

    if delay_signal:
        return RecoveryAction.SCHEDULE_REMINDER

    if customer_intent == CustomerIntent.DELAYING_PAYMENT:
        return RecoveryAction.SCHEDULE_REMINDER

    # --------------------------------------------------------
    # 6. TECHNICAL
    # --------------------------------------------------------

    if problem_type == ProblemType.TECHNICAL:

        if willingness_to_pay:
            return RecoveryAction.OFFER_RETRY

        # Unknown willingness is still recoverable because the
        # problem itself is technical.
        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    # --------------------------------------------------------
    # 7. CHECKOUT ABANDONMENT
    # --------------------------------------------------------

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:

        # Whether willingness is known or not, the safest action is
        # to offer the customer a way to resume the incomplete flow.
        return RecoveryAction.OFFER_RETRY

    # --------------------------------------------------------
    # 8. EXPLICIT WILLINGNESS
    # --------------------------------------------------------

    if customer_intent == CustomerIntent.WILLING_TO_PAY:
        return RecoveryAction.OFFER_RETRY

    # --------------------------------------------------------
    # 9. UNKNOWN EVERYTHING
    # --------------------------------------------------------

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# 12. HUMAN-READABLE EXPLANATION
# ============================================================

def _pretty(value: str) -> str:
    """Convert ENUM-style text into readable text."""

    return value.replace("_", " ").lower()


def build_explanation(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    recommended_action: RecoveryAction,
    *,
    willingness_to_pay: bool,
    delay_signal: bool,
    refusal_signal: bool,
    contradiction: bool,
    sensitive: bool,
    problem_confidence: float,
    intent_confidence: float,
) -> str:
    """
    Build an interpretable explanation suitable for audit logs,
    merchant dashboards, and judge demonstrations.
    """

    if sensitive:
        return (
            "Sensitive payment or authentication information was detected. "
            "The system will not process or expose the credential and "
            "will escalate the case safely."
        )

    if contradiction:
        return (
            "The customer message contains contradictory payment intent. "
            "Automated recovery is paused and the case is escalated "
            "for safe handling."
        )

    if problem_type == ProblemType.DISPUTE:
        return (
            "The message indicates a payment dispute or potentially "
            "unauthorized/incorrect payment. Recovery automation is "
            "stopped to avoid worsening the dispute."
        )

    if problem_type == ProblemType.FINANCIAL:
        return (
            "The customer appears to be experiencing financial difficulty. "
            "Automated payment pressure is avoided and the case is "
            "escalated for appropriate human handling."
        )

    if problem_type in {
        ProblemType.SECURITY_ACCESS,
        ProblemType.AUTHENTICATION,
    }:
        return (
            "The customer appears to have an authentication or "
            "security/access problem. Automated payment recovery is "
            "paused and human assistance is recommended."
        )

    if problem_type == ProblemType.TECHNICAL:

        if willingness_to_pay:
            return (
                "A technical payment problem was detected and the customer "
                "appears willing to pay. A controlled retry is recommended."
            )

        return (
            "A technical payment problem was detected, but customer "
            "willingness is unclear. An alternate approved payment option "
            "is recommended instead of assuming willingness."
        )

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:

        if willingness_to_pay:
            return (
                "The customer appears willing to complete the payment, "
                "but the checkout process was interrupted. A controlled "
                "retry/resume action is recommended."
            )

        return (
            "The payment appears to have been abandoned before completion. "
            "A controlled retry/resume option is recommended."
        )

    if delay_signal:
        return (
            "The customer appears willing to pay but has indicated a "
            "specific delay. A scheduled reminder is recommended."
        )

    if refusal_signal:
        return (
            "The customer has explicitly indicated that they do not want "
            "to pay. Automated recovery is not appropriate without "
            "additional context."
        )

    if customer_intent == CustomerIntent.WILLING_TO_PAY:
        return (
            "The customer appears willing to pay. A controlled retry "
            "or payment continuation is recommended."
        )

    if recommended_action == RecoveryAction.HUMAN_ESCALATION:
        return (
            "The available evidence is insufficient to determine a safe "
            "automated recovery action. The case is escalated."
        )

    return (
        f"Detected {_pretty(problem_type.value)} with "
        f"{_pretty(customer_intent.value)} intent. "
        f"Recommended action: {_pretty(recommended_action.value)}. "
        f"Problem confidence: {problem_confidence:.0%}; "
        f"intent confidence: {intent_confidence:.0%}."
    )


# ============================================================
# 13. MAIN ANALYSIS PIPELINE
# ============================================================

def analyze_message(text: str) -> DiagnosisAnalysis:
    """
    Full diagnosis pipeline.

    Pipeline:

        Raw message
             ↓
        Normalize
             ↓
        Safety detection
             ↓
        Problem evidence
             ↓
        Intent signals
             ↓
        Conflict detection
             ↓
        Intent resolution
             ↓
        Recovery policy
             ↓
        Explanation
    """

    normalized = normalize_text(text)

    # --------------------------------------------------------
    # Empty / unusable message
    # --------------------------------------------------------

    if not normalized:
        action = RecoveryAction.HUMAN_ESCALATION

        return DiagnosisAnalysis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.UNKNOWN,
            recommended_action=action,
            explanation=(
                "No meaningful customer message was provided. "
                "Human handling is required."
            ),
            problem_confidence=0.0,
            intent_confidence=0.0,
            overall_confidence=0.0,
        )

    # --------------------------------------------------------
    # Safety detection
    # --------------------------------------------------------

    sensitive = contains_sensitive_information(normalized)

    # --------------------------------------------------------
    # Problem classification
    # --------------------------------------------------------

    problem_evidence = score_patterns(
        normalized,
        PROBLEM_PATTERNS,
    )

    ranked_problem = _ranked(problem_evidence)

    if ranked_problem and ranked_problem[0].score > 0:

        try:
            problem_type = ProblemType(
                ranked_problem[0].category
            )
        except ValueError:
            problem_type = ProblemType.UNKNOWN

        problem_confidence = _confidence(
            problem_evidence
        )

    else:
        problem_type = ProblemType.UNKNOWN
        problem_confidence = 0.0

    # --------------------------------------------------------
    # Intent evidence
    # --------------------------------------------------------

    intent_evidence = score_patterns(
        normalized,
        INTENT_PATTERNS,
    )

    intent_confidence = _confidence(
        intent_evidence
    )

    # --------------------------------------------------------
    # Explicit semantic signals
    # --------------------------------------------------------

    willingness_to_pay = _detect_willingness(normalized)

    delay_signal = _detect_delay(normalized)

    refusal_signal = _detect_refusal(normalized)

    contradiction = _detect_contradiction(
        normalized,
        willingness_to_pay,
    )

    # --------------------------------------------------------
    # Resolve customer intent
    # --------------------------------------------------------

    customer_intent = _resolve_customer_intent(
        problem_type=problem_type,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        refusal_signal=refusal_signal,
        intent_evidence=intent_evidence,
    )

    # --------------------------------------------------------
    # Special handling for contradiction.
    #
    # A contradictory message should not pretend to have a useful
    # customer intent.
    # --------------------------------------------------------

    if contradiction:
        customer_intent = CustomerIntent.UNKNOWN

    # --------------------------------------------------------
    # Special handling for refusal with no positive intent.
    #
    # Refusal remains UNKNOWN in our current backward-compatible
    # enum model.
    # --------------------------------------------------------

    if refusal_signal and not willingness_to_pay:
        customer_intent = CustomerIntent.UNKNOWN

    # --------------------------------------------------------
    # Recovery policy
    # --------------------------------------------------------

    recommended_action = choose_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        contradiction=contradiction,
        sensitive=sensitive,
    )

    # --------------------------------------------------------
    # Overall confidence
    # --------------------------------------------------------

    if problem_type == ProblemType.UNKNOWN:
        overall_confidence = 0.0

    elif contradiction:
        overall_confidence = 0.0

    else:
        if intent_confidence > 0:
            overall_confidence = (
                problem_confidence * 0.60
                + intent_confidence * 0.40
            )
        else:
            overall_confidence = problem_confidence

    # --------------------------------------------------------
    # Low-confidence safety rule.
    #
    # We only apply this to genuinely ambiguous unknown cases.
    # Known safe technical/checkout problems are allowed to proceed
    # even when customer intent is UNKNOWN.
    # --------------------------------------------------------

    if (
        problem_type == ProblemType.UNKNOWN
        and overall_confidence < 0.45
        and not sensitive
        and not contradiction
    ):
        recommended_action = RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # Explanation
    # --------------------------------------------------------

    explanation = build_explanation(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=recommended_action,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        refusal_signal=refusal_signal,
        contradiction=contradiction,
        sensitive=sensitive,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
    )

    return DiagnosisAnalysis(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=recommended_action,
        explanation=explanation,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        refusal_signal=refusal_signal,
        contradiction=contradiction,
        sensitive=sensitive,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
        overall_confidence=overall_confidence,
        problem_evidence=problem_evidence,
        intent_evidence=intent_evidence,
    )


# ============================================================
# 14. PUBLIC API
# ============================================================

def diagnose_message(text: str) -> AIDiagnosis:
    """
    Public compatibility API.

    Returns the compact Pydantic AIDiagnosis object currently used
    by the FastAPI application and tests.
    """

    analysis = analyze_message(text)

    return AIDiagnosis(
        problem_type=analysis.problem_type,
        customer_intent=analysis.customer_intent,
        recommended_action=analysis.recommended_action,
        explanation=analysis.explanation,
    )


def detect_problem(text: str) -> ProblemType:
    """
    Backward-compatible helper returning only the problem type.
    """

    return analyze_message(text).problem_type