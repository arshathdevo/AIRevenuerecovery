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
# TEXT NORMALIZATION
# ============================================================

CONTRACTIONS = {
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "couldn't": "could not",
    "won't": "will not",
    "wouldn't": "would not",
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
}


def normalize_text(message: str) -> str:
    if not isinstance(message, str):
        return ""

    text = message.lower().strip()

    for contraction, expansion in CONTRACTIONS.items():
        text = re.sub(
            rf"\b{re.escape(contraction)}\b",
            expansion,
            text,
        )

    text = text.replace("-", " ")
    text = text.replace("_", " ")

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text: str) -> list[str]:
    return text.split() if text else []


# ============================================================
# SAFETY
# ============================================================

SENSITIVE_PATTERNS = [
    r"\bupi\s*pin\b",
    r"\bpin\s*(?:number|code)?\b",
    r"\botp\b",
    r"\bone\s*time\s*password\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bcard\s*(?:number|no)\b",
    r"\bcredit\s*card\s*(?:number|no)\b",
    r"\bdebit\s*card\s*(?:number|no)\b",
    r"\bpassword\b",
]


CREDENTIAL_VALUE_PATTERNS = [
    r"(\b(?:otp|pin|cvv|cvc)\b\s*(?:is|:|=)?\s*)\d{3,8}\b",

    r"(\b(?:card\s*(?:number|no)|account\s*(?:number|no))"
    r"\b\s*(?:is|:|=)?\s*)\d[\d\s-]{7,22}\b",
]


def contains_sensitive_information(text: str) -> bool:
    return any(
        re.search(pattern, text)
        for pattern in SENSITIVE_PATTERNS
    )


def redact_sensitive_information(message: str) -> str:
    """
    Safe representation for audit/logging.

    Credential values must never appear in our diagnosis output.
    """

    if not isinstance(message, str):
        return ""

    result = message

    for pattern in CREDENTIAL_VALUE_PATTERNS:
        result = re.sub(
            pattern,
            lambda match: f"{match.group(1)}[REDACTED]",
            result,
            flags=re.IGNORECASE,
        )

    return result


# ============================================================
# DOMAIN KNOWLEDGE
# ============================================================

@dataclass(frozen=True)
class Pattern:
    phrase: str
    weight: float
    aliases: tuple[str, ...] = ()


@dataclass
class Evidence:
    category: str
    phrase: str
    weight: float
    source: str
    negated: bool = False
    fuzzy: bool = False


@dataclass
class DiagnosisAnalysis:

    problem_type: ProblemType
    customer_intent: CustomerIntent
    recommended_action: RecoveryAction

    problem_scores: dict = field(default_factory=dict)
    intent_scores: dict = field(default_factory=dict)

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
# PROBLEM KNOWLEDGE
# ============================================================

