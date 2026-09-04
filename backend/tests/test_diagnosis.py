import pytest

from app.ai.diagnosis import (
    analyze_message,
    diagnose_message,
    normalize_text,
    redact_sensitive_information,
)

from app.models.revenue import (
    CustomerIntent,
    ProblemType,
    RecoveryAction,
)


@pytest.mark.parametrize(
    "message,problem,intent,action",
    [

        # ----------------------------------------------------
        # TECHNICAL
        # ----------------------------------------------------

        (
            "My bank app is not working and I will try again "
            "in a few minutes.",
            ProblemType.TECHNICAL,
            CustomerIntent.WILLING_TO_PAY,
            RecoveryAction.OFFER_RETRY,
        ),

        (
            "My bank server is down.",
            ProblemType.TECHNICAL,
            CustomerIntent.UNKNOWN,
            RecoveryAction.OFFER_ALTERNATE_PAYMENT,
        ),

        (
            "The payment timed out because my network was poor.",
            ProblemType.TECHNICAL,
            CustomerIntent.UNKNOWN,
            RecoveryAction.OFFER_ALTERNATE_PAYMENT,
        ),

        # ----------------------------------------------------
        # FINANCIAL
        # ----------------------------------------------------

        (
            "I don't have enough money right now.",
            ProblemType.FINANCIAL,
            CustomerIntent.FINANCIAL_DIFFICULTY,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        (
            "I cannot afford this payment.",
            ProblemType.FINANCIAL,
            CustomerIntent.FINANCIAL_DIFFICULTY,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        (
            "I can't pay until my salary comes.",
            ProblemType.FINANCIAL,
            CustomerIntent.FINANCIAL_DIFFICULTY,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        # ----------------------------------------------------
        # TIMING
        # ----------------------------------------------------

        (
            "I will pay tomorrow, I am busy today.",
            ProblemType.TIMING,
            CustomerIntent.DELAYING_PAYMENT,
            RecoveryAction.SCHEDULE_REMINDER,
        ),

        (
            "I can pay, but not today.",
            ProblemType.TIMING,
            CustomerIntent.DELAYING_PAYMENT,
            RecoveryAction.SCHEDULE_REMINDER,
        ),

        # ----------------------------------------------------
        # CHECKOUT
        # ----------------------------------------------------

        (
            "I forgot to complete the payment.",
            ProblemType.CHECKOUT_ABANDONMENT,
            CustomerIntent.UNKNOWN,
            RecoveryAction.OFFER_RETRY,
        ),

        (
            "I closed the payment page accidentally. "
            "I want to complete it.",
            ProblemType.CHECKOUT_ABANDONMENT,
            CustomerIntent.WILLING_TO_PAY,
            RecoveryAction.OFFER_RETRY,
        ),

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        (
            "My phone was stolen and I cannot access my payment app.",
            ProblemType.SECURITY_ACCESS,
            CustomerIntent.SECURITY_CONCERN,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        (
            "I lost my phone.",
            ProblemType.SECURITY_ACCESS,
            CustomerIntent.SECURITY_CONCERN,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        # ----------------------------------------------------
        # AUTHENTICATION
        # ----------------------------------------------------

        (
            "I forgot my UPI PIN.",
            ProblemType.AUTHENTICATION,
            CustomerIntent.SECURITY_CONCERN,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        (
            "My account is locked and I cannot log in.",
            ProblemType.AUTHENTICATION,
            CustomerIntent.UNKNOWN,
            RecoveryAction.HUMAN_ESCALATION,
        ),

        # ----------------------------------------------------
        # DISPUTES
        # ----------------------------------------------------

        (
            "I paid the wrong vendor.",
            ProblemType.DISPUTE,
            CustomerIntent.DISPUTE,
            RecoveryAction.STOP_RECOVERY,
        ),

        (
            "I was charged twice.",
            ProblemType.DISPUTE,
            CustomerIntent.DISPUTE,
            RecoveryAction.STOP_RECOVERY,
        ),

        (
            "I don't recognize this payment.",
            ProblemType.DISPUTE,
            CustomerIntent.DISPUTE,
            RecoveryAction.STOP_RECOVERY,
        ),

        # ----------------------------------------------------
        # NEGATION
        # ----------------------------------------------------

        (
            "I don't have any problem with my bank app. "
            "I just forgot to finish the payment.",
            ProblemType.CHECKOUT_ABANDONMENT,
            CustomerIntent.UNKNOWN,
            RecoveryAction.OFFER_RETRY,
        ),

        (
            "I don't want to pay.",
            ProblemType.UNKNOWN,
            CustomerIntent.UNKNOWN,
            RecoveryAction.HUMAN_ESCALATION,
        ),
    ],
)
def test_core_scenarios(
    message,
    problem,
    intent,
    action,
):

    result = diagnose_message(message)

    assert result.problem_type == problem

    assert result.customer_intent == intent

    assert result.recommended_action == action


def test_contraction_normalization():

    result = normalize_text(
        "I don't have enough money."
    )

    assert result == (
        "i do not have enough money"
    )


def test_negation_does_not_create_false_technical_match():

    result = analyze_message(
        "I do not have a bank problem. "
        "I forgot to complete the payment."
    )

    assert (
        result.problem_type
        == ProblemType.CHECKOUT_ABANDONMENT
    )


def test_negation_does_not_create_false_willingness():

    result = analyze_message(
        "I do not want to pay."
    )

    assert result.willingness_to_pay is False

    assert (
        result.customer_intent
        == CustomerIntent.UNKNOWN
    )


def test_willingness_and_delay_are_both_detected():

    result = analyze_message(
        "I will pay tomorrow."
    )

    assert result.willingness_to_pay is True

    assert result.delay_signal is True

    assert (
        result.customer_intent
        == CustomerIntent.DELAYING_PAYMENT
    )


def test_sensitive_message_is_escalated():

    result = analyze_message(
        "I forgot my UPI PIN."
    )

    assert result.sensitive is True

    assert (
        result.problem_type
        == ProblemType.AUTHENTICATION
    )

    assert (
        result.recommended_action
        == RecoveryAction.HUMAN_ESCALATION
    )


def test_sensitive_value_is_redacted():

    result = redact_sensitive_information(
        "My OTP is 123456."
    )

    assert "123456" not in result

    assert "[REDACTED]" in result


def test_empty_message_is_safe():

    result = diagnose_message("")

    assert (
        result.problem_type
        == ProblemType.UNKNOWN
    )

    assert (
        result.customer_intent
        == CustomerIntent.UNKNOWN
    )

    assert (
        result.recommended_action
        == RecoveryAction.HUMAN_ESCALATION
    )


def test_garbage_message_is_safe():

    result = diagnose_message(
        "asdf qwer zxcv"
    )

    assert (
        result.problem_type
        == ProblemType.UNKNOWN
    )

    assert (
        result.recommended_action
        == RecoveryAction.HUMAN_ESCALATION
    )


def test_contradiction_is_safe():

    result = analyze_message(
        "I want to pay but I do not want to pay."
    )

    assert result.contradiction is True

    assert (
        result.recommended_action
        == RecoveryAction.HUMAN_ESCALATION
    )