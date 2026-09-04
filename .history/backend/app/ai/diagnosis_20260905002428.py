"""
AI Revenue Recovery - Customer Diagnosis Engine

Deterministic, domain-specific reasoning engine for customer payment
recovery conversations.

Pipeline:

    Customer Message
          ↓
    Normalization
          ↓
    Evidence Detection
          ↓
    Problem Classification
          ↓
    Intent Classification
          ↓
    Safety / Policy
          ↓
    Recovery Action

This is intentionally NOT an LLM.

The goal is to provide explainable, auditable and safe reasoning that
can later evolve into a learned model using the platform's own data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    Convert messy natural language into predictable text.

    Steps:
        1. Lowercase
        2. Expand contractions
        3. Remove punctuation
        4. Collapse whitespace
    """

    if not text:
        return ""

    text = text.lower().strip()

    for contraction, expanded in CONTRACTIONS.items():
        text = re.sub(
            rf"\b{re.escape(contraction)}\b",
            expanded,
            text,
        )

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def tokenize(text: str) -> list[str]:
    """
    Tokenize normalized text.
    """

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
    r"\bbank\s+password\b",
    r"\bbanking\s+password\b",
]


CREDENTIAL_VALUE_PATTERNS = [
    # OTP / PIN-like number.
    r"\b\d{4,6}\b",

    # Card-number-like sequence.
    r"\b(?:\d[ -]?){13,19}\b",
]


def contains_sensitive_information(text: str) -> bool:
    """
    Detect potentially sensitive payment credentials.

    We never attempt to interpret or store the credential value.
    """

    if not text:
        return False

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
    Remove likely credential values before audit logging.
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
# 3. DATA STRUCTURES
# ============================================================

@dataclass
class Pattern:
    """
    Domain knowledge pattern.

    phrase:
        Normalized phrase to detect.

    weight:
        Strength of the evidence.
    """

    phrase: str
    weight: float


@dataclass
class Evidence:
    """
    Evidence detected in the customer message.
    """

    phrase: str
    weight: float