PROBLEM_PATTERNS = {

    ProblemType.TECHNICAL: [

        Pattern("bank server", 4.0),
        Pattern("bank servers", 4.0),

        Pattern(
            "bank app",
            3.5,
            ("bank application", "banking app"),
        ),

        Pattern("server problem", 4.0),
        Pattern("server issue", 4.0),
        Pattern("server error", 4.0),
        Pattern("server down", 4.5),

        Pattern("payment app", 3.0),

        Pattern("app not working", 4.0),
        Pattern("application not working", 4.0),

        Pattern("payment failed", 3.0),
        Pattern("transaction failed", 3.5),

        Pattern("payment error", 3.5),
        Pattern("transaction error", 3.5),

        Pattern("technical problem", 4.0),
        Pattern("technical issue", 4.0),

        Pattern("internet problem", 3.5),
        Pattern("internet issue", 3.5),

        Pattern("network problem", 3.5),
        Pattern("network issue", 3.5),

        Pattern("poor network", 3.5),
        Pattern("bad network", 3.5),

        Pattern("connection problem", 3.5),
        Pattern("connection issue", 3.5),

        Pattern("website not working", 4.0),

        Pattern("system problem", 3.5),
        Pattern("system issue", 3.5),

        Pattern("timed out", 3.5),
        Pattern("timeout", 3.5),

        Pattern("declined", 2.5),
    ],

    ProblemType.CHECKOUT_ABANDONMENT: [

        Pattern("forgot to pay", 4.0),
        Pattern("forgot payment", 4.0),

        Pattern("did not complete", 4.0),
        Pattern("did not finish", 4.0),

        Pattern(
            "did not complete the payment",
            4.5,
        ),

        Pattern(
            "did not finish the payment",
            4.5,
        ),

        Pattern("left the payment", 3.5),
        Pattern("closed the page", 4.0),
        Pattern("closed the app", 3.5),

        Pattern("payment page", 2.0),
        Pattern("checkout", 3.0),

        Pattern("abandoned", 4.0),

        Pattern("forgot", 1.5),

        Pattern("will complete", 3.0),
        Pattern("complete the payment", 4.0),
        Pattern("finish the payment", 4.0),

        Pattern("got distracted", 3.0),
        Pattern("was distracted", 2.5),
    ],

    ProblemType.FINANCIAL: [

        Pattern("cannot afford", 5.0),
        Pattern("no money", 5.0),

        Pattern(
            "do not have enough money",
            5.0,
        ),

        Pattern("not enough money", 5.0),
        Pattern("not enough funds", 5.0),

        Pattern("insufficient funds", 5.0),

        Pattern("short of money", 4.5),
        Pattern("short on money", 4.5),
        Pattern("short on cash", 4.5),

        Pattern("financial problem", 5.0),
        Pattern("financial issue", 5.0),
        Pattern("financial difficulty", 5.0),

        Pattern("money problem", 4.5),
        Pattern("cash problem", 4.5),

        Pattern("cannot pay", 5.0),
        Pattern("unable to pay", 5.0),

        Pattern("struggling financially", 5.0),

        Pattern(
            "having financial problems",
            5.0,
        ),

        Pattern("salary has not come", 4.5),
        Pattern("salary not received", 4.5),
        Pattern("waiting for salary", 4.0),

        Pattern("pay after salary", 4.5),
    ],

    ProblemType.TIMING: [

        Pattern("pay later", 4.0),
        Pattern("payment later", 4.0),

        Pattern("pay tomorrow", 4.5),
        Pattern("pay tonight", 4.0),
        Pattern("pay next week", 4.5),

        Pattern("not now", 3.0),

        Pattern("busy right now", 3.5),
        Pattern("busy today", 3.5),

        Pattern("will pay", 2.5),

        Pattern("later today", 4.0),

        Pattern("give me some time", 4.0),
        Pattern("need some time", 4.0),

        Pattern("after some time", 3.0),

        Pattern("in a few minutes", 3.0),
        Pattern("in an hour", 3.0),

        Pattern("after work", 3.0),
        Pattern("after class", 3.0),

        Pattern("tomorrow", 2.5),
        Pattern("next week", 2.5),
    ],

    ProblemType.AUTHENTICATION: [

        Pattern("forgot pin", 5.0),
        Pattern("forgot my pin", 5.0),

        Pattern("upi pin", 5.0),

        Pattern("authentication problem", 5.0),
        Pattern("authentication issue", 5.0),

        Pattern("login problem", 4.5),
        Pattern("login issue", 4.5),

        Pattern("cannot login", 4.5),
        Pattern("cannot log in", 4.5),

        Pattern("unable to login", 4.5),
        Pattern("unable to log in", 4.5),

        Pattern("account locked", 5.0),
        Pattern("account blocked", 5.0),

        Pattern("otp problem", 5.0),
        Pattern("otp issue", 5.0),

        Pattern("verification problem", 4.0),
        Pattern("verification failed", 4.5),
    ],

    ProblemType.SECURITY_ACCESS: [

        Pattern("lost my phone", 6.0),
        Pattern("lost phone", 6.0),

        Pattern("phone was stolen", 6.0),
        Pattern("phone stolen", 6.0),

        Pattern("phone was robbed", 6.0),
        Pattern("phone robbed", 6.0),

        Pattern("cannot access my phone", 5.0),
        Pattern(
            "do not have access to my phone",
            5.0,
        ),

        Pattern("lost access", 4.5),

        Pattern("someone stole", 6.0),
        Pattern("someone has my phone", 6.0),
    ],

    ProblemType.DISPUTE: [

        Pattern("wrong vendor", 6.0),
        Pattern("wrong merchant", 6.0),
        Pattern("wrong payment", 6.0),

        Pattern("paid someone else", 6.0),
        Pattern("paid the wrong", 6.0),

        Pattern("not my payment", 6.0),

        Pattern(
            "do not recognize this payment",
            6.0,
        ),

        Pattern(
            "do not recognize the payment",
            6.0,
        ),

        Pattern("dispute", 6.0),
        Pattern("refund", 4.0),

        Pattern("charged twice", 6.0),
        Pattern("charged two times", 6.0),

        Pattern("duplicate payment", 6.0),

        Pattern("unauthorized payment", 6.0),
        Pattern("unauthorised payment", 6.0),
    ],
}


