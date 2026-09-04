import re
from dataclasses import dataclass

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
    "you'll": "you will",
    "you're": "you are",
    "they're": "they are",
}


def normalize_text(message: str) -> str:
    """
    Normalize natural language before classification.
    """

    if not isinstance(message, str):
        return ""

    text = message.lower().strip()

    for contraction, expanded in CONTRACTIONS.items():
        text = text.replace(contraction, expanded)

    # Keep letters, numbers and spaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# 2. SECURITY / SENSITIVE INFORMATION DETECTION
# ============================================================

SENSITIVE_PATTERNS = [
    r"\bupi pin\b",
    r"\bpin number\b",
    r"\bmy pin\b",
    r"\botp\b",
    r"\bone time password\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bcard number\b",
    r"\bcredit card number\b",
    r"\bdebit card number\b",
    r"\bpassword\b",
]


def contains_sensitive_information_request(text: str) -> bool:
    """
    Detect messages involving sensitive payment credentials.
    The recovery agent must never request or process these.
    """

    return any(
        re.search(pattern, text)
        for pattern in SENSITIVE_PATTERNS
    )


# ============================================================
# 3. DOMAIN KNOWLEDGE
# ============================================================

@dataclass(frozen=True)
class Pattern:
    phrase: str
    weight: float


PROBLEM_PATTERNS = {
    ProblemType.TECHNICAL: [
        Pattern("bank server", 3.0),
        Pattern("bank app", 3.0),
        Pattern("bank application", 3.0),
        Pattern("server problem", 3.0),
        Pattern("server issue", 3.0),
        Pattern("server down", 3.0),
        Pattern("payment app", 2.5),
        Pattern("app not working", 3.0),
        Pattern("application not working", 3.0),
        Pattern("payment failed", 2.0),
        Pattern("transaction failed", 2.5),
        Pattern("technical problem", 3.0),
        Pattern("technical issue", 3.0),
        Pattern("internet problem", 2.5),
        Pattern("internet issue", 2.5),
        Pattern("network problem", 2.5),
        Pattern("network issue", 2.5),
        Pattern("connection problem", 2.5),
        Pattern("connection issue", 2.5),
        Pattern("website not working", 3.0),
        Pattern("system problem", 2.5),
        Pattern("system issue", 2.5),
    ],

    ProblemType.CHECKOUT_ABANDONMENT: [
        Pattern("forgot to pay", 3.0),
        Pattern("forgot payment", 3.0),
        Pattern("did not complete", 3.0),
        Pattern("did not finish", 3.0),
        Pattern("left the payment", 3.0),
        Pattern("closed the page", 3.0),
        Pattern("closed the app", 2.5),
        Pattern("payment page", 2.0),
        Pattern("checkout", 2.5),
        Pattern("forgot", 1.5),
        Pattern("will complete", 2.5),
        Pattern("complete the payment", 3.0),
    ],

    ProblemType.FINANCIAL: [
        Pattern("cannot afford", 4.0),
        Pattern("no money", 3.5),
        Pattern("do not have money", 3.5),
        Pattern("not enough money", 3.5),
        Pattern("not enough funds", 3.5),
        Pattern("short of money", 3.5),
        Pattern("short on money", 3.5),
        Pattern("short on cash", 3.5),
        Pattern("financial problem", 4.0),
        Pattern("financial issue", 4.0),
        Pattern("financial difficulty", 4.0),
        Pattern("money problem", 3.5),
        Pattern("cash problem", 3.5),
        Pattern("cannot pay", 3.5),
        Pattern("unable to pay", 3.5),
        Pattern("struggling financially", 4.0),
        Pattern("having financial problems", 4.0),
    ],

    ProblemType.TIMING: [
        Pattern("pay later", 3.5),
        Pattern("payment later", 3.5),
        Pattern("pay tomorrow", 3.5),
        Pattern("pay next week", 3.5),
        Pattern("not now", 2.5),
        Pattern("busy right now", 2.5),
        Pattern("busy", 1.5),
        Pattern("will pay", 2.5),
        Pattern("i will pay", 3.0),
        Pattern("later today", 3.0),
        Pattern("give me some time", 3.0),
        Pattern("need some time", 3.0),
    ],

    ProblemType.AUTHENTICATION: [
        Pattern("forgot pin", 4.0),
        Pattern("forgot my pin", 4.0),
        Pattern("upi pin", 4.0),
        Pattern("authentication problem", 4.0),
        Pattern("authentication issue", 4.0),
        Pattern("login problem", 3.5),
        Pattern("login issue", 3.5),
        Pattern("cannot login", 3.5),
        Pattern("cannot log in", 3.5),
        Pattern("unable to login", 3.5),
        Pattern("unable to log in", 3.5),
    ],

    ProblemType.SECURITY_ACCESS: [
        Pattern("lost my phone", 5.0),
        Pattern("lost phone", 5.0),
        Pattern("phone was stolen", 5.0),
        Pattern("phone stolen", 5.0),
        Pattern("phone was robbed", 5.0),
        Pattern("phone robbed", 5.0),
        Pattern("cannot access my phone", 4.0),
        Pattern("do not have access to my phone", 4.0),
        Pattern("lost access", 3.5),
    ],

    ProblemType.DISPUTE: [
        Pattern("wrong vendor", 5.0),
        Pattern("wrong merchant", 5.0),
        Pattern("wrong payment", 5.0),
        Pattern("paid someone else", 5.0),
        Pattern("paid the wrong", 5.0),
        Pattern("not my payment", 5.0),
        Pattern("do not recognize this payment", 5.0),
        Pattern("dispute", 5.0),
        Pattern("refund", 3.5),
        Pattern("charged twice", 5.0),
        Pattern("charged two times", 5.0),
    ],
}