@dataclass
class DiagnosisAnalysis:
    """
    Complete reasoning result.
    """

    problem_type: ProblemType
    customer_intent: CustomerIntent
    recommended_action: RecoveryAction

    explanation: str

    # Internal signals.
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

        Pattern("bank app not working", 9.0),
        Pattern("bank application not working", 9.0),

        Pattern("payment app not working", 9.0),
        Pattern("payment application not working", 9.0),

        Pattern("app not working", 7.0),
        Pattern("application not working", 7.0),

        Pattern("bank server down", 9.0),
        Pattern("bank server is down", 9.0),
        Pattern("server down", 8.0),

        Pattern("bank server problem", 8.0),
        Pattern("bank server issue", 8.0),

        Pattern("bank problem", 6.0),
        Pattern("bank issue", 6.0),

        Pattern("payment app problem", 7.0),
        Pattern("payment app issue", 7.0),

        Pattern("network problem", 7.0),
        Pattern("network issue", 7.0),
        Pattern("poor network", 8.0),
        Pattern("bad network", 7.0),

        Pattern("internet problem", 7.0),
        Pattern("internet issue", 7.0),
        Pattern("poor internet", 7.0),

        Pattern("connection problem", 7.0),
        Pattern("connection issue", 7.0),

        Pattern("payment timed out", 9.0),
        Pattern("payment timeout", 9.0),

        Pattern("transaction timed out", 9.0),
        Pattern("transaction timeout", 9.0),

        Pattern("request timed out", 8.0),
        Pattern("timed out", 7.0),
        Pattern("timeout", 6.0),

        Pattern("technical problem", 8.0),
        Pattern("technical issue", 8.0),

        Pattern("system error", 8.0),
        Pattern("system problem", 7.0),

        Pattern("payment failed", 7.0),
        Pattern("transaction failed", 7.0),

        Pattern("gateway error", 8.0),
        Pattern("gateway problem", 8.0),
        Pattern("gateway issue", 8.0),

        Pattern("server error", 8.0),
    ],

    # --------------------------------------------------------
    # CHECKOUT ABANDONMENT
    # --------------------------------------------------------

    ProblemType.CHECKOUT_ABANDONMENT: [

        Pattern("forgot to complete the payment", 10.0),
        Pattern("forgot to finish the payment", 10.0),
        Pattern("forgot to complete payment", 10.0),
        Pattern("forgot to finish payment", 10.0),

        Pattern("forgot to make the payment", 9.0),
        Pattern("forgot to make payment", 9.0),

        Pattern("forgot payment", 8.0),
        Pattern("forgot to pay", 8.0),

        Pattern("did not complete the payment", 9.0),
        Pattern("did not finish the payment", 9.0),

        Pattern("did not complete payment", 9.0),
        Pattern("did not finish payment", 9.0),

        Pattern("payment was not completed", 9.0),
        Pattern("payment was not finished", 9.0),

        Pattern("closed the payment page", 10.0),
        Pattern("closed payment page", 10.0),

        Pattern("payment page closed", 9.0),

        Pattern("closed checkout", 8.0),
        Pattern("closed the checkout", 8.0),

        Pattern("left the payment page", 8.0),
        Pattern("left payment page", 8.0),

        Pattern("left checkout", 8.0),

        Pattern("abandoned payment", 9.0),
        Pattern("abandoned checkout", 9.0),

        Pattern("checkout was not completed", 9.0),
        Pattern("checkout not completed", 9.0),
    ],

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    ProblemType.FINANCIAL: [

        Pattern("not enough money", 10.0),
        Pattern("do not have enough money", 10.0),

        Pattern("no money", 9.0),

        Pattern("not enough funds", 10.0),
        Pattern("insufficient funds", 10.0),

        Pattern("low balance", 9.0),
        Pattern("balance is low", 9.0),

        Pattern("cannot afford", 10.0),
        Pattern("cannot afford this payment", 10.0),

        Pattern("cannot pay", 9.0),
        Pattern("cannot make the payment", 9.0),
        Pattern("cannot make payment", 9.0),

        Pattern("money problem", 9.0),
        Pattern("money issue", 8.0),

        Pattern("financial problem", 10.0),
        Pattern("financial issue", 10.0),
        Pattern("financial difficulty", 10.0),

        Pattern("short of money", 9.0),
        Pattern("short on money", 9.0),

        Pattern("cash problem", 8.0),

        Pattern("salary comes", 9.0),
        Pattern("salary arrives", 9.0),
        Pattern("my salary comes", 10.0),
        Pattern("my salary arrives", 10.0),

        Pattern("waiting for salary", 10.0),
        Pattern("waiting for my salary", 10.0),

        Pattern("until salary", 10.0),
        Pattern("until my salary", 10.0),

        Pattern("when my salary comes", 10.0),
        Pattern("when my salary arrives", 10.0),

        Pattern("broke", 8.0),
    ],

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    ProblemType.TIMING: [

        Pattern("pay tomorrow", 9.0),
        Pattern("payment tomorrow", 9.0),

        Pattern("pay later", 8.0),
        Pattern("payment later", 8.0),

        Pattern("not today", 8.0),
        Pattern("busy today", 8.0),

        Pattern("pay next week", 9.0),
        Pattern("pay next month", 9.0),

        Pattern("will pay tomorrow", 10.0),
        Pattern("can pay tomorrow", 10.0),

        Pattern("can pay but not today", 10.0),

        Pattern("pay in a few days", 9.0),
        Pattern("pay in few days", 9.0),

        Pattern("after work", 8.0),
        Pattern("when i get time", 8.0),

        Pattern("this evening", 7.0),
        Pattern("later today", 8.0),
    ],

    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    ProblemType.AUTHENTICATION: [

        Pattern("forgot my upi pin", 10.0),
        Pattern("forgot upi pin", 10.0),

        Pattern("forgot my pin", 10.0),
        Pattern("forgot pin", 9.0),

        Pattern("upi pin", 9.0),

        Pattern("account locked", 10.0),
        Pattern("locked out", 9.0),

        Pattern("cannot log in", 9.0),
        Pattern("cannot login", 9.0),

        Pattern("unable to log in", 9.0),
        Pattern("unable to login", 9.0),

        Pattern("login problem", 9.0),
        Pattern("login issue", 9.0),

        Pattern("authentication problem", 9.0),
        Pattern("authentication issue", 9.0),

        Pattern("verification problem", 8.0),
        Pattern("verification issue", 8.0),
    ],

    # --------------------------------------------------------
    # SECURITY / ACCESS
    # --------------------------------------------------------

    ProblemType.SECURITY_ACCESS: [

        Pattern("phone was stolen", 10.0),
        Pattern("phone stolen", 10.0),
        Pattern("stolen phone", 10.0),

        Pattern("lost my phone", 10.0),
        Pattern("lost phone", 10.0),

        Pattern("cannot access my payment app", 9.0),
        Pattern("cannot access payment app", 9.0),

        Pattern("cannot access my account", 9.0),
        Pattern("cannot access account", 9.0),

        Pattern("security concern", 10.0),
        Pattern("security issue", 10.0),
        Pattern("security problem", 10.0),

        Pattern("account compromised", 10.0),
        Pattern("phone compromised", 10.0),

        Pattern("suspicious access", 10.0),
    ],

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    ProblemType.DISPUTE: [

        Pattern("paid the wrong vendor", 10.0),
        Pattern("wrong vendor", 10.0),

        Pattern("paid the wrong merchant", 10.0),
        Pattern("wrong merchant", 10.0),

        Pattern("wrong payment", 9.0),

        Pattern("charged twice", 10.0),
        Pattern("charged two times", 10.0),
        Pattern("charged multiple times", 10.0),

        Pattern("duplicate charge", 10.0),
        Pattern("duplicate payment", 10.0),

        Pattern("do not recognize this payment", 10.0),
        Pattern("do not recognize payment", 10.0),

        Pattern("unrecognized payment", 10.0),
        Pattern("unknown payment", 9.0),

        Pattern("fraudulent payment", 10.0),
        Pattern("payment fraud", 10.0),

        Pattern("unauthorized payment", 10.0),

        Pattern("want a refund", 8.0),
        Pattern("request a refund", 8.0),
    ],
}