# ============================================================
# INTENT KNOWLEDGE
# ============================================================

INTENT_PATTERNS = {

    CustomerIntent.WILLING_TO_PAY: [

        Pattern("i will pay", 5.0),
        Pattern("will pay", 4.0),

        Pattern("i want to pay", 5.0),
        Pattern("want to pay", 4.0),

        Pattern("i am ready to pay", 5.0),
        Pattern("ready to pay", 5.0),

        Pattern("i can pay", 4.5),
        Pattern("can pay", 3.5),

        Pattern("i will try again", 5.0),
        Pattern("will try again", 4.5),

        Pattern("try again", 3.5),

        Pattern("i will retry", 5.0),
        Pattern("retry", 3.0),

        Pattern("let me try", 4.0),

        Pattern("i want to complete", 4.0),
        Pattern("i can complete", 4.0),

        Pattern("i can pay now", 5.0),
        Pattern("i am able to pay", 4.5),

        Pattern("happy to pay", 4.5),
    ],

    CustomerIntent.DELAYING_PAYMENT: [

        Pattern("pay later", 5.0),
        Pattern("pay tomorrow", 5.0),
        Pattern("pay next week", 5.0),

        Pattern("not now", 4.0),

        Pattern("later today", 4.5),

        Pattern("give me some time", 4.5),
        Pattern("need some time", 4.5),

        Pattern("i am busy", 3.5),
        Pattern("busy right now", 4.0),
        Pattern("busy today", 4.0),

        Pattern("in a few minutes", 4.0),

        Pattern("after work", 3.5),
        Pattern("after class", 3.5),
    ],

    CustomerIntent.FINANCIAL_DIFFICULTY: [

        Pattern("no money", 6.0),

        Pattern(
            "do not have enough money",
            6.0,
        ),

        Pattern("not enough money", 6.0),

        Pattern("cannot afford", 6.0),

        Pattern("short on cash", 6.0),

        Pattern("financial problem", 6.0),
        Pattern("financial difficulty", 6.0),

        Pattern("cannot pay", 6.0),
        Pattern("unable to pay", 6.0),

        Pattern("insufficient funds", 6.0),

        Pattern("waiting for salary", 5.0),
        Pattern("pay after salary", 5.0),
    ],

    CustomerIntent.DISPUTE: [

        Pattern("wrong vendor", 6.0),
        Pattern("wrong merchant", 6.0),
        Pattern("wrong payment", 6.0),

        Pattern("not my payment", 6.0),
        Pattern("do not recognize", 6.0),

        Pattern("dispute", 6.0),
        Pattern("refund", 5.0),

        Pattern("charged twice", 6.0),

        Pattern("unauthorized", 6.0),
        Pattern("unauthorised", 6.0),
    ],

    CustomerIntent.SECURITY_CONCERN: [

        Pattern("phone stolen", 6.0),
        Pattern("phone was stolen", 6.0),

        Pattern("lost phone", 6.0),
        Pattern("phone robbed", 6.0),

        Pattern("someone stole", 6.0),

        Pattern("security problem", 6.0),
        Pattern("security issue", 6.0),

        Pattern("someone accessed", 6.0),

        Pattern("unauthorized", 6.0),
        Pattern("unauthorised", 6.0),
    ],
}


