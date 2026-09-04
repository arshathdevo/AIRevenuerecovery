import re
from dataclasses import dataclass

from app.models.revenue import (
    AIDiagnosis,
    CustomerIntent,
    ProblemType,
    RecoveryAction,
)


# ============================================================
# 1. PATTERN DATA STRUCTURES
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
    Normalize text for deterministic analysis.

    Example:
        I don't have enough money.
        ->
        i do not have enough money
    """

    if not isinstance(text, str):
        return ""

    text = text.lower().strip()

    # Expand contractions.
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
# 3. SENSITIVE INFORMATION
# ============================================================

SENSITIVE_PATTERNS = [
    r"\bupi\s*pin\b",
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
    Detect potentially sensitive credentials/payment information.
    """

    normalized = normalize_text(text)

    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    # Long numeric values can represent sensitive credentials.
    if re.search(r"\b\d{6,}\b", normalized):
        return True

    return False


def redact_sensitive_information(text: str) -> str:
    """
    Redact sensitive values from a message.
    """

    if not text:
        return ""

    redacted = text

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
    Pattern("forgot to complete the payment", 1.00),
    Pattern("forgot to complete payment", 1.00),
    Pattern("forgot to finish the payment", 1.00),
    Pattern("forgot to finish payment", 1.00),

    Pattern("forgot to make payment", 1.00),
    Pattern("forgot payment", 1.00),
    Pattern("forgot to pay", 1.00),

    Pattern("did not complete payment", 1.00),
    Pattern("did not finish payment", 1.00),

    Pattern("closed the payment page", 1.00),
    Pattern("closed payment page", 1.00),

    Pattern("closed the checkout page", 1.00),
    Pattern("closed checkout page", 1.00),

    Pattern("left payment page", 0.95),
    Pattern("left checkout page", 0.95),

    Pattern("abandoned payment", 1.00),
    Pattern("abandoned checkout", 1.00),

    Pattern("payment not completed", 1.00),
    Pattern("checkout not completed", 1.00),
]


FINANCIAL_PATTERNS = [
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
    Pattern("forgot my upi pin", 1.00),
    Pattern("forgot upi pin", 1.00),

    Pattern("forgot my pin", 1.00),
    Pattern("forgot pin", 1.00),

    Pattern("account is locked", 1.00),
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
    Pattern("do not recognize this payment", 1.00),

    Pattern("unrecognized payment", 1.00),
    Pattern("unknown payment", 0.95),

    Pattern("fraudulent payment", 1.00),
]