# ============================================================
# 5. INTENT KNOWLEDGE BASE
# ============================================================

INTENT_PATTERNS: dict[CustomerIntent, list[Pattern]] = {

    # --------------------------------------------------------
    # WILLING TO PAY
    # --------------------------------------------------------

    CustomerIntent.WILLING_TO_PAY: [

        Pattern("i want to pay", 10.0),

        Pattern("i want to complete the payment", 10.0),
        Pattern("i want to complete payment", 10.0),

        Pattern("i want to finish the payment", 10.0),
        Pattern("i want to finish payment", 10.0),

        Pattern("i will pay", 9.0),
        Pattern("i can pay", 9.0),

        Pattern("i can make the payment", 10.0),
        Pattern("i will make the payment", 10.0),

        Pattern("i will try again", 10.0),
        Pattern("i will retry", 10.0),

        Pattern("i can retry", 10.0),
        Pattern("i want to retry", 10.0),

        Pattern("i will complete it", 10.0),
        Pattern("i want to complete it", 10.0),

        Pattern("i can complete it", 10.0),
        Pattern("i can finish it", 10.0),

        Pattern("i am willing to pay", 10.0),
        Pattern("i am ready to pay", 10.0),

        Pattern("ready to pay", 9.0),
        Pattern("happy to pay", 9.0),

        Pattern("i will complete the payment", 10.0),
        Pattern("i can complete the payment", 10.0),
    ],

    # --------------------------------------------------------
    # DELAYING PAYMENT
    # --------------------------------------------------------

    CustomerIntent.DELAYING_PAYMENT: [

        Pattern("pay tomorrow", 10.0),
        Pattern("payment tomorrow", 10.0),

        Pattern("pay later", 9.0),
        Pattern("payment later", 9.0),

        Pattern("not today", 9.0),
        Pattern("busy today", 9.0),

        Pattern("pay next week", 10.0),
        Pattern("pay next month", 10.0),

        Pattern("will pay tomorrow", 10.0),
        Pattern("can pay tomorrow", 10.0),

        Pattern("can pay but not today", 10.0),

        Pattern("pay in a few days", 10.0),
        Pattern("pay in few days", 10.0),

        Pattern("after work", 8.0),
        Pattern("later today", 8.0),
    ],

    # --------------------------------------------------------
    # FINANCIAL DIFFICULTY
    # --------------------------------------------------------

    CustomerIntent.FINANCIAL_DIFFICULTY: [

        Pattern("not enough money", 10.0),
        Pattern("do not have enough money", 10.0),

        Pattern("no money", 10.0),

        Pattern("not enough funds", 10.0),
        Pattern("insufficient funds", 10.0),

        Pattern("low balance", 10.0),

        Pattern("cannot afford", 10.0),
        Pattern("cannot afford this payment", 10.0),

        Pattern("cannot pay", 10.0),
        Pattern("cannot make the payment", 10.0),
        Pattern("cannot make payment", 10.0),

        Pattern("money problem", 9.0),
        Pattern("financial problem", 10.0),
        Pattern("financial difficulty", 10.0),

        Pattern("short of money", 10.0),
        Pattern("short on money", 10.0),

        Pattern("salary comes", 10.0),
        Pattern("salary arrives", 10.0),

        Pattern("waiting for salary", 10.0),
        Pattern("waiting for my salary", 10.0),

        Pattern("until salary", 10.0),
        Pattern("until my salary", 10.0),

        Pattern("when my salary comes", 10.0),
        Pattern("when my salary arrives", 10.0),

        Pattern("broke", 9.0),
    ],

    # --------------------------------------------------------
    # DISPUTE
    # --------------------------------------------------------

    CustomerIntent.DISPUTE: [

        Pattern("wrong vendor", 10.0),
        Pattern("wrong merchant", 10.0),
        Pattern("wrong payment", 10.0),

        Pattern("charged twice", 10.0),
        Pattern("duplicate charge", 10.0),
        Pattern("duplicate payment", 10.0),

        Pattern("do not recognize this payment", 10.0),
        Pattern("do not recognize payment", 10.0),

        Pattern("unrecognized payment", 10.0),

        Pattern("fraudulent payment", 10.0),
        Pattern("payment fraud", 10.0),

        Pattern("unauthorized payment", 10.0),
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

        Pattern("security concern", 10.0),
        Pattern("security issue", 10.0),
        Pattern("security problem", 10.0),

        Pattern("account compromised", 10.0),
        Pattern("suspicious access", 10.0),

        Pattern("forgot my upi pin", 10.0),
        Pattern("forgot upi pin", 10.0),
        Pattern("forgot my pin", 10.0),
        Pattern("forgot pin", 10.0),
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
    Find exact token-level occurrences of a phrase.
    """

    if not phrase_tokens:
        return []

    positions: list[int] = []

    phrase_length = len(phrase_tokens)

    for index in range(
        len(tokens) - phrase_length + 1
    ):
        if (
            tokens[index:index + phrase_length]
            == phrase_tokens
        ):
            positions.append(index)

    return positions


def _is_negated_at(
    tokens: list[str],
    start_index: int,
) -> bool:
    """
    Detect whether an evidence phrase is negated.

    Important:

    We inspect ONLY the words immediately before the
    evidence phrase.

    Example:

        "I do not have a problem with my bank app"

    The word "problem" is not automatically considered
    positive technical evidence.

    At the same time:

        "bank app not working"

    remains valid technical evidence because "not" is
    INSIDE the evidence phrase, not before it.
    """

    if start_index <= 0:
        return False

    window_start = max(
        0,
        start_index - 5,
    )

    previous = tokens[
        window_start:start_index
    ]

    negation_sequences = [
        ["not"],
        ["no"],
        ["never"],
        ["without"],
        ["do", "not"],
        ["does", "not"],
        ["did", "not"],
        ["is", "not"],
        ["are", "not"],
        ["was", "not"],
        ["were", "not"],
    ]

    for sequence in negation_sequences:

        length = len(sequence)

        if len(previous) >= length:

            if previous[-length:] == sequence:
                return True

    return False


def _phrase_is_negated(
    text: str,
    phrase: str,
) -> bool:
    """
    Determine whether a specific phrase occurrence
    is negated.
    """

    tokens = tokenize(text)
    phrase_tokens = tokenize(phrase)

    occurrences = _find_phrase_occurrences(
        tokens,
        phrase_tokens,
    )

    if not occurrences:
        return False

    return all(
        _is_negated_at(tokens, occurrence)
        for occurrence in occurrences
    )


# ============================================================
# 7. PATTERN SCORING
# ============================================================

def score_patterns(
    text: str,
    patterns: list[Pattern],
) -> list[Evidence]:
    """
    Collect positive evidence.

    We intentionally use exact token matching instead of
    fuzzy matching.

    Why?

    In payment recovery, a false positive can cause the
    wrong recovery action. Explainability and safety are
    more important than being overly clever.
    """

    tokens = tokenize(text)

    evidence: list[Evidence] = []

    for pattern in patterns:

        phrase_tokens = tokenize(
            pattern.phrase
        )

        occurrences = _find_phrase_occurrences(
            tokens,
            phrase_tokens,
        )

        for occurrence in occurrences:

            if _is_negated_at(
                tokens,
                occurrence,
            ):
                continue

            evidence.append(
                Evidence(
                    phrase=pattern.phrase,
                    weight=pattern.weight,
                )
            )

    return evidence


def _score_group(
    text: str,
    patterns: list[Pattern],
) -> float:
    """
    Calculate a bounded evidence score.

    The strongest evidence matters most.
    Additional evidence provides support without allowing
    duplicate overlapping phrases to dominate.
    """

    evidence = score_patterns(
        text,
        patterns,
    )

    if not evidence:
        return 0.0

    weights = sorted(
        [
            item.weight
            for item in evidence
        ],
        reverse=True,
    )

    score = weights[0]

    for weight in weights[1:4]:
        score += weight * 0.30

    return score


def _ranked(
    text: str,
    groups,
):
    """
    Rank classification groups by evidence strength.
    """

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
    """
    Return the strongest category and confidence.
    """

    ranked = _ranked(
        text,
        groups,
    )

    if not ranked:
        return (
            unknown_value,
            0.0,
        )

    best_category, best_score = ranked[0]

    if best_score <= 0:
        return (
            unknown_value,
            0.0,
        )

    second_score = (
        ranked[1][1]
        if len(ranked) > 1
        else 0.0
    )

    # Strong evidence should remain confident even when
    # another weak category exists.
    absolute_confidence = min(
        best_score / 10.0,
        1.0,
    )

    if second_score <= 0:
        return (
            best_category,
            absolute_confidence,
        )

    margin = (
        best_score - second_score
    ) / max(best_score, 1.0)

    confidence = (
        absolute_confidence * 0.60
        + max(margin, 0.0) * 0.40
    )

    if best_score >= 8.0:
        confidence = max(
            confidence,
            0.70,
        )

    return (
        best_category,
        min(confidence, 1.0),
    )


# ============================================================
# 8. EXPLICIT CUSTOMER SIGNALS
# ============================================================

def _contains_any(
    text: str,
    phrases: list[str],
) -> bool:
    """
    Check whether any phrase occurs positively.
    """

    tokens = tokenize(text)

    for phrase in phrases:

        phrase_tokens = tokenize(
            phrase
        )

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
    Detect ONLY explicit willingness to pay.

    Important examples:

        "I want to pay"
            -> True

        "I will try again"
            -> True

        "I forgot to complete the payment"
            -> False

        "I don't want to pay"
            -> False

    Merely mentioning payment completion does not imply
    willingness.
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

        "i can complete it",
        "i can finish it",

        "i am willing to pay",
        "i am ready to pay",

        "ready to pay",
        "happy to pay",

        "i will complete the payment",
        "i can complete the payment",
    ]

    negative_willingness = [

        "i do not want to pay",
        "i do not want to make the payment",

        "i will not pay",

        "i refuse to pay",

        "i do not want to pay this",
    ]

    if _contains_any(
        text,
        negative_willingness,
    ):
        return False

    return _contains_any(
        text,
        explicit_willingness,
    )


def _detect_negative_willingness(
    text: str,
) -> bool:
    """
    Detect explicit refusal.
    """

    negative_willingness = [

        "i do not want to pay",
        "i do not want to make the payment",
        "i will not pay",
        "i refuse to pay",
        "i do not want to pay this",
    ]

    return _contains_any(
        text,
        negative_willingness,
    )


def _detect_delay(
    text: str,
) -> bool:
    """
    Detect explicit payment-delay signals.
    """

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

        "after work",
        "later today",
    ]

    return _contains_any(
        text,
        delay_phrases,
    )


def _detect_contradiction(
    text: str,
) -> bool:
    """
    Detect contradictory payment intent.

    Example:

        "I want to pay but I do not want to pay."

    This should not be guessed.
    """

    willingness = _detect_willingness(
        text
    )

    refusal = _detect_negative_willingness(
        text
    )

    return willingness and refusal


# ============================================================
# 9. INTENT CLASSIFICATION
# ============================================================

def classify_intent(
    text: str,
) -> tuple[CustomerIntent, float]:
    """
    Determine customer intent.

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
            min(
                dispute_score / 10.0,
                1.0,
            ),
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
            min(
                security_score / 10.0,
                1.0,
            ),
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
            min(
                financial_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # CONTRADICTION
    # --------------------------------------------------------

    if _detect_contradiction(text):
        return (
            CustomerIntent.UNKNOWN,
            0.0,
        )

    # --------------------------------------------------------
    # DELAY
    # --------------------------------------------------------

    if _detect_delay(text):
        return (
            CustomerIntent.DELAYING_PAYMENT,
            0.90,
        )

    # --------------------------------------------------------
    # WILLINGNESS
    # --------------------------------------------------------

    if _detect_willingness(text):
        return (
            CustomerIntent.WILLING_TO_PAY,
            0.90,
        )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

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
    """
    Determine the customer's problem.

    Priority is based on evidence and safety:

        DISPUTE
        SECURITY
        AUTHENTICATION
        FINANCIAL
        TECHNICAL
        CHECKOUT
        TIMING
        UNKNOWN

    Important:

    We do not simply use the highest raw score because some
    categories have naturally stronger phrases.
    """

    # --------------------------------------------------------
    # Calculate all scores once.
    # --------------------------------------------------------

    scores: dict[ProblemType, float] = {}

    for problem_type, patterns in PROBLEM_PATTERNS.items():

        scores[problem_type] = _score_group(
            text,
            patterns,
        )

    dispute_score = scores.get(
        ProblemType.DISPUTE,
        0.0,
    )

    security_score = scores.get(
        ProblemType.SECURITY_ACCESS,
        0.0,
    )

    authentication_score = scores.get(
        ProblemType.AUTHENTICATION,
        0.0,
    )

    financial_score = scores.get(
        ProblemType.FINANCIAL,
        0.0,
    )

    technical_score = scores.get(
        ProblemType.TECHNICAL,
        0.0,
    )

    checkout_score = scores.get(
        ProblemType.CHECKOUT_ABANDONMENT,
        0.0,
    )

    timing_score = scores.get(
        ProblemType.TIMING,
        0.0,
    )

    # --------------------------------------------------------
    # 1. DISPUTE
    # --------------------------------------------------------

    if dispute_score >= 6.0:
        return (
            ProblemType.DISPUTE,
            min(
                dispute_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # 2. SECURITY
    # --------------------------------------------------------

    if security_score >= 6.0:
        return (
            ProblemType.SECURITY_ACCESS,
            min(
                security_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # 3. AUTHENTICATION
    # --------------------------------------------------------

    if authentication_score >= 6.0:
        return (
            ProblemType.AUTHENTICATION,
            min(
                authentication_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # 4. FINANCIAL
    #
    # Financial evidence gets priority over timing.
    #
    # Example:
    #
    # "I can't pay until my salary comes."
    #
    # This is financial difficulty, NOT merely timing.
    # --------------------------------------------------------

    if financial_score >= 5.0:
        return (
            ProblemType.FINANCIAL,
            min(
                financial_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # 5. TECHNICAL
    #
    # Technical evidence is checked BEFORE checkout/timing.
    # This prevents:
    #
    # "bank app is not working and I will try again"
    #
    # from being lost because of another weak signal.
    # --------------------------------------------------------

    if technical_score >= 5.0:
        return (
            ProblemType.TECHNICAL,
            min(
                technical_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # 6. CHECKOUT
    # --------------------------------------------------------

    if checkout_score >= 5.0:
        return (
            ProblemType.CHECKOUT_ABANDONMENT,
            min(
                checkout_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # 7. TIMING
    # --------------------------------------------------------

    if timing_score >= 5.0:
        return (
            ProblemType.TIMING,
            min(
                timing_score / 10.0,
                1.0,
            ),
        )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return (
        ProblemType.UNKNOWN,
        0.0,
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
    """
    Convert diagnosis into a bounded recovery action.

    IMPORTANT:

    Unknown intent does NOT automatically mean human escalation.

    Example:

        "My bank server is down."

    Intent:
        UNKNOWN

    Problem:
        TECHNICAL

    Safe action:
        OFFER_ALTERNATE_PAYMENT
    """

    # ========================================================
    # 1. SAFETY OVERRIDES EVERYTHING
    # ========================================================

    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    if contradiction:
        return RecoveryAction.HUMAN_ESCALATION

    # ========================================================
    # 2. HIGH-RISK PROBLEM TYPES
    # ========================================================

    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if customer_intent == CustomerIntent.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if problem_type in {
        ProblemType.SECURITY_ACCESS,
        ProblemType.AUTHENTICATION,
    }:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.SECURITY_CONCERN:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.FINANCIAL_DIFFICULTY:
        return RecoveryAction.HUMAN_ESCALATION

    # ========================================================
    # 3. TIMING
    # ========================================================

    if (
        problem_type == ProblemType.TIMING
        or delay_signal
        or customer_intent
        == CustomerIntent.DELAYING_PAYMENT
    ):
        return RecoveryAction.SCHEDULE_REMINDER

    # ========================================================
    # 4. TECHNICAL
    # ========================================================

    if problem_type == ProblemType.TECHNICAL:

        if willingness_to_pay:
            return RecoveryAction.OFFER_RETRY

        # Unknown intent is safe here.
        #
        # Example:
        # "My bank server is down."
        #
        # We don't know whether the customer is willing,
        # but we know the payment problem is technical.
        #
        # Offering an alternate payment method is bounded
        # and safe.

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    # ========================================================
    # 5. CHECKOUT ABANDONMENT
    # ========================================================

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:

        # Checkout abandonment itself is sufficient evidence
        # for a safe retry/resume action.
        #
        # We do NOT require explicit willingness.
        #
        # Example:
        # "I forgot to complete the payment."
        #
        # Intent = UNKNOWN
        # Action = OFFER_RETRY

        return RecoveryAction.OFFER_RETRY

    # ========================================================
    # 6. EXPLICIT WILLINGNESS
    # ========================================================

    if (
        customer_intent
        == CustomerIntent.WILLING_TO_PAY
        or willingness_to_pay
    ):
        return RecoveryAction.OFFER_RETRY

    # ========================================================
    # 7. UNKNOWN
    # ========================================================

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# 12. EXPLANATION
# ============================================================

def _pretty(value) -> str:
    """
    Convert enum values into readable text.
    """

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
    """
    Generate an explainable diagnosis summary.
    """

    problem_text = _pretty(
        problem_type
    )

    intent_text = _pretty(
        customer_intent
    )

    action_text = _pretty(
        recommended_action
    )

    signals: list[str] = []

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
    """
    Main AI reasoning pipeline.
    """

    normalized = normalize_text(
        message
    )

    # ========================================================
    # EMPTY MESSAGE
    # ========================================================

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

    # ========================================================
    # SAFETY
    # ========================================================

    sensitive = contains_sensitive_information(
        message
    )

    # ========================================================
    # EXPLICIT SIGNALS
    # ========================================================

    willingness_to_pay = _detect_willingness(
        normalized
    )

    delay_signal = _detect_delay(
        normalized
    )

    contradiction = _detect_contradiction(
        normalized
    )

    # ========================================================
    # PROBLEM
    # ========================================================

    problem_type, problem_confidence = classify_problem(
        normalized
    )

    # ========================================================
    # INTENT
    # ========================================================

    customer_intent, intent_confidence = classify_intent(
        normalized
    )

    # ========================================================
    # CONTRADICTION
    # ========================================================

    if contradiction:

        customer_intent = CustomerIntent.UNKNOWN
        intent_confidence = 0.0

    # ========================================================
    # SENSITIVE INFORMATION
    # ========================================================

    if sensitive:

        # If the exact problem cannot be identified,
        # classify it conservatively as authentication.
        if problem_type == ProblemType.UNKNOWN:

            problem_type = ProblemType.AUTHENTICATION
            problem_confidence = 0.90

        customer_intent = (
            CustomerIntent.SECURITY_CONCERN
        )

        intent_confidence = 0.95

    # ========================================================
    # FINANCIAL OVERRIDE
    #
    # Financial difficulty must dominate generic delay.
    #
    # Example:
    #
    # "I can't pay until my salary comes."
    #
    # This is:
    #
    # FINANCIAL
    # FINANCIAL_DIFFICULTY
    #
    # NOT:
    #
    # TIMING
    # ========================================================

    if (
        problem_type == ProblemType.FINANCIAL
        and not sensitive
    ):

        customer_intent = (
            CustomerIntent.FINANCIAL_DIFFICULTY
        )

        intent_confidence = max(
            intent_confidence,
            0.90,
        )

    # ========================================================
    # SECURITY / AUTHENTICATION OVERRIDE
    # ========================================================

    if (
        problem_type
        in {
            ProblemType.SECURITY_ACCESS,
            ProblemType.AUTHENTICATION,
        }
        and not sensitive
    ):

        if (
            customer_intent
            not in {
                CustomerIntent.DISPUTE,
                CustomerIntent.FINANCIAL_DIFFICULTY,
            }
        ):

            # Security-specific problems should not be
            # interpreted as willingness/delay.
            if problem_type in {
                ProblemType.SECURITY_ACCESS,
                ProblemType.AUTHENTICATION,
            }:

                if customer_intent == CustomerIntent.UNKNOWN:
                    pass

    # ========================================================
    # DISPUTE OVERRIDE
    # ========================================================

    if problem_type == ProblemType.DISPUTE:

        customer_intent = (
            CustomerIntent.DISPUTE
        )

        intent_confidence = max(
            intent_confidence,
            0.90,
        )

    # ========================================================
    # DELAY OVERRIDE
    #
    # Delay wins over generic willingness.
    #
    # Example:
    #
    # "I will pay tomorrow."
    #
    # Internal:
    #
    # willingness = True
    # delay = True
    #
    # External:
    #
    # DELAYING_PAYMENT
    # ========================================================

    if (
        delay_signal
        and not sensitive
        and problem_type
        not in {
            ProblemType.FINANCIAL,
            ProblemType.DISPUTE,
            ProblemType.SECURITY_ACCESS,
            ProblemType.AUTHENTICATION,
        }
    ):

        customer_intent = (
            CustomerIntent.DELAYING_PAYMENT
        )

        intent_confidence = max(
            intent_confidence,
            0.90,
        )

    # ========================================================
    # CHECKOUT INTENT
    #
    # Checkout abandonment DOES NOT automatically mean
    # willingness.
    #
    # "I forgot to complete the payment."
    #
    # => UNKNOWN
    #
    # "I forgot to complete the payment.
    #  I want to finish it."
    #
    # => WILLING_TO_PAY
    # ========================================================

    if (
        problem_type
        == ProblemType.CHECKOUT_ABANDONMENT
        and not delay_signal
        and not sensitive
    ):

        if not willingness_to_pay:

            customer_intent = (
                CustomerIntent.UNKNOWN
            )

            intent_confidence = 0.0

    # ========================================================
    # UNKNOWN PROBLEM
    # ========================================================

    if problem_type == ProblemType.UNKNOWN:

        customer_intent = (
            customer_intent
            if customer_intent
            in {
                CustomerIntent.DISPUTE,
                CustomerIntent.SECURITY_CONCERN,
                CustomerIntent.FINANCIAL_DIFFICULTY,
                CustomerIntent.DELAYING_PAYMENT,
                CustomerIntent.WILLING_TO_PAY,
            }
            else CustomerIntent.UNKNOWN
        )

    # ========================================================
    # OVERALL CONFIDENCE
    # ========================================================

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

    elif problem_type == ProblemType.UNKNOWN:

        overall_confidence = (
            intent_confidence
        )

    elif customer_intent == CustomerIntent.UNKNOWN:

        # IMPORTANT:
        #
        # A known problem with unknown intent is still
        # meaningful.
        #
        # Example:
        #
        # "My bank server is down."
        #
        # Problem confidence = high
        # Intent confidence = 0
        #
        # Overall confidence should NOT become unsafe.
        overall_confidence = (
            problem_confidence
        )

    else:

        overall_confidence = (
            problem_confidence * 0.60
            + intent_confidence * 0.40
        )

    # ========================================================
    # RECOVERY ACTION
    # ========================================================

    recommended_action = choose_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
        contradiction=contradiction,
        sensitive=sensitive,
        confidence=overall_confidence,
    )

    # ========================================================
    # EXPLANATION
    # ========================================================

    explanation = build_explanation(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=recommended_action,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
        willingness_to_pay=willingness_to_pay,
        delay_signal=delay_signal,
    )

    # ========================================================
    # RESULT
    # ========================================================

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
    Backward-compatible problem detection helper.
    """

    problem, _ = classify_problem(
        message
    )

    return problem