# ============================================================
# NEGATION
# ============================================================

NEGATION_WORDS = {
    "not",
    "no",
    "never",
    "cannot",
    "without",
}


def _phrase_tokens(phrase: str) -> list[str]:
    return phrase.split()


def _find_phrase_occurrences(
    tokens: list[str],
    phrase: str,
) -> list[int]:

    target = _phrase_tokens(phrase)

    if not target:
        return []

    if len(target) > len(tokens):
        return []

    positions = []

    width = len(target)

    for index in range(
        len(tokens) - width + 1
    ):

        if tokens[index:index + width] == target:
            positions.append(index)

    return positions


def _is_negated_at(
    tokens: list[str],
    start: int,
) -> bool:

    window_start = max(0, start - 5)

    window = tokens[
        window_start:start
    ]

    joined = " ".join(window)

    direct_negations = (
        "do not",
        "does not",
        "did not",
        "will not",
        "would not",
        "could not",
        "cannot",
        "never",
    )

    if any(
        marker in joined
        for marker in direct_negations
    ):
        return True

    return (
        "not" in window
        or "no" in window
    )


# ============================================================
# FUZZY MATCHING
# ============================================================

def _fuzzy_phrase_match(
    text: str,
    phrase: str,
) -> bool:

    phrase_words = phrase.split()

    # Single words are too dangerous to fuzzy-match.
    if len(phrase_words) < 2:
        return False

    words = text.split()

    window_size = len(phrase_words)

    if len(words) < window_size:
        return False

    target = " ".join(phrase_words)

    for index in range(
        len(words) - window_size + 1
    ):

        candidate = " ".join(
            words[index:index + window_size]
        )

        similarity = SequenceMatcher(
            None,
            candidate,
            target,
        ).ratio()

        if similarity >= 0.91:
            return True

    return False


# ============================================================
# EVIDENCE SCORING
# ============================================================

def _score_group(
    text: str,
    patterns: Iterable[Pattern],
    category: str,
):

    tokens = tokenize(text)

    score = 0.0

    evidence = []

    for pattern in patterns:

        occurrences = _find_phrase_occurrences(
            tokens,
            pattern.phrase,
        )

        if occurrences:

            for start in occurrences:

                negated = _is_negated_at(
                    tokens,
                    start,
                )

                evidence.append(
                    Evidence(
                        category=category,
                        phrase=pattern.phrase,
                        weight=pattern.weight,
                        source="exact",
                        negated=negated,
                    )
                )

                if not negated:
                    score += pattern.weight

            continue

        # ----------------------------------------------------
        # aliases
        # ----------------------------------------------------

        alias_found = False

        for alias in pattern.aliases:

            alias_occurrences = (
                _find_phrase_occurrences(
                    tokens,
                    alias,
                )
            )

            if alias_occurrences:

                alias_found = True

                for start in alias_occurrences:

                    negated = _is_negated_at(
                        tokens,
                        start,
                    )

                    evidence.append(
                        Evidence(
                            category=category,
                            phrase=alias,
                            weight=pattern.weight * 0.95,
                            source="alias",
                            negated=negated,
                        )
                    )

                    if not negated:
                        score += (
                            pattern.weight * 0.95
                        )

                break

        if alias_found:
            continue

        # ----------------------------------------------------
        # conservative fuzzy matching
        # ----------------------------------------------------

        if _fuzzy_phrase_match(
            text,
            pattern.phrase,
        ):

            evidence.append(
                Evidence(
                    category=category,
                    phrase=pattern.phrase,
                    weight=pattern.weight * 0.60,
                    source="fuzzy",
                    fuzzy=True,
                )
            )

            score += pattern.weight * 0.60

    return score, evidence


