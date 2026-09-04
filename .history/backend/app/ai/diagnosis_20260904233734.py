import re

from app.models.revenue import ProblemType


def normalize_text(message: str) -> str:
    """
    Clean the customer's message so our AI
    can analyze it consistently.
    """

    message = message.lower()

    # Remove punctuation
    message = re.sub(r"[^a-z0-9\s]", " ", message)

    # Remove extra spaces
    message = re.sub(r"\s+", " ", message).strip()

    return message


PROBLEM_PATTERNS = {
    ProblemType.TECHNICAL: [
        "bank server",
        "bank app",
        "server down",
        "not working",
        "technical problem",
        "technical issue",
        "internet problem",
        "network problem",
        "connection problem",
        "payment failed",
    ],

    ProblemType.CHECKOUT_ABANDONMENT: [
        "forgot to pay",
        "did not complete",
        "didn't complete",
        "left the payment",
        "closed the page",
        "forgot",
        "will complete",
    ],

    ProblemType.FINANCIAL: [
        "cannot afford",
        "can't afford",
        "no money",
        "don't have money",
        "financial problem",
        "financial issue",
        "short of money",
    ],

    ProblemType.TIMING: [
        "pay later",
        "later",
        "tomorrow",
        "next week",
        "busy",
        "will pay",
        "not now",
    ],

    ProblemType.AUTHENTICATION: [
        "forgot pin",
        "forgot my pin",
        "upi pin",
        "authentication problem",
        "login problem",
        "cannot login",
        "can't login",
    ],

    ProblemType.SECURITY_ACCESS: [
        "lost my phone",
        "phone was stolen",
        "phone stolen",
        "robbed",
        "lost phone",
        "cannot access my phone",
    ],

    ProblemType.DISPUTE: [
        "wrong vendor",
        "wrong merchant",
        "wrong payment",
        "i paid someone else",
        "this is not my payment",
        "dispute",
        "refund",
    ],
}


def detect_problem(message: str) -> ProblemType:
    """
    Detect the most likely problem type
    from the customer's message.
    """

    text = normalize_text(message)

    scores = {}

    for problem_type, patterns in PROBLEM_PATTERNS.items():

        score = 0

        for pattern in patterns:

            if pattern in text:
                score += 1

        scores[problem_type] = score

    best_problem = max(scores, key=scores.get)

    if scores[best_problem] == 0:
        return ProblemType.UNKNOWN

    return best_problem