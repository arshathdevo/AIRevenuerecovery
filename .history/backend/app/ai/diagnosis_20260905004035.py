import re
from dataclasses import dataclass

from app.models.revenue import (
    AIDiagnosis,
    CustomerIntent,
    ProblemType,
    RecoveryAction,
)


# ============================================================
# 1. DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class Pattern:
    phrase: str
    weight: float = 1.0


@dataclass(frozen=True)
class Evidence:
    category: str
    phrase: str
    weight: float


# ============================================================
# 2. CONTRACTION NORMALIZATION
# ============================================================

CONTRACTIONS = {
    "can't": "cannot",
    "cannot": "cannot",
    "won't": "will not",
    "wouldn't": "would not",
    "couldn't": "could not",
    "shouldn't": "should not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "i'm": "i am",
    "i'll": "i will",
    "i'd": "i would",
    "i've": "i have",
    "you're": "you are",
    "you'll": "you will",
    "you'd": "you would",
    "you've": "you have",
    "we're": "we are",
    "we'll": "we will",
    "we'd": "we would",
    "we've": "we have",
    "they're": "they are",
    "they'll": "they will",
    "they'd": "they would",
    "they've": "they have",
}


def normalize_text(text: str) -> str:
    """
    Normalize user text before analysis.

    Steps:
    1. Convert to lowercase.
    2. Expand common contractions.
    3. Remove punctuation.
    4. Collapse repeated whitespace.

    Example:
        "I don't have enough money."
        ->
        "i do not have enough money"
    """

    if not text:
        return ""

    text = text.lower().strip()

    # Expand contractions.
    # Sort longest first so multi-character forms are handled safely.
    for contraction, replacement in sorted(
        CONTRACTIONS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = re.sub(
            rf"(?<!\w){re.escape(contraction)}(?!\w)",
            replacement,
            text,
        )

    # Remove punctuation.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# 3. SENSITIVE INFORMATION DETECTION
# ============================================================

SENSITIVE_PATTERNS = [
    r"\bupi\s*pin\b",
    r"\bpin\b",
    r"\botp\b",
    r"\bone\s*time\s*password\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bcard\s*(?:number|no)\b",
    r"\bpassword\b",
    r"\bpasscode\b",
    r"\bsecurity\s*code\b",
]


def contains_sensitive_information(text: str) -> bool:
    """
    Detect potentially sensitive payment/authentication information.

    We intentionally err on the safe side.
    """

    normalized = normalize_text(text)

    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    # Detect long numeric sequences.
    # This prevents users from accidentally submitting card/account-like
    # numeric information to the recovery agent.
    if re.search(r"\b\d{6,}\b", normalized):
        return True

    return False


def redact_sensitive_information(text: str) -> str:
    """
    Replace detected sensitive information with [REDACTED].
    """

    if not text:
        return ""

    redacted = text

    # Redact explicit sensitive keywords and the value following them
    # when it looks like a credential.
    redacted = re.sub(
        r"(?i)\bupi\s*pin\b\s*[:\-]?\s*\d+",
        "[REDACTED]",
        redacted,
    )

    redacted = re.sub(
        r"(?i)\botp\b\s*[:\-]?\s*\d+",
        "[REDACTED]",
        redacted,
    )

    redacted = re.sub(
        r"(?i)\bcvv\b\s*[:\-]?\s*\d+",
        "[REDACTED]",
        redacted,
    )

    redacted = re.sub(
        r"(?i)\bcvc\b\s*[:\-]?\s*\d+",
        "[REDACTED]",
        redacted,
    )

    redacted = re.sub(
        r"(?i)\bpassword\b\s*[:\-]?\s*\S+",
        "[REDACTED]",
        redacted,
    )

    redacted = re.sub(
        r"\b\d{6,}\b",
        "[REDACTED]",
        redacted,
    )

    return redacted


# ============================================================
# 4. PROBLEM PATTERNS
# ============================================================

TECHNICAL_PATTERNS = [
    Pattern("bank app is not working", 1.00),
    Pattern("bank application is not working", 1.00),
    Pattern("payment app is not working", 1.00),
    Pattern("payment application is not working", 1.00),
    Pattern("app is not working", 0.95),
    Pattern("application is not working", 0.95),

    Pattern("bank server is down", 1.00),
    Pattern("server is down", 0.95),

    Pattern("bank problem", 0.90),
    Pattern("bank issue", 0.90),
    Pattern("payment app problem", 0.95),
    Pattern("payment app issue", 0.95),

    Pattern("network problem", 0.95),
    Pattern("network issue", 0.95),
    Pattern("poor network", 0.90),
    Pattern("bad network", 0.90),

    Pattern("internet problem", 0.95),
    Pattern("internet issue", 0.95),

    Pattern("connection problem", 0.95),
    Pattern("connection issue", 0.95),

    Pattern("payment timed out", 1.00),
    Pattern("payment timeout", 1.00),
    Pattern("transaction timed out", 1.00),
    Pattern("transaction timeout", 1.00),

    Pattern("technical problem", 1.00),
    Pattern("technical issue", 1.00),

    Pattern("system error", 0.95),
    Pattern("system problem", 0.95),

    Pattern("gateway error", 0.95),
    Pattern("gateway problem", 0.95),

    Pattern("payment failed", 0.90),
    Pattern("transaction failed", 0.90),
]


CHECKOUT_PATTERNS = [
    Pattern("forgot to complete payment", 1.00),
    Pattern("forgot to finish payment", 1.00),
    Pattern("forgot to make payment", 1.00),
    Pattern("forgot payment", 1.00),
    Pattern("forgot to pay", 1.00),

    Pattern("did not complete payment", 1.00),
    Pattern("did not finish payment", 1.00),

    Pattern("closed payment page", 1.00),
    Pattern("closed checkout page", 1.00),

    Pattern("left payment page", 0.95),
    Pattern("left checkout page", 0.95),

    Pattern("abandoned payment", 1.00),
    Pattern("abandoned checkout", 1.00),

    Pattern("payment not completed", 1.00),
    Pattern("checkout not completed", 1.00),
]


FINANCIAL_PATTERNS = [
    # Important:
    # These explicit forms are required because contraction normalization
    # changes "I don't have enough money" into
    # "i do not have enough money".
    Pattern("do not have enough money", 1.00),
    Pattern("do not have enough funds", 1.00),
    Pattern("do not have money", 0.95),
    Pattern("do not have funds", 0.95),

    Pattern("not enough money", 1.00),
    Pattern("not enough funds", 1.00),

    Pattern("insufficient funds", 1.00),
    Pattern("no money", 0.95),

    Pattern("cannot afford", 1.00),
    Pattern("cannot pay", 1.00),
    Pattern("cannot make payment", 1.00),

    Pattern("financial problem", 1.00),
    Pattern("financial issue", 1.00),

    Pattern("money problem", 0.95),
    Pattern("money issue", 0.95),
    Pattern("cash problem", 0.95),
    Pattern("cash issue", 0.95),

    Pattern("short of money", 1.00),
    Pattern("low balance", 0.95),
    Pattern("broke", 0.90),

    Pattern("waiting for salary", 1.00),
    Pattern("until salary comes", 1.00),
    Pattern("until salary arrives", 1.00),
    Pattern("salary comes", 0.95),
    Pattern("salary arrives", 0.95),
]


TIMING_PATTERNS = [
    Pattern("pay tomorrow", 1.00),
    Pattern("payment tomorrow", 1.00),

    Pattern("pay later", 1.00),
    Pattern("payment later", 1.00),

    Pattern("not today", 1.00),
    Pattern("busy today", 1.00),

    Pattern("next week", 1.00),
    Pattern("next month", 1.00),

    Pattern("in a few days", 1.00),
    Pattern("after work", 1.00),
    Pattern("when i get time", 1.00),

    Pattern("tomorrow", 0.85),
    Pattern("later", 0.80),
]


AUTHENTICATION_PATTERNS = [
    Pattern("forgot upi pin", 1.00),
    Pattern("forgot pin", 1.00),

    Pattern("account locked", 1.00),
    Pattern("locked out", 1.00),

    Pattern("cannot log in", 1.00),
    Pattern("cannot login", 1.00),
    Pattern("unable to log in", 1.00),
    Pattern("unable to login", 1.00),

    Pattern("login problem", 1.00),
    Pattern("login issue", 1.00),

    Pattern("authentication problem", 1.00),
    Pattern("authentication issue", 1.00),
]


SECURITY_PATTERNS = [
    Pattern("phone was stolen", 1.00),
    Pattern("phone stolen", 1.00),
    Pattern("lost my phone", 1.00),
    Pattern("phone is lost", 1.00),

    Pattern("cannot access payment app", 1.00),
    Pattern("unable to access payment app", 1.00),

    Pattern("cannot access account", 1.00),
    Pattern("unable to access account", 1.00),

    Pattern("security concern", 1.00),
    Pattern("security issue", 1.00),
    Pattern("security problem", 1.00),

    Pattern("account compromised", 1.00),
    Pattern("suspicious access", 1.00),
]


DISPUTE_PATTERNS = [
    Pattern("wrong vendor", 1.00),
    Pattern("wrong merchant", 1.00),
    Pattern("wrong payment", 1.00),

    Pattern("charged twice", 1.00),
    Pattern("charged two times", 1.00),
    Pattern("charged multiple times", 1.00),

    Pattern("duplicate charge", 1.00),
    Pattern("duplicate payment", 1.00),

    Pattern("do not recognize payment", 1.00),
    Pattern("unrecognized payment", 1.00),
    Pattern("unknown payment", 0.95),
    Pattern("fraudulent payment", 1.00),
]


# ============================================================
# 5. INTENT PATTERNS
# ============================================================

POSITIVE_WILLINGNESS_PATTERNS = [
    Pattern("i want to pay", 1.00),
    Pattern("i want to complete payment", 1.00),
    Pattern("i want to finish payment", 1.00),

    Pattern("i will pay", 1.00),
    Pattern("i can pay", 1.00),
    Pattern("i can make payment", 1.00),
    Pattern("i will make payment", 1.00),

    Pattern("i will try again", 1.00),
    Pattern("i will retry", 1.00),
    Pattern("i can retry", 1.00),
    Pattern("i want to retry", 1.00),

    Pattern("i want to complete it", 1.00),
    Pattern("i will complete it", 1.00),

    Pattern("i am willing to pay", 1.00),
    Pattern("i am ready to pay", 1.00),
    Pattern("i am ready", 0.90),
    Pattern("ready to pay", 1.00),
    Pattern("happy to pay", 1.00),
]


NEGATIVE_WILLINGNESS_PATTERNS = [
    Pattern("i do not want to pay", 1.00),
    Pattern("i will not pay", 1.00),
    Pattern("i do not want to make payment", 1.00),
    Pattern("i refuse to pay", 1.00),
    Pattern("i refuse payment", 1.00),
]


DELAY_PATTERNS = [
    Pattern("tomorrow", 1.00),
    Pattern("later", 0.95),
    Pattern("not today", 1.00),
    Pattern("next week", 1.00),
    Pattern("next month", 1.00),
    Pattern("in a few days", 1.00),
    Pattern("after work", 1.00),
    Pattern("when i get time", 1.00),
    Pattern("busy today", 1.00),
]


# ============================================================
# 6. PHRASE MATCHING
# ============================================================

def _find_phrase_occurrences(
    text: str,
    phrase: str,
) -> list[tuple[int, int]]:
    """
    Find exact phrase occurrences after normalization.
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
    Detect phrase-aware negation.

    IMPORTANT:
    We do NOT treat every occurrence of "not" before a phrase
    as negation.

    Example:

        "bank app is not working"
        -> technical evidence is valid

        "I do not have a bank problem"
        -> bank problem is negated

    This prevents broad negation from destroying legitimate
    technical evidence.
    """

    normalized = normalize_text(text)

    before = normalized[:start].strip()

    if not before:
        return False

    words = before.split()

    if not words:
        return False

    # Only inspect the recent context.
    recent = " ".join(words[-8:])

    # "I do not have ..."
    if re.search(
        r"\b(?:do|does|did)\s+not\s+have"
        r"(?:\s+any)?\s*$",
        recent,
    ):
        return True

    # "no ..."
    if re.search(r"\bno\s*$", recent):
        return True

    # "without ..."
    if re.search(r"\bwithout\s*$", recent):
        return True

    # "never ..."
    if re.search(r"\bnever\s*$", recent):
        return True

    return False


def _pattern_matches(
    text: str,
    pattern: Pattern,
) -> bool:
    """
    Check whether a pattern appears without being explicitly negated.
    """

    occurrences = _find_phrase_occurrences(
        text,
        pattern.phrase,
    )

    for start, _ in occurrences:
        if not _is_negated_at(
            text,
            start,
            pattern.phrase,
        ):
            return True

    return False


# ============================================================
# 7. EVIDENCE COLLECTION
# ============================================================

def _collect_evidence(
    text: str,
    patterns: list[Pattern],
    category: str,
) -> list[Evidence]:

    evidence: list[Evidence] = []

    for pattern in patterns:
        if _pattern_matches(text, pattern):
            evidence.append(
                Evidence(
                    category=category,
                    phrase=pattern.phrase,
                    weight=pattern.weight,
                )
            )

    return evidence


def _best_evidence(
    evidence: list[Evidence],
) -> Evidence | None:

    if not evidence:
        return None

    return max(
        evidence,
        key=lambda item: item.weight,
    )


# ============================================================
# 8. PROBLEM CLASSIFICATION
# ============================================================

def _classify_problem(
    text: str,
) -> tuple[ProblemType, float, list[Evidence]]:

    categories = [
        (
            ProblemType.TECHNICAL,
            "technical",
            TECHNICAL_PATTERNS,
        ),
        (
            ProblemType.CHECKOUT_ABANDONMENT,
            "checkout",
            CHECKOUT_PATTERNS,
        ),
        (
            ProblemType.FINANCIAL,
            "financial",
            FINANCIAL_PATTERNS,
        ),
        (
            ProblemType.TIMING,
            "timing",
            TIMING_PATTERNS,
        ),
        (
            ProblemType.AUTHENTICATION,
            "authentication",
            AUTHENTICATION_PATTERNS,
        ),
        (
            ProblemType.SECURITY_ACCESS,
            "security",
            SECURITY_PATTERNS,
        ),
        (
            ProblemType.DISPUTE,
            "dispute",
            DISPUTE_PATTERNS,
        ),
    ]

    best_problem = ProblemType.UNKNOWN
    best_score = 0.0
    best_evidence: list[Evidence] = []

    for problem_type, category, patterns in categories:

        evidence = _collect_evidence(
            text,
            patterns,
            category,
        )

        if not evidence:
            continue

        # Strongest evidence determines the category.
        score = max(
            item.weight
            for item in evidence
        )

        # Number of independent matching signals provides
        # a small confidence bonus.
        if len(evidence) >= 2:
            score = min(score + 0.10, 1.0)

        if score > best_score:
            best_score = score
            best_problem = problem_type
            best_evidence = evidence

    return (
        best_problem,
        round(best_score, 2),
        best_evidence,
    )


# ============================================================
# 9. INTENT CLASSIFICATION
# ============================================================

def _has_positive_willingness(text: str) -> bool:
    return any(
        _pattern_matches(text, pattern)
        for pattern in POSITIVE_WILLINGNESS_PATTERNS
    )


def _has_negative_willingness(text: str) -> bool:
    return any(
        _pattern_matches(text, pattern)
        for pattern in NEGATIVE_WILLINGNESS_PATTERNS
    )


def _has_delay_signal(text: str) -> bool:
    return any(
        _pattern_matches(text, pattern)
        for pattern in DELAY_PATTERNS
    )


def _classify_intent(
    text: str,
) -> tuple[CustomerIntent, float, bool]:

    positive = _has_positive_willingness(text)
    negative = _has_negative_willingness(text)
    delay = _has_delay_signal(text)

    # Contradiction is intentionally detected before everything else.
    if positive and negative:
        return (
            CustomerIntent.UNKNOWN,
            1.0,
            True,
        )

    # Financial/delay intent is handled here only as linguistic intent.
    if delay and positive:
        return (
            CustomerIntent.DELAYING_PAYMENT,
            1.0,
            False,
        )

    if delay:
        return (
            CustomerIntent.DELAYING_PAYMENT,
            0.90,
            False,
        )

    if positive:
        return (
            CustomerIntent.WILLING_TO_PAY,
            1.0,
            False,
        )

    if negative:
        return (
            CustomerIntent.UNKNOWN,
            1.0,
            False,
        )

    return (
        CustomerIntent.UNKNOWN,
        0.0,
        False,
    )


# ============================================================
# 10. POLICY ENGINE
# ============================================================

def _select_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    problem_confidence: float,
    intent_confidence: float,
    contradiction: bool,
    sensitive: bool,
) -> RecoveryAction:

    # --------------------------------------------------------
    # SAFETY OVERRIDES
    # --------------------------------------------------------

    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    if contradiction:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_confidence < 0.70:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # PROBLEM-SPECIFIC POLICY
    # --------------------------------------------------------

    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if problem_type == ProblemType.SECURITY_ACCESS:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.AUTHENTICATION:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.TIMING:
        return RecoveryAction.SCHEDULE_REMINDER

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:
        return RecoveryAction.OFFER_RETRY

    if problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:
            return RecoveryAction.OFFER_RETRY

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# 11. MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_message(text: str) -> AIDiagnosis:
    """
    Main deterministic AI diagnosis engine.

    Pipeline:

        Raw Message
             ↓
        Normalize
             ↓
        Sensitive Detection
             ↓
        Problem Evidence
             ↓
        Problem Classification
             ↓
        Intent Classification
             ↓
        Safety / Policy Engine
             ↓
        Recovery Action
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not text.strip():
        return AIDiagnosis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.UNKNOWN,
            recommended_action=RecoveryAction.HUMAN_ESCALATION,
            explanation="No customer message was provided.",
        )

    normalized = normalize_text(text)

    # --------------------------------------------------------
    # SENSITIVE INFORMATION
    # --------------------------------------------------------

    sensitive = contains_sensitive_information(text)

    if sensitive:
        return AIDiagnosis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.SECURITY_CONCERN,
            recommended_action=RecoveryAction.HUMAN_ESCALATION,
            explanation=(
                "The message appears to contain sensitive payment or "
                "authentication information. Automated recovery is stopped "
                "for safety."
            ),
        )

    # --------------------------------------------------------
    # PROBLEM
    # --------------------------------------------------------

    (
        problem_type,
        problem_confidence,
        problem_evidence,
    ) = _classify_problem(normalized)

    # --------------------------------------------------------
    # CUSTOMER INTENT
    # --------------------------------------------------------

    (
        customer_intent,
        intent_confidence,
        contradiction,
    ) = _classify_intent(normalized)

    # --------------------------------------------------------
    # OVERRIDE INTENT BASED ON PROBLEM TYPE
    # --------------------------------------------------------

    # Financial difficulty always wins over willingness.
    if problem_type == ProblemType.FINANCIAL:
        customer_intent = CustomerIntent.FINANCIAL_DIFFICULTY
        intent_confidence = max(intent_confidence, 1.0)

    # Dispute always means dispute intent.
    elif problem_type == ProblemType.DISPUTE:
        customer_intent = CustomerIntent.DISPUTE
        intent_confidence = max(intent_confidence, 1.0)

    # Security/authentication problems are security-related.
    elif problem_type in {
        ProblemType.SECURITY_ACCESS,
        ProblemType.AUTHENTICATION,
    }:
        customer_intent = CustomerIntent.SECURITY_CONCERN
        intent_confidence = max(intent_confidence, 1.0)

    # Contradiction always overrides normal intent.
    if contradiction:
        customer_intent = CustomerIntent.UNKNOWN
        intent_confidence = 1.0

    # --------------------------------------------------------
    # RECOVERY POLICY
    # --------------------------------------------------------

    action = _select_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        problem_confidence=problem_confidence,
        intent_confidence=intent_confidence,
        contradiction=contradiction,
        sensitive=sensitive,
    )

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    if contradiction:
        explanation = (
            "The customer expressed contradictory willingness to pay. "
            "Automated recovery is stopped and human review is required."
        )

    elif problem_type == ProblemType.UNKNOWN:
        explanation = (
            "The message does not contain enough reliable evidence to "
            "determine the customer's problem safely."
        )

    elif problem_type == ProblemType.FINANCIAL:
        explanation = (
            "The customer appears to be experiencing financial difficulty. "
            "Automated payment pressure is not appropriate, so the case "
            "should be escalated to a human."
        )

    elif problem_type == ProblemType.DISPUTE:
        explanation = (
            "The customer appears to dispute the payment. Recovery is "
            "stopped to prevent inappropriate collection activity."
        )

    elif problem_type == ProblemType.SECURITY_ACCESS:
        explanation = (
            "The customer appears to have a security or access problem. "
            "Human assistance is required."
        )

    elif problem_type == ProblemType.AUTHENTICATION:
        explanation = (
            "The customer appears to have an authentication problem. "
            "Sensitive credentials must not be collected by the recovery "
            "agent, so the case is escalated."
        )

    elif problem_type == ProblemType.CHECKOUT_ABANDONMENT:
        explanation = (
            "The customer started or intended to make the payment but did "
            "not complete checkout. Offering a safe retry is appropriate."
        )

    elif problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:
            explanation = (
                "The customer reported a technical payment problem and "
                "explicitly indicated willingness to pay. A retry is "
                "appropriate."
            )
        else:
            explanation = (
                "The customer appears to have a technical payment problem. "
                "Because willingness to pay is not explicit, an alternate "
                "payment option is safer than assuming intent."
            )

    elif problem_type == ProblemType.TIMING:
        explanation = (
            "The customer appears willing to pay later rather than refusing "
            "payment. A scheduled reminder is appropriate."
        )

    else:
        explanation = (
            "The customer message was analyzed using the recovery policy."
        )

    return AIDiagnosis(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=action,
        explanation=explanation,
    )


# ============================================================
# 12. BACKWARD-COMPATIBILITY HELPER
# ============================================================

def _fuzzy_phrase_match(
    text: str,
    phrase: str,
    threshold: float = 0.85,
) -> bool:
    """
    Fuzzy matching is intentionally disabled in the core recovery path.

    Why?

    Payment recovery is a safety-sensitive domain. A fuzzy match can
    incorrectly interpret unrelated customer messages as payment problems.

    The function remains here only for backwards compatibility with older
    tests/imports.
    """

    return False


# ============================================================
# 13. BACKWARD-COMPATIBILITY API
# ============================================================

def diagnose_message(text: str) -> AIDiagnosis:
    """
    Backward-compatible public API.

    Older parts of the project use diagnose_message(),
    while the current diagnosis engine uses analyze_message().

    Both intentionally use the same diagnosis pipeline.
    """
    return analyze_message(text)