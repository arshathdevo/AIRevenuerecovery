"""
AI Revenue Recovery - Customer Diagnosis Engine

This module implements a deterministic, domain-specific AI layer for
understanding customer messages during payment recovery.

Design principles
-----------------
1. Normalize messy human language.
2. Detect problem type using weighted evidence.
3. Detect customer intent independently.
4. Keep willingness and delay as separate signals internally.
5. Handle negation.
6. Detect contradictory statements.
7. Detect sensitive payment information.
8. Choose a safe recovery action.
9. Never expose sensitive credentials.
10. Prefer safe UNKNOWN over an unsafe guess.

This is intentionally NOT an LLM.
It is a domain-specific reasoning engine that can later evolve into
a learned model using the platform's own recovery data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.models.revenue import (
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
    "aren't": "are not",
    "arent": "are not",
    "wasn't": "was not",
    "wasnt": "was not",
    "weren't": "were not",
    "werent": "were not",
    "i'm": "i am",
    "im": "i am",
    "i'll": "i will",
    "ill": "i will",
    "i've": "i have",
    "ive": "i have",
    "i'd": "i would",
    "id": "i would",
    "you're": "you are",
    "youre": "you are",
    "you'll": "you will",
    "youll": "you will",
    "you've": "you have",
    "youve": "you have",
    "we're": "we are",
    "were": "we are",
    "we'll": "we will",
    "well": "we will",
    "they're": "they are",
    "theyre": "they are",
    "they'll": "they will",
    "theyll": "they will",
}


def normalize_text(text: str) -> str:
    """
    Normalize customer language into a predictable representation.
    """

    if not text:
        return ""

    text = text.lower().strip()

    # Expand contractions before tokenization.
    for contraction, expanded in CONTRACTIONS.items():
        text = re.sub(
            rf"\b{re.escape(contraction)}\b",
            expanded,
            text,
        )

    # Keep letters/numbers but remove punctuation noise.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text: str) -> list[str]:
    return normalize_text(text).split()


# ============================================================
# 2. SAFETY / SENSITIVE INFORMATION
# ============================================================

SENSITIVE_PATTERNS = [
    r"\bupi\s+pin\b",
    r"\bpin\s+number\b",
    r"\bsecurity\s+code\b",
    r"\botp\b",
    r"\bone\s+time\s+password\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bpassword\b",
    r"\bpasscode\b",
    r"\bcard\s+number\b",
    r"\bfull\s+card\b",
]

CREDENTIAL_VALUE_PATTERNS = [
    # 4-6 digit PIN/OTP-like values.
    r"\b\d{4,6}\b",

    # Card-number-like sequence.
    r"\b(?:\d[ -]?){13,19}\b",
]


def contains_sensitive_information(text: str) -> bool:
    normalized = normalize_text(text)

    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    for pattern in CREDENTIAL_VALUE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


def redact_sensitive_information(text: str) -> str:
    """
    Redact likely credential values before audit logging.
    """

    if not text:
        return text

    redacted = text

    for pattern in CREDENTIAL_VALUE_PATTERNS:
        redacted = re.sub(
            pattern,
            "[REDACTED]",
            redacted,
        )

    return redacted


# ============================================================
# 3. EVIDENCE STRUCTURES
# ============================================================

@dataclass
class Pattern:
    phrase: str
    weight: float


@dataclass
class Evidence:
    phrase: str
    weight: float


@dataclass
class DiagnosisAnalysis:
    problem_type: ProblemType
    customer_intent: CustomerIntent
    recommended_action: RecoveryAction

    explanation: str

    # Internal reasoning signals.
    willingness_to_pay: bool
    delay_signal: bool
    contradiction: bool
    sensitive: bool

    # Confidence.
    problem_confidence: float
    intent_confidence: float
    overall_confidence: float


# ============================================================
# 4. PROBLEM KNOWLEDGE BASE
# ============================================================

PROBLEM_PATTERNS: dict[ProblemType, list[Pattern]] = {

    # --------------------------------------------------------
    # TECHNICAL
    # --------------------------------------------------------

    ProblemType.TECHNICAL: [
        Pattern("bank app not working", 5.0),
        Pattern("bank application not working", 5.0),
        Pattern("bank server down", 5.0),
        Pattern("bank server is down", 5.0),
        Pattern("bank server problem", 4.5),
        Pattern("bank issue", 3.5),
        Pattern("payment app not working", 5.0),
        Pattern("payment app problem", 4.0),
        Pattern("app not working", 4.0),
        Pattern("server down", 4.5),
        Pattern("network problem", 4.0),
        Pattern("poor network", 4.0),
        Pattern("bad network", 3.5),
        Pattern("internet problem", 4.0),
        Pattern("internet issue", 4.0),
        Pattern("connection problem", 4.0),
        Pattern("payment timed out", 5.0),
        Pattern("payment timeout", 5.0),
        Pattern("transaction timed out", 5.0),
        Pattern("transaction timeout", 5.0),
        Pattern("technical problem", 4.0),
        Pattern("technical issue", 4.0),
        Pattern("system error", 4.0),
        Pattern("payment failed", 3.5),
        Pattern("transaction failed", 3.5),
        Pattern("gateway error", 4.5),
        Pattern("gateway problem", 4.0),
    ],

    # --------------------------------------------------------
    # CHECKOUT ABANDONMENT
    # --------------------------------------------------------

    ProblemType.CHECKOUT_ABANDONMENT: [
        Pattern("forgot to complete the payment", 6.0),
        Pattern("forgot to finish the payment", 6.0),
        Pattern("forgot to make the payment", 5.5),
        Pattern("forgot payment", 5.0),
        Pattern("forgot to pay", 5.0),
        Pattern("did not complete the payment", 5.0),
        Pattern("did not finish the payment", 5.0),
        Pattern("did not complete payment", 5.0),
        Pattern("did not finish payment", 5.0),
        Pattern("closed the payment page", 6.0),
        Pattern("closed payment page", 6.0),
        Pattern("payment page closed", 5.0),
        Pattern("left the payment page", 5.0),
        Pattern("abandoned payment", 5.5),
        Pattern("abandoned checkout", 5.5),
        Pattern("left checkout", 5.0),
        Pattern("payment was not completed", 5.0),
        Pattern("checkout was not completed", 5.0),
    ],

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    ProblemType.FINANCIAL: [
        Pattern("not enough money", 6.0),
        Pattern("do not have enough money", 6.0),
        Pattern("no money", 5.5),
        Pattern("not enough funds", 6.0),
        Pattern("insufficient funds", 6.0),
        Pattern("cannot afford", 6.0),
        Pattern("cannot afford this payment", 6.5),
        Pattern("cannot pay", 5.5),
        Pattern("cannot make the payment", 5.0),
        Pattern("cannot make payment", 5.0),
        Pattern("cannot pay until salary", 7.0),
        Pattern("cannot pay until my salary", 7.0),
        Pattern("pay until salary", 6.0),
        Pattern("salary comes", 5.5),
        Pattern("salary arrives", 5.5),
        Pattern("waiting for salary", 5.5),
        Pattern("financial problem", 6.0),
        Pattern("financial difficulty", 6.0),
        Pattern("money problem", 5.5),
        Pattern("cash problem", 5.0),
        Pattern("short of money", 5.5),
        Pattern("short on money", 5.5),
        Pattern("broke", 4.5),
    ],

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    ProblemType.TIMING: [
        Pattern("pay tomorrow", 6.0),
        Pattern("payment tomorrow", 6.0),
        Pattern("pay later", 5.5),
        Pattern("payment later", 5.5),
        Pattern("not today", 5.0),
        Pattern("busy today", 5.0),
        Pattern("pay next week", 6.0),
        Pattern("pay next month", 6.0),
        Pattern("will pay later", 6.0),
        Pattern("i will pay tomorrow", 7.0),
        Pattern("i can pay tomorrow", 7.0),
        Pattern("i can pay but not today", 7.0),
        Pattern("cannot pay today", 5.0),
        Pattern("pay in a few days", 5.5),
        Pattern("pay in few days", 5.5),
    ],

    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    ProblemType.AUTHENTICATION: [
        Pattern("forgot my upi pin", 8.0),
        Pattern("forgot upi pin", 8.0),
        Pattern("forgot pin", 7.0),
        Pattern("upi pin", 6.0),
        Pattern("account locked", 7.0),
        Pattern("locked out", 6.0),
        Pattern("cannot log in", 6.0),
        Pattern("cannot login", 6.0),
        Pattern("unable to log in", 6.0),
        Pattern("unable to login", 6.0),
        Pattern("login problem", 5.5),
        Pattern("login issue", 5.5),
        Pattern("authentication problem", 6.0),
        Pattern("authentication issue", 6.0),
    ],

    # --------------------------------------------------------
    # SECURITY / ACCESS
    # --------------------------------------------------------

    ProblemType.SECURITY_ACCESS: [
        Pattern("phone was stolen", 8.0),
        Pattern("phone stolen", 8.0),
        Pattern("stolen phone", 8.0),
        Pattern("lost my phone", 8.0),
        Pattern("lost phone", 8.0),
        Pattern("cannot access my payment app", 6.0),
        Pattern("cannot access payment app", 6.0),
        Pattern("cannot access my account", 5.5),
        Pattern("security concern", 7.0),
        Pattern("security issue", 6.5),
        Pattern("security problem", 6.5),
    ],

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    ProblemType.DISPUTE: [
        Pattern("paid the wrong vendor", 8.0),
        Pattern("wrong vendor", 7.0),
        Pattern("wrong merchant", 7.0),
        Pattern("wrong payment", 6.5),
        Pattern("charged twice", 8.0),
        Pattern("charged two times", 8.0),
        Pattern("charged multiple times", 8.0),
        Pattern("duplicate charge", 8.0),
        Pattern("duplicate payment", 8.0),
        Pattern("do not recognize this payment", 8.0),
        Pattern("do not recognize payment", 8.0),
        Pattern("unrecognized payment", 8.0),
        Pattern("unknown payment", 7.0),
        Pattern("fraudulent payment", 8.0),
        Pattern("payment fraud", 8.0),
    ],
}


# ============================================================
# 5. CUSTOMER INTENT KNOWLEDGE BASE
# ============================================================

INTENT_PATTERNS: dict[CustomerIntent, list[Pattern]] = {

    # --------------------------------------------------------
    # WILLING TO PAY
    # --------------------------------------------------------

    CustomerIntent.WILLING_TO_PAY: [
        Pattern("i want to pay", 8.0),
        Pattern("i want to complete the payment", 9.0),
        Pattern("i want to complete payment", 9.0),
        Pattern("i want to finish the payment", 9.0),
        Pattern("i want to finish payment", 9.0),
        Pattern("i will pay", 7.0),
        Pattern("i can pay", 7.0),
        Pattern("i can make the payment", 8.0),
        Pattern("i will make the payment", 8.0),
        Pattern("i will try again", 8.0),
        Pattern("i will retry", 8.0),
        Pattern("i can retry", 8.0),
        Pattern("i want to retry", 8.0),
        Pattern("i will try again in a few minutes", 9.0),
        Pattern("i will complete it", 8.0),
        Pattern("i want to complete it", 8.0),
    ],

    # --------------------------------------------------------
    # DELAYING PAYMENT
    # --------------------------------------------------------

    CustomerIntent.DELAYING_PAYMENT: [
        Pattern("pay tomorrow", 8.0),
        Pattern("payment tomorrow", 8.0),
        Pattern("pay later", 7.0),
        Pattern("payment later", 7.0),
        Pattern("not today", 7.0),
        Pattern("busy today", 7.0),
        Pattern("pay next week", 8.0),
        Pattern("pay next month", 8.0),
        Pattern("i will pay tomorrow", 9.0),
        Pattern("i can pay tomorrow", 9.0),
        Pattern("i can pay but not today", 9.0),
        Pattern("pay in a few days", 8.0),
        Pattern("pay in few days", 8.0),
    ],

    # --------------------------------------------------------
    # FINANCIAL DIFFICULTY
    # --------------------------------------------------------

    CustomerIntent.FINANCIAL_DIFFICULTY: [
        Pattern("not enough money", 9.0),
        Pattern("do not have enough money", 9.0),
        Pattern("no money", 8.0),
        Pattern("not enough funds", 9.0),
        Pattern("insufficient funds", 9.0),
        Pattern("cannot afford", 9.0),
        Pattern("cannot afford this payment", 10.0),
        Pattern("cannot pay until salary", 10.0),
        Pattern("cannot pay until my salary", 10.0),
        Pattern("salary comes", 8.0),
        Pattern("salary arrives", 8.0),
        Pattern("waiting for salary", 8.0),
        Pattern("financial problem", 9.0),
        Pattern("financial difficulty", 9.0),
        Pattern("money problem", 8.0),
        Pattern("short of money", 8.0),
        Pattern("short on money", 8.0),
        Pattern("broke", 7.0),
    ],

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    CustomerIntent.DISPUTE: [
        Pattern("wrong vendor", 9.0),
        Pattern("wrong merchant", 9.0),
        Pattern("wrong payment", 8.0),
        Pattern("charged twice", 10.0),
        Pattern("duplicate charge", 10.0),
        Pattern("duplicate payment", 10.0),
        Pattern("do not recognize this payment", 10.0),
        Pattern("do not recognize payment", 10.0),
        Pattern("unrecognized payment", 10.0),
        Pattern("fraudulent payment", 10.0),
        Pattern("payment fraud", 10.0),
    ],

    # --------------------------------------------------------
    # SECURITY CONCERN
    # --------------------------------------------------------

    CustomerIntent.SECURITY_CONCERN: [
        Pattern("phone was stolen", 10.0),
        Pattern("phone stolen", 10.0),
        Pattern("stolen phone", 10.0),
        Pattern("lost my phone", 10.0),
        Pattern("lost phone", 10.0),
        Pattern("security concern", 9.0),
        Pattern("security issue", 9.0),
        Pattern("security problem", 9.0),
        Pattern("forgot my upi pin", 9.0),
        Pattern("forgot upi pin", 9.0),
        Pattern("forgot pin", 8.0),
    ],
}


# ============================================================
# 6. PHRASE MATCHING
# ============================================================

def _find_phrase_occurrences(
    tokens: list[str],
    phrase_tokens: list[str],
) -> list[int]:
    """
    Return starting indexes where a phrase occurs.
    """

    if not phrase_tokens:
        return []

    positions = []

    phrase_length = len(phrase_tokens)

    for index in range(len(tokens) - phrase_length + 1):
        if tokens[index:index + phrase_length] == phrase_tokens:
            positions.append(index)

    return positions


def _is_negated_at(
    tokens: list[str],
    start_index: int,
) -> bool:
    """
    Detect local negation before an evidence phrase.

    Example:
        "do not have a problem with my bank app"

    The bank-app evidence should be suppressed.
    """

    window_start = max(0, start_index - 4)

    window = tokens[window_start:start_index]

    negations = {
        "not",
        "no",
        "never",
        "cannot",
        "without",
    }

    return any(word in negations for word in window)


def _fuzzy_phrase_match(
    tokens: list[str],
    phrase_tokens: list[str],
    threshold: float = 0.90,
) -> bool:
    """
    Conservative fuzzy matching.

    Only used for multi-word phrases to tolerate small language mistakes.
    """

    if len(phrase_tokens) < 2:
        return False

    phrase = " ".join(phrase_tokens)

    window_size = len(phrase_tokens)

    for index in range(len(tokens) - window_size + 1):
        window = " ".join(
            tokens[index:index + window_size]
        )

        similarity = SequenceMatcher(
            None,
            window,
            phrase,
        ).ratio()

        if similarity >= threshold:
            if not _is_negated_at(tokens, index):
                return True

    return False


# ============================================================
# 7. PATTERN SCORING
# ============================================================

def score_patterns(
    text: str,
    patterns: list[Pattern],
) -> list[Evidence]:
    """
    Collect all positive evidence for a pattern group.
    """

    tokens = tokenize(text)

    evidence: list[Evidence] = []

    for pattern in patterns:

        phrase_tokens = tokenize(pattern.phrase)

        # Exact token-level matching.
        occurrences = _find_phrase_occurrences(
            tokens,
            phrase_tokens,
        )

        for occurrence in occurrences:

            if _is_negated_at(tokens, occurrence):
                continue

            evidence.append(
                Evidence(
                    phrase=pattern.phrase,
                    weight=pattern.weight,
                )
            )

        # Conservative fuzzy matching.
        if not occurrences:
            if _fuzzy_phrase_match(
                tokens,
                phrase_tokens,
            ):
                evidence.append(
                    Evidence(
                        phrase=pattern.phrase,
                        weight=pattern.weight * 0.8,
                    )
                )

    return evidence


def _score_group(
    text: str,
    patterns: list[Pattern],
) -> float:
    evidence = score_patterns(
        text,
        patterns,
    )

    if not evidence:
        return 0.0

    # Prevent many overlapping phrases from dominating.
    weights = sorted(
        [item.weight for item in evidence],
        reverse=True,
    )

    if len(weights) == 1:
        return weights[0]

    return weights[0] + sum(
        weight * 0.35
        for weight in weights[1:4]
    )


def _ranked(
    text: str,
    groups,
):
    scores = []

    for category, patterns in groups.items():
        score = _score_group(
            text,
            patterns,
        )

        scores.append(
            (category, score)
        )

    return sorted(
        scores,
        key=lambda item: item[1],
        reverse=True,
    )


def get_best_category(
    text: str,
    groups,
    unknown_value,
):
    ranked = _ranked(
        text,
        groups,
    )

    if not ranked or ranked[0][1] <= 0:
        return unknown_value, 0.0

    best_category, best_score = ranked[0]

    if len(ranked) == 1:
        confidence = min(best_score / 10.0, 1.0)

    else:
        second_score = ranked[1][1]

        if second_score <= 0:
            confidence = min(best_score / 10.0, 1.0)

        else:
            margin = best_score - second_score
            confidence = min(
                max(margin / best_score, 0.0),
                1.0,
            )

            # Strong absolute evidence should remain confident
            # even when several categories have weak evidence.
            if best_score >= 7:
                confidence = max(
                    confidence,
                    0.65,
                )

    return best_category, confidence


# ============================================================
# 8. EXPLICIT CUSTOMER SIGNALS
# ============================================================

def _contains_any(
    text: str,
    phrases: list[str],
) -> bool:

    tokens = tokenize(text)

    for phrase in phrases:

        phrase_tokens = tokenize(phrase)

        occurrences = _find_phrase_occurrences(
            tokens,
            phrase_tokens,
        )

        for occurrence in occurrences:
            if not _is_negated_at(
                tokens,
                occurrence,
            ):
                return True

    return False


def _detect_willingness(
    text: str,
) -> bool:
    """
    Detect EXPLICIT willingness.

    Important:
    Merely mentioning payment completion is NOT enough.

    Example:
        "I forgot to complete the payment."

    This does NOT mean:
        "I want to complete the payment."

    Therefore we intentionally require explicit intent language.
    """

    explicit_willingness = [
        "i want to pay",
        "i want to complete the payment",
        "i want to complete payment",
        "i want to finish the payment",
        "i want to finish payment",
        "i will pay",
        "i can pay",
        "i can make the payment",
        "i will make the payment",
        "i will try again",
        "i will retry",
        "i can retry",
        "i want to retry",
        "i will complete it",
        "i want to complete it",
        "i am willing to pay",
        "i am ready to pay",
        "ready to pay",
        "happy to pay",
    ]

    return _contains_any(
        text,
        explicit_willingness,
    )


def _detect_delay(
    text: str,
) -> bool:

    delay_phrases = [
        "pay tomorrow",
        "payment tomorrow",
        "pay later",
        "payment later",
        "not today",
        "busy today",
        "pay next week",
        "pay next month",
        "will pay tomorrow",
        "can pay tomorrow",
        "can pay but not today",
        "pay in a few days",
        "pay in few days",
    ]

    return _contains_any(
        text,
        delay_phrases,
    )


def _detect_contradiction(
    text: str,
) -> bool:
    """
    Detect direct contradiction between willingness and refusal.
    """

    normalized = normalize_text(text)

    willingness = _detect_willingness(
        normalized
    )

    refusal_phrases = [
        "i do not want to pay",
        "i do not want to make the payment",
        "i will not pay",
        "i cannot pay",
        "i refuse to pay",
        "i do not want to pay this",
    ]

    refusal = _contains_any(
        normalized,
        refusal_phrases,
    )

    return willingness and refusal


# ============================================================
# 9. INTENT CLASSIFICATION
# ============================================================

def classify_intent(
    text: str,
) -> tuple[CustomerIntent, float]:
    """
    Classify customer intent using explicit evidence.

    Priority:
        1. Dispute
        2. Security
        3. Financial difficulty
        4. Contradiction
        5. Delay
        6. Explicit willingness
        7. Unknown
    """

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    dispute_score = _score_group(
        text,
        INTENT_PATTERNS[
            CustomerIntent.DISPUTE
        ],
    )

    if dispute_score > 0:
        return (
            CustomerIntent.DISPUTE,
            min(dispute_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    security_score = _score_group(
        text,
        INTENT_PATTERNS[
            CustomerIntent.SECURITY_CONCERN
        ],
    )

    if security_score > 0:
        return (
            CustomerIntent.SECURITY_CONCERN,
            min(security_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    financial_score = _score_group(
        text,
        INTENT_PATTERNS[
            CustomerIntent.FINANCIAL_DIFFICULTY
        ],
    )

    if financial_score > 0:
        return (
            CustomerIntent.FINANCIAL_DIFFICULTY,
            min(financial_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # EXPLICIT SIGNALS
    # --------------------------------------------------------

    willingness = _detect_willingness(
        text
    )

    delay = _detect_delay(
        text
    )

    # If both are present, delay is the operationally
    # important state while willingness remains an
    # internal signal.
    if delay:
        return (
            CustomerIntent.DELAYING_PAYMENT,
            0.90,
        )

    if willingness:
        return (
            CustomerIntent.WILLING_TO_PAY,
            0.90,
        )

    return (
        CustomerIntent.UNKNOWN,
        0.0,
    )


# ============================================================
# 10. PROBLEM CLASSIFICATION
# ============================================================

def classify_problem(
    text: str,
) -> tuple[ProblemType, float]:

    ranked = _ranked(
        text,
        PROBLEM_PATTERNS,
    )

    if not ranked:
        return (
            ProblemType.UNKNOWN,
            0.0,
        )

    best_problem, best_score = ranked[0]

    if best_score <= 0:
        return (
            ProblemType.UNKNOWN,
            0.0,
        )

    # --------------------------------------------------------
    # Explicit financial language can override weak timing
    # evidence.
    #
    # "I can't pay until my salary comes."
    # is financial difficulty, not merely timing.
    # --------------------------------------------------------

    financial_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.FINANCIAL
        ],
    )

    if financial_score >= 5.0:
        return (
            ProblemType.FINANCIAL,
            min(financial_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # Checkout abandonment gets priority when explicitly
    # detected.
    # --------------------------------------------------------

    checkout_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.CHECKOUT_ABANDONMENT
        ],
    )

    if checkout_score >= 5.0:
        return (
            ProblemType.CHECKOUT_ABANDONMENT,
            min(checkout_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # Security
    # --------------------------------------------------------

    security_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.SECURITY_ACCESS
        ],
    )

    if security_score >= 6.0:
        return (
            ProblemType.SECURITY_ACCESS,
            min(security_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    authentication_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.AUTHENTICATION
        ],
    )

    if authentication_score >= 6.0:
        return (
            ProblemType.AUTHENTICATION,
            min(authentication_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # Dispute
    # --------------------------------------------------------

    dispute_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.DISPUTE
        ],
    )

    if dispute_score >= 6.0:
        return (
            ProblemType.DISPUTE,
            min(dispute_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # Timing
    # --------------------------------------------------------

    timing_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.TIMING
        ],
    )

    if timing_score >= 5.0:
        return (
            ProblemType.TIMING,
            min(timing_score / 10.0, 1.0),
        )

    # --------------------------------------------------------
    # Technical
    # --------------------------------------------------------

    technical_score = _score_group(
        text,
        PROBLEM_PATTERNS[
            ProblemType.TECHNICAL
        ],
    )

    if technical_score >= 4.0:
        return (
            ProblemType.TECHNICAL,
            min(technical_score / 10.0, 1.0),
        )

    return (
        best_problem,
        min(best_score / 10.0, 1.0),
    )


# ============================================================
# 11. RECOVERY POLICY
# ============================================================

def choose_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    willingness_to_pay: bool = False,
    delay_signal: bool = False,
    contradiction: bool = False,
    sensitive: bool = False,
    confidence: float = 1.0,
) -> RecoveryAction:

    # --------------------------------------------------------
    # SAFETY FIRST
    # --------------------------------------------------------

    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    if contradiction:
        return RecoveryAction.HUMAN_ESCALATION

    if confidence < 0.45:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # DISPUTES MUST STOP
    # --------------------------------------------------------

    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if customer_intent == CustomerIntent.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    # --------------------------------------------------------
    # FINANCIAL DIFFICULTY
    # --------------------------------------------------------

    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.FINANCIAL_DIFFICULTY:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # SECURITY / AUTHENTICATION
    # --------------------------------------------------------

    if problem_type in {
        ProblemType.SECURITY_ACCESS,
        ProblemType.AUTHENTICATION,
    }:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.SECURITY_CONCERN:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    if (
        problem_type == ProblemType.TIMING
        or delay_signal
        or customer_intent == CustomerIntent.DELAYING_PAYMENT
    ):
        return RecoveryAction.SCHEDULE_REMINDER

    # --------------------------------------------------------
    # TECHNICAL
    # --------------------------------------------------------

    if problem_type == ProblemType.TECHNICAL:

        if willingness_to_pay:
            return RecoveryAction.OFFER_RETRY

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    # --------------------------------------------------------
    # CHECKOUT
    # --------------------------------------------------------

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:

        return RecoveryAction.OFFER_RETRY

    # --------------------------------------------------------
    # EXPLICIT WILLINGNESS
    # --------------------------------------------------------

    if (
        customer_intent == CustomerIntent.WILLING_TO_PAY
        or willingness_to_pay
    ):
        return RecoveryAction.OFFER_RETRY

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# 12. EXPLANATION
# ============================================================

def _pretty(value) -> str:

    if hasattr(value, "value"):
        value = value.value

    return value.replace(
        "_",
        " ",
    ).title()


def build_explanation(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    recommended_action: RecoveryAction,
    problem_confidence: float,
    intent_confidence: float,
    willingness_to_pay: bool,
    delay_signal: bool,
) -> str:

    problem_text = _pretty(
        problem_type
    )

    intent_text = _pretty(
        customer_intent
    )

    action_text = _pretty(
        recommended_action
    )

    signals = []

    if willingness_to_pay:
        signals.append(
            "explicit willingness to pay"
        )

    if delay_signal:
        signals.append(
            "payment delay signal"
        )

    if signals:
        signal_text = (
            " Detected signals: "
            + ", ".join(signals)
            + "."
        )
    else:
        signal_text = ""

    return (
        f"Detected {problem_text} with "
        f"{intent_text} intent. "
        f"Recommended action: {action_text}. "
        f"Problem confidence: "
        f"{problem_confidence:.2f}. "
        f"Intent confidence: "
        f"{intent_confidence:.2f}."
        f"{signal_text}"
    )


# ============================================================
# 13. MAIN ANALYSIS PIPELINE
# ============================================================

def analyze_message(
    message: str,
) -> DiagnosisAnalysis:

    normalized = normalize_text(
        message
    )

    # --------------------------------------------------------
    # Empty input
    # --------------------------------------------------------

    if not normalized:

        return DiagnosisAnalysis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.UNKNOWN,
            recommended_action=RecoveryAction.HUMAN_ESCALATION,
            explanation=(
                "No meaningful customer message "
                "was provided."
            ),
            willingness_to_pay=False,
            delay_signal=False,
            contradiction=False,
            sensitive=False,
            problem_confidence=0.0,
            intent_confidence=0.0,
            overall_confidence=0.0,
        )

    # --------------------------------------------------------
    # Safety detection
    # --------------------------------------------------------

    sensitive = contains_sensitive_information(
        message
    )

    # --------------------------------------------------------
    # Independent signals
    # --------------------------------------------------------

    willingness_to_pay = _detect_willingness(
        normalized
    )

    delay_signal = _detect_delay(
        normalized
    )

    contradiction = _detect_contradiction(
        normalized
    )

    # --------------------------------------------------------
    # Problem classification
    # --------------------------------------------------------

    problem_type, problem_confidence = classify_problem(
        normalized
    )

    # --------------------------------------------------------
    # Intent classification
    # --------------------------------------------------------

    customer_intent, intent_confidence = classify_intent(
        normalized
    )

    # --------------------------------------------------------
    # Contradiction gets UNKNOWN intent.
    #
    # We do not pretend to understand contradictory
    # customer intent.
    # --------------------------------------------------------

    if contradiction:
        customer_intent = CustomerIntent.UNKNOWN
        intent_confidence = 0.0

    # --------------------------------------------------------
    # Safety-sensitive authentication/security messages
    # --------------------------------------------------------

    if sensitive:

        # Sensitive information should never become an
        # ordinary recovery conversation.
        if problem_type == ProblemType.UNKNOWN:
            problem_type = ProblemType.AUTHENTICATION
            problem_confidence = 0.90

        customer_intent = CustomerIntent.SECURITY_CONCERN
        intent_confidence = 0.95

    # --------------------------------------------------------
    # If financial language exists, enforce financial intent.
    # --------------------------------------------------------

    if problem_type == ProblemType.FINANCIAL:

        customer_intent = (
            CustomerIntent.FINANCIAL_DIFFICULTY
        )

        intent_confidence = max(
            intent_confidence,
            0.90,
        )

    # --------------------------------------------------------
    # Delay takes precedence over generic willingness.
    #
    # "I will pay tomorrow."
    #
    # Internally:
    #     willingness = True
    #     delay = True
    #
    # Externally:
    #     DELAYING_PAYMENT
    # --------------------------------------------------------

    if (
        delay_signal
        and not sensitive
        and problem_type != ProblemType.FINANCIAL
    ):
        customer_intent = (
            CustomerIntent.DELAYING_PAYMENT
        )

        intent_confidence = max(
            intent_confidence,
            0.90,
        )

    # --------------------------------------------------------
    # Checkout abandonment should NOT automatically imply
    # willingness.
    #
    # Example:
    #     "I forgot to complete the payment."
    #
    # This means:
    #     Problem = CHECKOUT_ABANDONMENT
    #     Intent = UNKNOWN
    #
    # Only explicit phrases such as:
    #     "I want to complete it."
    #
    # should produce WILLING_TO_PAY.
    # --------------------------------------------------------

    if (
        problem_type == ProblemType.CHECKOUT_ABANDONMENT
        and not delay_signal
        and not sensitive
    ):

        explicit_willingness = _detect_willingness(
            normalized
        )

        if not explicit_willingness:
            customer_intent = CustomerIntent.UNKNOWN
            intent_confidence = 0.0

    # --------------------------------------------------------
    # "I don't have any problem with my bank app..."
    #
    # The negated technical evidence must not affect the
    # final diagnosis.
    # --------------------------------------------------------

    # Nothing special is required here because all evidence
    # matching passes through _is_negated_at().
    #
    # The important part is that checkout abandonment can
    # remain the dominant positive evidence.

    # --------------------------------------------------------
    # Overall confidence
    # --------------------------------------------------------

    if contradiction:
        overall_confidence = 0.0

    elif sensitive:
        overall_confidence = min(
            0.95,
            max(
                problem_confidence,
                intent_confidence,
            ),
        )

    else:
        overall_confidence = (
            problem_confidence * 0.60
            + intent_confidence * 0.40
        )

    # --------------------------------------------------------
    # Recovery action
    # --------------------------------------------------------

    recommended_action = choose_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        contradiction=contradiction,
        sensitive=sensitive,
        confidence=overall_confidence,
    )

    # --------------------------------------------------------
    # Explanation
    # --------------------------------------------------------

    explanation = build_explanation(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=recommended_action,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
    )

    return DiagnosisAnalysis(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=recommended_action,
        explanation=explanation,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        contradiction=contradiction,
        sensitive=sensitive,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
        overall_confidence=overall_confidence,
    )


# ============================================================
# 14. PUBLIC API
# ============================================================

def diagnose_message(
    message: str,
) -> DiagnosisAnalysis:
    """
    Public diagnosis API.
    """

    return analyze_message(
        message
    )


def detect_problem(
    message: str,
) -> ProblemType:
    """
    Backward-compatible helper.
    """

    problem, _ = classify_problem(
        message
    )

    return problem