def score_patterns(
    text: str,
    pattern_groups: dict,
):

    scores = {}
    evidence = {}

    for category, patterns in pattern_groups.items():

        score, matches = _score_group(
            text,
            patterns,
            str(category),
        )

        scores[category] = round(
            score,
            3,
        )

        evidence[category] = matches

    return scores, evidence


# ============================================================
# RANKING
# ============================================================

def _ranked(scores: dict):

    return sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )


def get_best_category(scores: dict):

    ranked = _ranked(scores)

    if not ranked:
        return None, 0.0

    if ranked[0][1] <= 0:
        return None, 0.0

    return ranked[0]


# ============================================================
# CONFIDENCE
# ============================================================

def _confidence(
    scores: dict,
    evidence_count: int,
) -> float:

    positive = sorted(
        [
            score
            for score in scores.values()
            if score > 0
        ],
        reverse=True,
    )

    if not positive:
        return 0.0

    best = positive[0]

    second = (
        positive[1]
        if len(positive) > 1
        else 0.0
    )

    strength = min(
        best / 10.0,
        1.0,
    )

    margin = min(
        max(best - second, 0.0) / 8.0,
        1.0,
    )

    evidence_bonus = min(
        evidence_count * 0.04,
        0.16,
    )

    confidence = (
        0.35
        + 0.35 * strength
        + 0.22 * margin
        + evidence_bonus
    )

    return round(
        min(confidence, 0.99),
        2,
    )


# ============================================================
# SPECIAL SIGNALS
# ============================================================

def _contains_any(
    text: str,
    phrases: Iterable[str],
) -> bool:

    tokens = tokenize(text)

    return any(
        _find_phrase_occurrences(
            tokens,
            phrase,
        )
        for phrase in phrases
    )


def _detect_willingness(text: str) -> bool:

    positive = (

        "i will pay",
        "will pay",

        "i want to pay",
        "want to pay",

        "ready to pay",

        "i can pay",
        "can pay",

        "try again",
        "retry",

        "will complete",

        "i want to complete",

        "happy to pay",
    )

    negative = (

        "do not want to pay",

        "do not wish to pay",

        "will not pay",

        "cannot pay",

        "unable to pay",

        "i cannot afford",
    )

    if _contains_any(
        text,
        negative,
    ):
        return False

    return _contains_any(
        text,
        positive,
    )


def _detect_delay(text: str) -> bool:

    return _contains_any(
        text,
        (
            "pay later",
            "pay tomorrow",
            "pay next week",
            "not now",
            "later today",
            "give me some time",
            "need some time",
            "busy right now",
            "busy today",
            "in a few minutes",
            "after work",
            "after class",
            "tomorrow",
            "next week",
        ),
    )


def _detect_contradiction(
    text: str,
) -> bool:

    positive = _detect_willingness(text)

    negative = _contains_any(
        text,
        (
            "do not want to pay",
            "do not wish to pay",
            "will not pay",
            "cannot pay",
            "unable to pay",
        ),
    )

    return positive and negative


# ============================================================
# RECOVERY POLICY
# ============================================================

