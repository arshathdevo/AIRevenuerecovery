from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.models.revenue import (
    CustomerIntent,
    ProblemType,
    RecoveryAction,
)


# ============================================================
# NORMALIZATION
# ============================================================

_CONTRACTIONS = {
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
    "aren't": "are not",
    "arent": "are not",
    "weren't": "were not",
    "werent": "were not",
    "i'm": "i am",
    "im": "i am",
    "i'll": "i will",
    "ill": "i will",
    "i'd": "i would",
    "id": "i would",
    "i've": "i have",
    "ive": "i have",
}


def normalize_text(text: str) -> str:
    """
    Normalize customer text without destroying sentence structure.

    We intentionally keep periods and sentence boundaries because
    negation can be clause-specific.
    """
    if not text:
        return ""

    text = text.lower().strip()

    for contraction, replacement in _CONTRACTIONS.items():
        text = re.sub(
            rf"\b{re.escape(contraction)}\b",
            replacement,
            text,
        )

    # Normalize punctuation except sentence boundaries.
    text = re.sub(r"[^a-z0-9\s.!?,']", " ", text)

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# SENSITIVE INFORMATION
# ============================================================

_SENSITIVE_PATTERNS = [
    r"\bupi\s+pin\b",
    r"\bpin\s+(?:number|code)\b",
    r"\botp\b",
    r"\bone\s*time\s*password\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bsecurity\s+code\b",
    r"\bpassword\b",
    r"\bpasscode\b",
    r"\bcard\s+number\b",
    r"\bcredit\s+card\b",
    r"\bdebit\s+card\b",
]


def contains_sensitive_information(text: str) -> bool:
    normalized = normalize_text(text)

    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    # Detect long digit sequences that could represent
    # credentials/card/account information.
    if re.search(r"\b\d{6,19}\b", normalized):
        return True

    return False