# ============================================================
# 5. CUSTOMER INTENT PATTERNS
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
    Determine whether an evidence phrase is actually negated.

    This function is intentionally conservative.

    We DO NOT simply search for the word "not".

    Examples:

        "bank app is not working"
        -> NOT negated
        -> technical evidence remains valid

        "I do not have a bank problem"
        -> "bank problem" IS negated

        "I don't recognize this payment"
        -> dispute evidence is NOT negated
        -> "do not recognize" is itself the dispute phrase
    """

    normalized = normalize_text(text)

    before = normalized[:start].strip()

    if not before:
        return False

    words = before.split()

    if not words:
        return False

    recent = " ".join(words[-10:])

    # --------------------------------------------------------
    # IMPORTANT EXCEPTION
    # --------------------------------------------------------
    #
    # "do not recognize payment" is NOT a negation.
    #
    # It means the customer does not recognize the payment,
    # which is itself a dispute signal.
    #
    if phrase:
        normalized_phrase = normalize_text(phrase)

        if (
            normalized_phrase.startswith("do not recognize")
            or normalized_phrase.startswith("cannot recognize")
            or normalized_phrase.startswith("unable to recognize")
        ):
            return False

    # --------------------------------------------------------
    # "do not have ..."
    # --------------------------------------------------------
    #
    # Handles:
    #
    # "I do not have a bank problem"
    # "I do not have any bank problem"
    # "I do not have any problem with my bank app"
    #
    if re.search(
        r"\b(?:do|does|did)\s+not\s+have"
        r"(?:\s+(?:a|an|any|the))?"
        r"\s*$",
        recent,
    ):
        return True

    # "no bank problem"
    if re.search(r"\bno\s*$", recent):
        return True

    # "without a bank problem"
    if re.search(r"\bwithout(?:\s+(?:a|an|any|the))?\s*$", recent):
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
    Determine whether a pattern has valid evidence.
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

        score = max(
            item.weight
            for item in evidence
        )

        # Multiple independent signals increase confidence.
        if len(evidence) >= 2:
            score = min(score + 0.10, 1.00)

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
) -> tuple[CustomerIntent, float, bool, bool, bool]:
    """
    Returns:

        intent
        confidence
        contradiction
        willingness_to_pay
    """

    positive = _has_positive_willingness(text)
    negative = _has_negative_willingness(text)
    delay = _has_delay_signal(text)

    # --------------------------------------------------------
    # CONTRADICTION
    # --------------------------------------------------------

    if positive and negative:

        return (
       CustomerIntent.UNKNOWN,
       1.00,
     True,
    False,
    delay,
)

    # --------------------------------------------------------
    # DELAY + WILLINGNESS
    # --------------------------------------------------------

    if delay and positive:

        return (
            CustomerIntent.DELAYING_PAYMENT,
            1.00,
            False,
            True,
        )

    # --------------------------------------------------------
    # DELAY ONLY
    # --------------------------------------------------------

    if delay:

        return (
            CustomerIntent.DELAYING_PAYMENT,
            0.90,
            False,
            False,
        )

    # --------------------------------------------------------
    # WILLINGNESS
    # --------------------------------------------------------

    if positive:

        return (
            CustomerIntent.WILLING_TO_PAY,
            1.00,
            False,
            True,
        )

    # --------------------------------------------------------
    # NEGATIVE WILLINGNESS
    # --------------------------------------------------------

    if negative:

        return (
            CustomerIntent.UNKNOWN,
            1.00,
            False,
            False,
        )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return (
        CustomerIntent.UNKNOWN,
        0.00,
        False,
        False,
    )


# ============================================================
# 10. POLICY ENGINE
# ============================================================

def _select_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    problem_confidence: float,
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
    # DISPUTES
    # --------------------------------------------------------

    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if problem_type == ProblemType.SECURITY_ACCESS:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    if problem_type == ProblemType.AUTHENTICATION:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    # --------------------------------------------------------
    # TIMING
    # --------------------------------------------------------

    if problem_type == ProblemType.TIMING:
        return RecoveryAction.SCHEDULE_REMINDER

    # --------------------------------------------------------
    # CHECKOUT
    # --------------------------------------------------------

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:
        return RecoveryAction.OFFER_RETRY

    # --------------------------------------------------------
    # TECHNICAL
    # --------------------------------------------------------

    if problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:
            return RecoveryAction.OFFER_RETRY

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# 11. EXPLANATION GENERATOR
# ============================================================

def _build_explanation(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    action: RecoveryAction,
    sensitive: bool,
    contradiction: bool,
) -> str:

    if sensitive:

        return (
            "The message contains potentially sensitive payment or "
            "authentication information. The issue was diagnosed, but "
            "automated recovery is blocked and human assistance is required."
        )

    if contradiction:

        return (
            "The customer expressed contradictory willingness to pay. "
            "Automated recovery is stopped and human review is required."
        )

    if problem_type == ProblemType.UNKNOWN:

        return (
            "The message does not contain enough reliable evidence to "
            "determine the customer's problem safely."
        )

    if problem_type == ProblemType.FINANCIAL:

        return (
            "The customer appears to be experiencing financial difficulty. "
            "Automated payment pressure is not appropriate, so the case "
            "should be escalated to a human."
        )

    if problem_type == ProblemType.DISPUTE:

        return (
            "The customer appears to dispute the payment. Recovery is "
            "stopped to prevent inappropriate collection activity."
        )

    if problem_type == ProblemType.SECURITY_ACCESS:

        return (
            "The customer appears to have a security or access problem. "
            "Human assistance is required."
        )

    if problem_type == ProblemType.AUTHENTICATION:

        return (
            "The customer appears to have an authentication problem. "
            "Sensitive credentials must not be collected by the recovery "
            "agent, so the case is escalated."
        )

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:

        return (
            "The customer started or intended to make the payment but "
            "did not complete checkout. Offering a safe retry is appropriate."
        )

    if problem_type == ProblemType.TIMING:

        return (
            "The customer appears willing to pay later rather than refusing "
            "payment. A scheduled reminder is appropriate."
        )

    if problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:

            return (
                "The customer reported a technical payment problem and "
                "explicitly indicated willingness to pay. A retry is "
                "appropriate."
            )

        return (
            "The customer appears to have a technical payment problem. "
            "Because willingness to pay is not explicit, an alternate "
            "payment option is safer than assuming intent."
        )

    return (
        "The customer message was analyzed using the recovery policy."
    )


# ============================================================
# 12. MAIN DIAGNOSIS ENGINE
# ============================================================

def analyze_message(text: str) -> AIDiagnosis:
    """
    Main deterministic AI diagnosis pipeline.

        Raw message
             ↓
        Normalize
             ↓
        Sensitive detection
             ↓
        Problem classification
             ↓
        Intent classification
             ↓
        Safety overrides
             ↓
        Recovery policy
             ↓
        Diagnosis result
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    # --------------------------------------------------------
    # EMPTY MESSAGE
    # --------------------------------------------------------

    if not text.strip():

        return AIDiagnosis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.UNKNOWN,
            recommended_action=RecoveryAction.HUMAN_ESCALATION,
            explanation="No customer message was provided.",
            willingness_to_pay=False,
            sensitive=False,
            contradiction=False,
        )

    normalized = normalize_text(text)

    # --------------------------------------------------------
    # SENSITIVE INFORMATION
    # --------------------------------------------------------

    sensitive = contains_sensitive_information(text)

    # IMPORTANT:
    #
    # We DO NOT return here.
    #
    # We continue diagnosis so that:
    #
    # "I forgot my UPI PIN"
    #
    # becomes:
    #
    # AUTHENTICATION + SECURITY_CONCERN + sensitive=True
    #
    # rather than UNKNOWN.
    #
    # The policy engine will still force HUMAN_ESCALATION.

    # --------------------------------------------------------
    # PROBLEM
    # --------------------------------------------------------

    (
        problem_type,
        problem_confidence,
        _problem_evidence,
    ) = _classify_problem(normalized)

    # --------------------------------------------------------
    # INTENT
    # --------------------------------------------------------

    (
        customer_intent,
        _intent_confidence,
        contradiction,
        willingness_to_pay,
    ) = _classify_intent(normalized)

    # --------------------------------------------------------
    # PROBLEM-SPECIFIC INTENT OVERRIDES
    # --------------------------------------------------------

    # Financial difficulty overrides normal willingness.
    if problem_type == ProblemType.FINANCIAL:

        customer_intent = CustomerIntent.FINANCIAL_DIFFICULTY

    # Payment disputes have their own intent.
    elif problem_type == ProblemType.DISPUTE:

        customer_intent = CustomerIntent.DISPUTE

    # SECURITY_ACCESS specifically indicates a security concern.
    elif problem_type == ProblemType.SECURITY_ACCESS:

        customer_intent = CustomerIntent.SECURITY_CONCERN

    # Authentication is slightly different.
    #
    # "I forgot my UPI PIN."
    # -> security concern
    #
    # "My account is locked and I cannot log in."
    # -> UNKNOWN according to our current test contract.
    #
    # Therefore only explicit credential/security situations force
    # SECURITY_CONCERN here.
    elif problem_type == ProblemType.AUTHENTICATION:

        if sensitive:
            customer_intent = CustomerIntent.SECURITY_CONCERN

    # Contradiction always wins.
    if contradiction:

        customer_intent = CustomerIntent.UNKNOWN
        willingness_to_pay = False

    # --------------------------------------------------------
    # POLICY
    # --------------------------------------------------------

    action = _select_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        problem_confidence=problem_confidence,
        contradiction=contradiction,
        sensitive=sensitive,
    )

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    explanation = _build_explanation(
        problem_type=problem_type,
        customer_intent=customer_intent,
        action=action,
        sensitive=sensitive,
        contradiction=contradiction,
    )

    # --------------------------------------------------------
    # FINAL STRUCTURED RESULT
    # --------------------------------------------------------

    return AIDiagnosis(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=action,
        explanation=explanation,

        # Diagnostic metadata.
        willingness_to_pay=willingness_to_pay,
        sensitive=sensitive,
        contradiction=contradiction,
    )


# ============================================================
# 13. PUBLIC API ALIASES
# ============================================================

def diagnose_message(text: str) -> AIDiagnosis:
    """
    Public diagnosis API.

    Kept as a wrapper around analyze_message() so both names
    remain compatible with existing code and tests.
    """

    return analyze_message(text)


# ============================================================
# 14. LEGACY FUZZY MATCH FUNCTION
# ============================================================

def _fuzzy_phrase_match(
    text: str,
    phrase: str,
    threshold: float = 0.85,
) -> bool:
    """
    Fuzzy matching intentionally disabled in the core MVP.

    Payment recovery is safety-sensitive. False-positive fuzzy
    matches can trigger inappropriate recovery actions.

    Kept only for compatibility with older imports/tests.
    """

    return False