def choose_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    sensitive: bool,
    confidence: float = 1.0,
    contradiction: bool = False,
) -> RecoveryAction:

    # Safety first.
    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    # Contradictory language should not trigger automation.
    if contradiction:
        return RecoveryAction.HUMAN_ESCALATION

    # Low confidence should not trigger aggressive recovery.
    if confidence < 0.45:
        return RecoveryAction.HUMAN_ESCALATION

    # Security.
    if problem_type == ProblemType.SECURITY_ACCESS:
        return RecoveryAction.HUMAN_ESCALATION

    # Disputes.
    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if customer_intent == CustomerIntent.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    # Security intent.
    if customer_intent == CustomerIntent.SECURITY_CONCERN:
        return RecoveryAction.HUMAN_ESCALATION

    # Financial hardship.
    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.FINANCIAL_DIFFICULTY:
        return RecoveryAction.HUMAN_ESCALATION

    # Authentication.
    if problem_type == ProblemType.AUTHENTICATION:
        return RecoveryAction.HUMAN_ESCALATION

    # Technical.
    if problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:
            return RecoveryAction.OFFER_RETRY

        if customer_intent == CustomerIntent.DELAYING_PAYMENT:
            return RecoveryAction.SCHEDULE_REMINDER

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    # Checkout abandonment.
    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:

        if customer_intent == CustomerIntent.DELAYING_PAYMENT:
            return RecoveryAction.SCHEDULE_REMINDER

        return RecoveryAction.OFFER_RETRY

    # Timing.
    if problem_type == ProblemType.TIMING:
        return RecoveryAction.SCHEDULE_REMINDER

    # Generic intent.
    if customer_intent == CustomerIntent.WILLING_TO_PAY:
        return RecoveryAction.OFFER_RETRY

    if customer_intent == CustomerIntent.DELAYING_PAYMENT:
        return RecoveryAction.SCHEDULE_REMINDER

    # Safe fallback.
    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# EXPLANATION
# ============================================================

def _pretty(value) -> str:

    raw = getattr(
        value,
        "value",
        str(value),
    )

    return raw.lower().replace(
        "_",
        " ",
    )