# ============================================================
# 4. CUSTOMER INTENT KNOWLEDGE
# ============================================================

INTENT_PATTERNS = {
    CustomerIntent.WILLING_TO_PAY: [
        Pattern("i will pay", 4.0),
        Pattern("will pay", 3.5),
        Pattern("i want to pay", 4.0),
        Pattern("want to pay", 3.5),
        Pattern("i am ready to pay", 4.0),
        Pattern("ready to pay", 4.0),
        Pattern("i can pay", 3.5),
        Pattern("can pay", 3.0),
        Pattern("i will try again", 4.0),
        Pattern("try again", 3.0),
        Pattern("i will retry", 4.0),
        Pattern("retry", 2.5),
        Pattern("let me try", 3.0),
        Pattern("i want to complete", 3.0),
        Pattern("i can complete", 3.0),
    ],

    CustomerIntent.DELAYING_PAYMENT: [
        Pattern("pay later", 4.0),
        Pattern("pay tomorrow", 4.0),
        Pattern("pay next week", 4.0),
        Pattern("not now", 3.0),
        Pattern("later today", 3.5),
        Pattern("give me some time", 3.5),
        Pattern("need some time", 3.5),
        Pattern("i am busy", 2.5),
        Pattern("busy right now", 3.0),
    ],

    CustomerIntent.FINANCIAL_DIFFICULTY: [
        Pattern("no money", 5.0),
        Pattern("do not have money", 5.0),
        Pattern("cannot afford", 5.0),
        Pattern("not enough money", 5.0),
        Pattern("short on cash", 5.0),
        Pattern("financial problem", 5.0),
        Pattern("financial difficulty", 5.0),
        Pattern("cannot pay", 5.0),
        Pattern("unable to pay", 5.0),
    ],

    CustomerIntent.DISPUTE: [
        Pattern("wrong vendor", 5.0),
        Pattern("wrong merchant", 5.0),
        Pattern("wrong payment", 5.0),
        Pattern("not my payment", 5.0),
        Pattern("do not recognize", 5.0),
        Pattern("dispute", 5.0),
        Pattern("refund", 4.0),
    ],

    CustomerIntent.SECURITY_CONCERN: [
        Pattern("phone stolen", 5.0),
        Pattern("phone was stolen", 5.0),
        Pattern("lost phone", 5.0),
        Pattern("phone robbed", 5.0),
        Pattern("someone stole", 5.0),
        Pattern("security problem", 5.0),
        Pattern("security issue", 5.0),
        Pattern("someone accessed", 5.0),
        Pattern("unauthorized", 5.0),
    ],
}


# ============================================================
# 5. NEGATION HANDLING
# ============================================================

NEGATION_WORDS = {
    "not",
    "no",
    "never",
    "cannot",
    "without",
    "do not",
    "does not",
    "did not",
    "will not",
}


def is_negated(text: str, phrase: str) -> bool:
    """
    Basic local negation detection.

    Example:
        "I am not having a bank problem"

    should not strongly classify as TECHNICAL.
    """

    index = text.find(phrase)

    if index == -1:
        return False

    before_phrase = text[max(0, index - 35):index]

    return any(
        re.search(rf"\b{re.escape(word)}\b", before_phrase)
        for word in NEGATION_WORDS
    )


# ============================================================
# 6. GENERIC SCORING ENGINE
# ============================================================

def score_patterns(
    text: str,
    pattern_groups: dict,
) -> dict:

    scores = {}

    for category, patterns in pattern_groups.items():

        score = 0.0

        for pattern in patterns:

            if pattern.phrase in text:

                if is_negated(text, pattern.phrase):
                    continue

                score += pattern.weight

        scores[category] = score

    return scores


def get_best_category(scores: dict):
    """
    Return best category and its score.
    """

    if not scores:
        return None, 0.0

    sorted_scores = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_category, best_score = sorted_scores[0]

    if best_score <= 0:
        return None, 0.0

    return best_category, best_score


# ============================================================
# 7. CONFIDENCE
# ============================================================