def redact_sensitive_information(text: str) -> str:
    """
    Redact obvious sensitive information before storing/logging it.
    """
    if not text:
        return text

    redacted = text

    for pattern in _SENSITIVE_PATTERNS:
        redacted = re.sub(
            pattern,
            "[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )

    redacted = re.sub(
        r"\b\d{6,19}\b",
        "[REDACTED]",
        redacted,
    )

    return redacted


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class Pattern:
    """
    A classification pattern.

    phrase:
        Human-readable phrase/pattern.

    weight:
        Evidence strength.

    regex:
        Optional regex for variable language.
    """

    phrase: str
    weight: float = 1.0
    regex: str | None = None


@dataclass(frozen=True)
class Evidence:
    category: str
    phrase: str
    weight: float
    start: int = -1
    end: int = -1
    negated: bool = False


@dataclass
class DiagnosisAnalysis:
    problem_type: ProblemType
    customer_intent: CustomerIntent
    recommended_action: RecoveryAction
    explanation: str

    problem_evidence: list[Evidence] = field(default_factory=list)
    intent_evidence: list[Evidence] = field(default_factory=list)

    willingness_to_pay: bool = False
    delay_signal: bool = False
    contradiction: bool = False
    sensitive: bool = False

    problem_confidence: float = 0.0
    intent_confidence: float = 0.0
    overall_confidence: float = 0.0


# ============================================================
# PROBLEM PATTERNS
# ============================================================

PROBLEM_PATTERNS: dict[ProblemType, list[Pattern]] = {

    ProblemType.TECHNICAL: [
        Pattern("bank app is not working", 1.00),
        Pattern("bank application is not working", 1.00),
        Pattern("payment app is not working", 1.00),
        Pattern("payment application is not working", 1.00),
        Pattern("app is not working", 0.95),

        Pattern("bank server is down", 1.00),
        Pattern("server is down", 0.90),

        Pattern("bank problem", 0.85),
        Pattern("bank issue", 0.85),
        Pattern("payment app problem", 0.90),
        Pattern("payment app issue", 0.90),

        Pattern("network problem", 0.95),
        Pattern("network issue", 0.95),
        Pattern("poor network", 0.95),
        Pattern("bad network", 0.90),

        Pattern("internet problem", 0.95),
        Pattern("internet issue", 0.95),
        Pattern("connection problem", 0.90),
        Pattern("connection issue", 0.90),

        Pattern("payment timed out", 1.00),
        Pattern("payment timeout", 1.00),
        Pattern("transaction timed out", 1.00),
        Pattern("transaction timeout", 1.00),

        Pattern("technical problem", 1.00),
        Pattern("technical issue", 1.00),
        Pattern("system error", 1.00),
        Pattern("gateway error", 1.00),
        Pattern("gateway problem", 1.00),

        Pattern("payment failed", 0.85),
        Pattern("transaction failed", 0.85),
    ],

    ProblemType.CHECKOUT_ABANDONMENT: [
        Pattern("forgot to complete the payment", 1.00),
        Pattern("forgot to finish the payment", 1.00),
        Pattern("forgot to make the payment", 1.00),
        Pattern("forgot the payment", 0.95),
        Pattern("forgot to pay", 0.95),

        Pattern("did not complete the payment", 1.00),
        Pattern("did not finish the payment", 1.00),
        Pattern("did not complete payment", 1.00),
        Pattern("did not finish payment", 1.00),

        Pattern("closed the payment page", 1.00),
        Pattern("payment page closed", 1.00),
        Pattern("closed the checkout page", 1.00),

        Pattern("left the payment page", 0.95),
        Pattern("left the checkout page", 0.95),

        Pattern("abandoned payment", 1.00),
        Pattern("abandoned checkout", 1.00),

        Pattern("payment not completed", 1.00),
        Pattern("checkout not completed", 1.00),
    ],

    ProblemType.FINANCIAL: [
        Pattern("not enough money", 1.00),
        Pattern("not enough funds", 1.00),
        Pattern("insufficient funds", 1.00),
        Pattern("no money", 0.95),

        Pattern("cannot afford", 1.00),
        Pattern("cannot pay", 1.00),
        Pattern("cannot make the payment", 1.00),
        Pattern("cannot make payment", 1.00),

        Pattern("financial problem", 1.00),
        Pattern("financial issue", 1.00),
        Pattern("money problem", 0.95),
        Pattern("money issue", 0.95),
        Pattern("cash problem", 0.90),

        Pattern("short of money", 1.00),
        Pattern("low balance", 0.95),
        Pattern("broke", 0.90),

        Pattern(
            "waiting for salary",
            1.00,
            regex=r"\bwaiting\s+for\s+(?:my\s+)?salary\b",
        ),
        Pattern(
            "until salary comes",
            1.00,
            regex=r"\buntil\s+(?:my\s+)?salary\s+(?:comes|arrives)\b",
        ),
        Pattern(
            "salary comes",
            0.95,
            regex=r"\bsalary\s+(?:comes|arrives)\b",
        ),
        Pattern(
            "salary arrives",
            0.95,
            regex=r"\bsalary\s+(?:comes|arrives)\b",
        ),
    ],

    ProblemType.TIMING: [
        Pattern("pay tomorrow", 1.00),
        Pattern("payment tomorrow", 1.00),

        Pattern("pay later", 1.00),
        Pattern("payment later", 1.00),

        Pattern("not today", 1.00),
        Pattern("busy today", 0.95),

        Pattern("pay next week", 1.00),
        Pattern("pay next month", 1.00),

        Pattern("in a few days", 0.95),
        Pattern("after work", 0.90),
        Pattern("when i get time", 0.90),

        Pattern(
            "will pay later",
            1.00,
            regex=r"\bwill\s+pay\s+(?:later|tomorrow|next\s+week|next\s+month)\b",
        ),
    ],

    ProblemType.AUTHENTICATION: [
        Pattern("forgot my upi pin", 1.00),
        Pattern("forgot upi pin", 1.00),
        Pattern("forgot my pin", 0.95),
        Pattern("forgot the pin", 0.95),

        Pattern("account is locked", 1.00),
        Pattern("account locked", 1.00),
        Pattern("locked out", 1.00),

        Pattern("cannot log in", 1.00),
        Pattern("cannot login", 1.00),
        Pattern("unable to log in", 1.00),
        Pattern("unable to login", 1.00),

        Pattern("login problem", 0.95),
        Pattern("login issue", 0.95),
        Pattern("authentication problem", 1.00),
        Pattern("authentication issue", 1.00),
    ],

    ProblemType.SECURITY_ACCESS: [
        Pattern("phone was stolen", 1.00),
        Pattern("phone stolen", 1.00),
        Pattern("lost my phone", 1.00),
        Pattern("phone is lost", 1.00),

        Pattern("cannot access my payment app", 1.00),
        Pattern("cannot access payment app", 1.00),
        Pattern("unable to access payment app", 1.00),

        Pattern("cannot access my account", 0.95),
        Pattern("unable to access my account", 0.95),

        Pattern("security concern", 1.00),
        Pattern("security issue", 1.00),
        Pattern("security problem", 1.00),

        Pattern("account compromised", 1.00),
        Pattern("suspicious access", 1.00),
    ],

    ProblemType.DISPUTE: [
        Pattern("paid the wrong vendor", 1.00),
        Pattern("paid wrong vendor", 1.00),
        Pattern("wrong vendor", 1.00),
        Pattern("wrong merchant", 1.00),
        Pattern("wrong payment", 0.95),

        Pattern("charged twice", 1.00),
        Pattern("charged two times", 1.00),
        Pattern("charged multiple times", 1.00),

        Pattern("duplicate charge", 1.00),
        Pattern("duplicate payment", 1.00),

        Pattern("do not recognize this payment", 1.00),
        Pattern("do not recognize the payment", 1.00),
        Pattern("unrecognized payment", 1.00),
        Pattern("unknown payment", 1.00),
        Pattern("fraudulent payment", 1.00),
    ],
}


# ============================================================
# INTENT PATTERNS
# ============================================================

WILLING_PATTERNS = [
    Pattern("i want to pay", 1.00),
    Pattern("i want to complete the payment", 1.00),
    Pattern("i want to finish the payment", 1.00),

    Pattern("i will pay", 1.00),
    Pattern("i can pay", 1.00),
    Pattern("i can make the payment", 1.00),
    Pattern("i will make the payment", 1.00),

    Pattern("i will try again", 1.00),
    Pattern("i will retry", 1.00),
    Pattern("i can retry", 1.00),
    Pattern("i want to retry", 1.00),

    Pattern("i will complete it", 1.00),
    Pattern("i want to complete it", 1.00),

    Pattern("i am willing to pay", 1.00),
    Pattern("i am ready to pay", 1.00),
    Pattern("ready to pay", 1.00),
    Pattern("happy to pay", 1.00),
]


NEGATIVE_WILLING_PATTERNS = [
    Pattern("i do not want to pay", 1.00),
    Pattern("i will not pay", 1.00),
    Pattern("i do not want to make the payment", 1.00),
    Pattern("i refuse to pay", 1.00),
    Pattern("i refuse payment", 1.00),
]


DELAY_PATTERNS = [
    "tomorrow",
    "later",
    "not today",
    "next week",
    "next month",
    "in a few days",
    "after work",
    "when i get time",
    "busy today",
]


# ============================================================
# HELPERS
# ============================================================

def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    normalized = normalize_text(text)

    for phrase in phrases:
        if phrase in normalized:
            return True

    return False


def _find_phrase_occurrences(
    text: str,
    phrase: str,
) -> list[tuple[int, int]]:
    """
    Find exact phrase occurrences.

    We use word boundaries so that 'pay' does not accidentally
    match inside another word.
    """
    normalized = normalize_text(text)
    phrase = normalize_text(phrase)

    if not phrase:
        return []

    pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"

    return [
        (match.start(), match.end())
        for match in re.finditer(pattern, normalized)
    ]


def _is_negated_at(
    text: str,
    start: int,
    phrase: str | None = None,
) -> bool:
    """
    Determine whether a matched phrase is actually negated.

    IMPORTANT:

    'bank app is not working'
        -> NOT negated

    'I do not have a bank problem'
        -> 'bank problem' IS negated

    We therefore inspect the words immediately BEFORE the
    matched phrase rather than simply searching the whole
    sentence for 'not'.
    """
    normalized = normalize_text(text)

    before = normalized[:start].strip()

    if not before:
        return False

    # Only inspect the current clause.
    before = re.split(r"[.!?]", before)[-1].strip()

    words = before.split()

    if not words:
        return False

    # Most common explicit negation structures.
    negation_patterns = [
        r"\bdo not have\b$",
        r"\bdoes not have\b$",
        r"\bdid not have\b$",
        r"\bdo not\b$",
        r"\bdoes not\b$",
        r"\bdid not\b$",
        r"\bno\b$",
        r"\bwithout\b$",
        r"\bnever\b$",
    ]

    for pattern in negation_patterns:
        if re.search(pattern, before):
            return True

    # Handle structures such as:
    #
    # "I have no bank problem"
    # "There is no bank issue"
    #
    recent = " ".join(words[-4:])

    if re.search(r"\bno\s+(?:bank|payment|technical|network)\b", recent):
        return True

    return False


def _fuzzy_phrase_match(
    text: str,
    phrase: str,
    threshold: float = 0.90,
) -> bool:
    """
    Kept for backwards compatibility.

    Fuzzy matching is deliberately disabled in the core
    diagnosis engine because approximate matches can produce
    unsafe payment classifications.

    Exact/regex evidence is used instead.
    """
    return False


def _score_group(
    text: str,
    patterns: list[Pattern],
    category: str,
) -> tuple[float, list[Evidence]]:
    """
    Score one classification group.
    """
    normalized = normalize_text(text)

    score = 0.0
    evidence: list[Evidence] = []

    for pattern in patterns:

        occurrences: list[tuple[int, int]] = []

        # Regex pattern.
        if pattern.regex:
            for match in re.finditer(
                pattern.regex,
                normalized,
            ):
                occurrences.append(
                    (match.start(), match.end())
                )

        # Exact phrase.
        else:
            occurrences.extend(
                _find_phrase_occurrences(
                    normalized,
                    pattern.phrase,
                )
            )

        for start, end in occurrences:

            if _is_negated_at(
                normalized,
                start,
                pattern.phrase,
            ):
                evidence.append(
                    Evidence(
                        category=category,
                        phrase=pattern.phrase,
                        weight=pattern.weight,
                        start=start,
                        end=end,
                        negated=True,
                    )
                )
                continue

            evidence.append(
                Evidence(
                    category=category,
                    phrase=pattern.phrase,
                    weight=pattern.weight,
                    start=start,
                    end=end,
                    negated=False,
                )
            )

            score += pattern.weight

    return score, evidence


def _ranked(
    text: str,
) -> list[tuple[ProblemType, float, list[Evidence]]]:
    """
    Rank problem categories by evidence.
    """
    results = []

    for problem_type, patterns in PROBLEM_PATTERNS.items():
        score, evidence = _score_group(
            text,
            patterns,
            problem_type.value,
        )

        positive_evidence = [
            item
            for item in evidence
            if not item.negated
        ]

        if positive_evidence:
            results.append(
                (
                    problem_type,
                    score,
                    positive_evidence,
                )
            )

    results.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return results


def get_best_category(
    text: str,
) -> tuple[ProblemType, float, list[Evidence]]:
    ranked = _ranked(text)

    if not ranked:
        return (
            ProblemType.UNKNOWN,
            0.0,
            [],
        )

    # Safety priority for high-risk categories.
    priority = {
        ProblemType.DISPUTE: 7,
        ProblemType.SECURITY_ACCESS: 6,
        ProblemType.AUTHENTICATION: 5,
        ProblemType.FINANCIAL: 4,
        ProblemType.TECHNICAL: 3,
        ProblemType.CHECKOUT_ABANDONMENT: 2,
        ProblemType.TIMING: 1,
        ProblemType.UNKNOWN: 0,
    }

    # First result is normally strongest.
    best_type, best_score, best_evidence = ranked[0]

    # If another category is close and is safety-critical,
    # prefer the safety category.
    for candidate_type, candidate_score, candidate_evidence in ranked[1:]:

        if (
            candidate_type in {
                ProblemType.DISPUTE,
                ProblemType.SECURITY_ACCESS,
                ProblemType.AUTHENTICATION,
            }
            and candidate_score >= best_score * 0.70
            and priority[candidate_type] > priority[best_type]
        ):
            best_type = candidate_type
            best_score = candidate_score
            best_evidence = candidate_evidence

    # Confidence is evidence based, not arbitrary.
    confidence = min(
        1.0,
        0.50 + (best_score * 0.35),
    )

    return (
        best_type,
        confidence,
        best_evidence,
    )


# ============================================================
# INTENT DETECTION
# ============================================================

def _detect_willingness(
    text: str,
) -> tuple[bool, list[Evidence]]:
    normalized = normalize_text(text)

    positive: list[Evidence] = []
    negative: list[Evidence] = []

    for pattern in WILLING_PATTERNS:
        for start, end in _find_phrase_occurrences(
            normalized,
            pattern.phrase,
        ):
            positive.append(
                Evidence(
                    category="WILLING",
                    phrase=pattern.phrase,
                    weight=pattern.weight,
                    start=start,
                    end=end,
                )
            )

    for pattern in NEGATIVE_WILLING_PATTERNS:
        for start, end in _find_phrase_occurrences(
            normalized,
            pattern.phrase,
        ):
            negative.append(
                Evidence(
                    category="NOT_WILLING",
                    phrase=pattern.phrase,
                    weight=pattern.weight,
                    start=start,
                    end=end,
                )
            )

    # Explicit refusal wins over willingness.
    if negative:
        return False, negative

    if positive:
        return True, positive

    return False, []


def _detect_delay(
    text: str,
) -> tuple[bool, list[Evidence]]:
    normalized = normalize_text(text)

    evidence: list[Evidence] = []

    for phrase in DELAY_PATTERNS:
        for start, end in _find_phrase_occurrences(
            normalized,
            phrase,
        ):
            evidence.append(
                Evidence(
                    category="DELAY",
                    phrase=phrase,
                    weight=1.0,
                    start=start,
                    end=end,
                )
            )

    return bool(evidence), evidence


def _detect_contradiction(
    text: str,
) -> bool:
    """
    Detect explicit contradictory payment intent.

    Example:

        I want to pay
        +
        I do not want to pay

    => contradiction
    """
    normalized = normalize_text(text)

    has_positive = False
    has_negative = False

    for pattern in WILLING_PATTERNS:
        if _find_phrase_occurrences(
            normalized,
            pattern.phrase,
        ):
            has_positive = True
            break

    for pattern in NEGATIVE_WILLING_PATTERNS:
        if _find_phrase_occurrences(
            normalized,
            pattern.phrase,
        ):
            has_negative = True
            break

    return has_positive and has_negative


def classify_intent(
    text: str,
) -> tuple[CustomerIntent, float, list[Evidence], bool, bool]:
    """
    Return:

        intent
        confidence
        evidence
        willingness
        delay
    """
    normalized = normalize_text(text)

    contradiction = _detect_contradiction(normalized)

    if contradiction:
        return (
            CustomerIntent.UNKNOWN,
            0.0,
            [],
            False,
            False,
        )

    # Safety categories first.
    problem_type, _, _ = get_best_category(normalized)

    if problem_type == ProblemType.DISPUTE:
        return (
            CustomerIntent.DISPUTE,
            1.0,
            [],
            False,
            False,
        )

    if problem_type in {
        ProblemType.SECURITY_ACCESS,
    }:
        return (
            CustomerIntent.SECURITY_CONCERN,
            1.0,
            [],
            False,
            False,
        )

    # Authentication can be security-related.
    if problem_type == ProblemType.AUTHENTICATION:
        return (
            CustomerIntent.SECURITY_CONCERN
            if "pin" in normalized
            else CustomerIntent.UNKNOWN,
            0.90 if "pin" in normalized else 0.60,
            [],
            False,
            False,
        )

    # Financial inability overrides willingness.
    if problem_type == ProblemType.FINANCIAL:
        return (
            CustomerIntent.FINANCIAL_DIFFICULTY,
            1.0,
            [],
            False,
            False,
        )

    willingness, willingness_evidence = _detect_willingness(
        normalized
    )

    delay, delay_evidence = _detect_delay(
        normalized
    )

    evidence = (
        willingness_evidence
        + delay_evidence
    )

    if willingness and delay:
        return (
            CustomerIntent.DELAYING_PAYMENT,
            0.95,
            evidence,
            True,
            True,
        )

    if delay:
        return (
            CustomerIntent.DELAYING_PAYMENT,
            0.90,
            evidence,
            False,
            True,
        )

    if willingness:
        return (
            CustomerIntent.WILLING_TO_PAY,
            0.95,
            evidence,
            True,
            False,
        )

    return (
        CustomerIntent.UNKNOWN,
        0.40,
        evidence,
        False,
        False,
    )


# ============================================================
# PROBLEM CLASSIFICATION
# ============================================================

def classify_problem(
    text: str,
) -> tuple[ProblemType, float, list[Evidence]]:
    return get_best_category(text)


# ============================================================
# RECOVERY POLICY
# ============================================================

def choose_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    problem_confidence: float = 1.0,
    *,
    sensitive: bool = False,
    contradiction: bool = False,
) -> RecoveryAction:
    """
    Deterministic recovery policy.

    IMPORTANT:
    We do NOT use overall confidence here.

    Unknown intent does NOT automatically mean human escalation.

    Example:

        "My bank server is down."

    Problem is clearly TECHNICAL.
    Intent is UNKNOWN.

    Safe action:
        OFFER_ALTERNATE_PAYMENT

    Example:

        "I forgot to complete the payment."

    Problem is clearly CHECKOUT_ABANDONMENT.
    Intent is UNKNOWN.

    Safe action:
        OFFER_RETRY
    """

    # Never automate sensitive situations.
    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    # Contradictory intent requires human review.
    if contradiction:
        return RecoveryAction.HUMAN_ESCALATION

    # If we genuinely don't understand the problem,
    # do not guess.
    if (
        problem_type == ProblemType.UNKNOWN
        or problem_confidence < 0.40
    ):
        return RecoveryAction.HUMAN_ESCALATION

    # Disputes must stop automated recovery.
    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    # Security/access problems require human handling.
    if problem_type == ProblemType.SECURITY_ACCESS:
        return RecoveryAction.HUMAN_ESCALATION

    # Authentication problems require human handling.
    if problem_type == ProblemType.AUTHENTICATION:
        return RecoveryAction.HUMAN_ESCALATION

    # Financial hardship requires human/merchant handling.
    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    # Timing requests are perfect candidates for scheduling.
    if (
        problem_type == ProblemType.TIMING
        or customer_intent == CustomerIntent.DELAYING_PAYMENT
    ):
        return RecoveryAction.SCHEDULE_REMINDER

    # Technical issue:
    #
    # Willing customer -> retry
    # Unknown intent -> alternate payment
    if problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:
            return RecoveryAction.OFFER_RETRY

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    # Checkout abandonment:
    #
    # Even if intent is unknown, retrying/resuming checkout
    # is a safe recovery action.
    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:
        return RecoveryAction.OFFER_RETRY

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# EXPLANATION
# ============================================================