def build_explanation(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    action: RecoveryAction,
    confidence: float,
    *,
    willingness_to_pay: bool = False,
    delay_signal: bool = False,
    contradiction: bool = False,
    sensitive: bool = False,
) -> str:

    parts = [

        f"Detected {_pretty(problem_type)}.",

        (
            f"Primary customer intent: "
            f"{_pretty(customer_intent)}."
        ),
    ]

    if (
        willingness_to_pay
        and delay_signal
    ):

        parts.append(
            "The customer appears willing to pay "
            "but is requesting a delay."
        )

    elif willingness_to_pay:

        parts.append(
            "The customer appears willing to pay."
        )

    elif delay_signal:

        parts.append(
            "The customer appears to be delaying payment."
        )

    if contradiction:

        parts.append(
            "Conflicting payment-intent signals "
            "were detected."
        )

    parts.append(
        f"Recommended action: {_pretty(action)}."
    )

    parts.append(
        f"Diagnosis confidence: "
        f"{int(confidence * 100)}%."
    )

    if sensitive:

        parts.append(
            "Sensitive payment credentials must "
            "never be requested, stored, or repeated "
            "by the recovery agent."
        )

    return " ".join(parts)


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_message(
    message: str,
) -> DiagnosisAnalysis:

    text = normalize_text(message)

    # Empty message.
    if not text:

        return DiagnosisAnalysis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.UNKNOWN,
            recommended_action=(
                RecoveryAction.HUMAN_ESCALATION
            ),
        )

    sensitive = contains_sensitive_information(
        text
    )

    # --------------------------------------------------------
    # Problem scoring
    # --------------------------------------------------------

    problem_scores, problem_evidence_map = (
        score_patterns(
            text,
            PROBLEM_PATTERNS,
        )
    )

    # --------------------------------------------------------
    # Intent scoring
    # --------------------------------------------------------

    intent_scores, intent_evidence_map = (
        score_patterns(
            text,
            INTENT_PATTERNS,
        )
    )

    problem_type, _ = get_best_category(
        problem_scores
    )

    customer_intent, _ = get_best_category(
        intent_scores
    )

    if problem_type is None:
        problem_type = ProblemType.UNKNOWN

    if customer_intent is None:
        customer_intent = CustomerIntent.UNKNOWN

    # --------------------------------------------------------
    # Independent semantic signals
    # --------------------------------------------------------

    willingness = _detect_willingness(
        text
    )

    delay = _detect_delay(
        text
    )

    contradiction = _detect_contradiction(
        text
    )

    # --------------------------------------------------------
    # Problem-specific refinement
    # --------------------------------------------------------

    if problem_type == ProblemType.FINANCIAL:

        customer_intent = (
            CustomerIntent.FINANCIAL_DIFFICULTY
        )

    elif problem_type == ProblemType.DISPUTE:

        customer_intent = (
            CustomerIntent.DISPUTE
        )

    elif problem_type == ProblemType.SECURITY_ACCESS:

        customer_intent = (
            CustomerIntent.SECURITY_CONCERN
        )

    elif (
        problem_type == ProblemType.TECHNICAL
        and willingness
        and customer_intent
        == CustomerIntent.UNKNOWN
    ):

        customer_intent = (
            CustomerIntent.WILLING_TO_PAY
        )

    elif (
        delay
        and willingness
        and customer_intent
        == CustomerIntent.UNKNOWN
    ):

        customer_intent = (
            CustomerIntent.DELAYING_PAYMENT
        )

    # --------------------------------------------------------
    # Safety override
    # --------------------------------------------------------

    if sensitive:

        problem_type = (
            ProblemType.AUTHENTICATION
        )

        customer_intent = (
            CustomerIntent.SECURITY_CONCERN
        )

    # --------------------------------------------------------
    # Evidence
    # --------------------------------------------------------

    problem_evidence = [
        evidence
        for evidence_list
        in problem_evidence_map.values()
        for evidence
        in evidence_list
        if not evidence.negated
    ]

    intent_evidence = [
        evidence
        for evidence_list
        in intent_evidence_map.values()
        for evidence
        in evidence_list
        if not evidence.negated
    ]

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    problem_confidence = _confidence(
        problem_scores,
        len(problem_evidence),
    )

    intent_confidence = _confidence(
        intent_scores,
        len(intent_evidence),
    )

    if customer_intent == CustomerIntent.UNKNOWN:
        intent_confidence = 0.0

    overall_confidence = round(
        (
            problem_confidence
            + intent_confidence
        ) / 2,
        2,
    )

    if problem_type == ProblemType.UNKNOWN:
        overall_confidence = 0.0

    if sensitive:
        overall_confidence = 0.99

    # --------------------------------------------------------
    # Policy
    # --------------------------------------------------------

    action = choose_recovery_action(
        problem_type=problem_type,
        customer_intent=customer_intent,
        sensitive=sensitive,
        confidence=overall_confidence,
        contradiction=contradiction,
    )

    return DiagnosisAnalysis(

        problem_type=problem_type,

        customer_intent=customer_intent,

        recommended_action=action,

        problem_scores=problem_scores,

        intent_scores=intent_scores,

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
    message: str,
) -> AIDiagnosis:

    analysis = analyze_message(
        message
    )

    explanation = build_explanation(
        analysis.problem_type,
        analysis.customer_intent,
        analysis.recommended_action,
        analysis.overall_confidence,
        willingness_to_pay=analysis.willingness_to_pay,
        delay_signal=analysis.delay_signal,
        contradiction=analysis.contradiction,
        sensitive=analysis.sensitive,
    )

    return AIDiagnosis(
        problem_type=analysis.problem_type,

        customer_intent=analysis.customer_intent,

        recommended_action=(
            analysis.recommended_action
        ),

        explanation=explanation,
    )


def detect_problem(
    message: str,
) -> ProblemType:

    return diagnose_message(
        message
    ).problem_type