def calculate_confidence(scores: dict) -> float:

    positive_scores = sorted(
        [score for score in scores.values() if score > 0],
        reverse=True,
    )

    if not positive_scores:
        return 0.0

    best = positive_scores[0]

    if len(positive_scores) == 1:
        confidence = min(0.95, 0.55 + (best / 10))

    else:
        second = positive_scores[1]

        separation = best - second

        confidence = 0.50 + min(
            separation / 10,
            0.45,
        )

    return round(min(confidence, 0.99), 2)


# ============================================================
# 8. RECOVERY ACTION SELECTION
# ============================================================

def choose_recovery_action(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    sensitive: bool,
) -> RecoveryAction:

    # Security/sensitive situations always stop automation.
    if sensitive:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.SECURITY_ACCESS:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if customer_intent == CustomerIntent.DISPUTE:
        return RecoveryAction.STOP_RECOVERY

    if customer_intent == CustomerIntent.SECURITY_CONCERN:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.FINANCIAL:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.FINANCIAL_DIFFICULTY:
        return RecoveryAction.HUMAN_ESCALATION

    if problem_type == ProblemType.TECHNICAL:

        if customer_intent == CustomerIntent.WILLING_TO_PAY:
            return RecoveryAction.OFFER_RETRY

        return RecoveryAction.OFFER_ALTERNATE_PAYMENT

    if problem_type == ProblemType.CHECKOUT_ABANDONMENT:
        return RecoveryAction.OFFER_RETRY

    if problem_type == ProblemType.TIMING:
        return RecoveryAction.SCHEDULE_REMINDER

    if problem_type == ProblemType.AUTHENTICATION:
        return RecoveryAction.HUMAN_ESCALATION

    if customer_intent == CustomerIntent.WILLING_TO_PAY:
        return RecoveryAction.OFFER_RETRY

    if customer_intent == CustomerIntent.DELAYING_PAYMENT:
        return RecoveryAction.SCHEDULE_REMINDER

    return RecoveryAction.HUMAN_ESCALATION


# ============================================================
# 9. EXPLANATION GENERATOR
# ============================================================

def build_explanation(
    problem_type: ProblemType,
    customer_intent: CustomerIntent,
    action: RecoveryAction,
    confidence: float,
) -> str:

    confidence_percent = int(confidence * 100)

    return (
        f"Detected {problem_type.value.lower().replace('_', ' ')} "
        f"with customer intent classified as "
        f"{customer_intent.value.lower().replace('_', ' ')}. "
        f"Recommended action: "
        f"{action.value.lower().replace('_', ' ')}. "
        f"Diagnosis confidence: {confidence_percent}%."
    )


# ============================================================
# 10. MAIN DIAGNOSIS FUNCTION
# ============================================================

def diagnose_message(message: str) -> AIDiagnosis:

    text = normalize_text(message)

    # Empty / invalid input.
    if not text:
        return AIDiagnosis(
            problem_type=ProblemType.UNKNOWN,
            customer_intent=CustomerIntent.UNKNOWN,
            recommended_action=RecoveryAction.HUMAN_ESCALATION,
            explanation="The customer message is empty or could not be understood.",
        )

    sensitive = contains_sensitive_information_request(text)

    # Score problem and intent independently.
    problem_scores = score_patterns(
        text,
        PROBLEM_PATTERNS,
    )

    intent_scores = score_patterns(
        text,
        INTENT_PATTERNS,
    )

    problem_type, problem_score = get_best_category(
        problem_scores
    )

    customer_intent, intent_score = get_best_category(
        intent_scores
    )

    if problem_type is None:
        problem_type = ProblemType.UNKNOWN

    if customer_intent is None:
        customer_intent = CustomerIntent.UNKNOWN

    # Security takes precedence.
    if sensitive:
        problem_type = ProblemType.AUTHENTICATION
        customer_intent = CustomerIntent.SECURITY_CONCERN

    problem_confidence = calculate_confidence(
        problem_scores
    )

    intent_confidence = calculate_confidence(
        intent_scores
    )

    confidence = round(
        (problem_confidence + intent_confidence) / 2,
        2,
    )

    if problem_type == ProblemType.UNKNOWN:
        confidence = 0.0

    action = choose_recovery_action(
        problem_type,
        customer_intent,
        sensitive,
    )

    explanation = build_explanation(
        problem_type,
        customer_intent,
        action,
        confidence,
    )

    if sensitive:
        explanation += (
            " Sensitive payment credentials must not be requested "
            "or handled by the recovery agent."
        )

    return AIDiagnosis(
        problem_type=problem_type,
        customer_intent=customer_intent,
        recommended_action=action,
        explanation=explanation,
    )


# ============================================================
# 11. BACKWARD-COMPATIBLE HELPER
# ============================================================

def detect_problem(message: str) -> ProblemType:
    """
    Compatibility helper for our earlier tests.
    """

    return diagnose_message(message).problem_type