def build_explanation(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    action: RecoveryAction,
    problem_evidence: list[Evidence] | None = None,
    intent_evidence: list[Evidence] | None = None,
) -> str:

    problem_evidence = problem_evidence or []
    intent_evidence = intent_evidence or []

    problem_reasons = [
        item.phrase
        for item in problem_evidence
        if not item.negated
    ]

    intent_reasons = [
        item.phrase
        for item in intent_evidence
    ]

    if problem_reasons:
        problem_reason = ", ".join(
            dict.fromkeys(problem_reasons)
        )
    else:
        problem_reason = "no strong problem evidence"

    if intent_reasons:
        intent_reason = ", ".join(
            dict.fromkeys(intent_reasons)
        )
    else:
        intent_reason = "no explicit payment intent"

    return (
        f"Problem classified as {problem_type.value} "
        f"based on: {problem_reason}. "
        f"Customer intent: {customer_intent.value} "
        f"based on: {intent_reason}. "
        f"Selected recovery action: {action.value}."
    )


# ============================================================
# COMPLETE ANALYSIS
# ============================================================

def analyze_message(
    text: str,
) -> DiagnosisAnalysis:
    normalized = normalize_text(text)

    sensitive = contains_sensitive_information(
        normalized
    )

    contradiction = _detect_contradiction(
        normalized
    )

    (
        problem_type,
        problem_confidence,
        problem_evidence,
    ) = classify_problem(normalized)

    (
        customer_intent,
        intent_confidence,
        intent_evidence,
        willingness,
        delay,
    ) = classify_intent(normalized)

    # Contradiction must force UNKNOWN intent.
    if contradiction:
        customer_intent = CustomerIntent.UNKNOWN
        intent_confidence = 0.0
        willingness = False

    action = choose_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        problem_confidence=problem_confidence,
        sensitive=sensitive,
        contradiction=contradiction,
    )

    # Overall confidence is informational only.
    if contradiction or sensitive:
        overall_confidence = 0.0
    else:
        overall_confidence = (
            problem_confidence * 0.60
            + intent_confidence * 0.40
        )

    explanation = build_explanation(
        problem_type=problem_type,
        customer_intent=customer_intent,
        action=action,
        problem_evidence=problem_evidence,
        intent_evidence=intent_evidence,
    )

    return DiagnosisAnalysis(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=action,
        explanation=explanation,
        problem_evidence=problem_evidence,
        intent_evidence=intent_evidence,
        willingness_to_pay=willingness,
        delay_signal=delay,
        contradiction=contradiction,
        sensitive=sensitive,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
        overall_confidence=overall_confidence,
    )


# ============================================================
# PUBLIC API
# ============================================================

def diagnose_message(
    text: str,
) -> DiagnosisAnalysis:
    """
    Main public diagnosis function.
    """
    return analyze_message(text)


def detect_problem(
    text: str,
) -> ProblemType:
    """
    Backwards-compatible helper.
    """
    problem_type, _, _ = classify_problem(text)
    return problem_type