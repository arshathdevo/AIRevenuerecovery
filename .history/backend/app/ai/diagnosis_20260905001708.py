(venv) PS C:\Users\arsha\OneDrive\Desktop\AIRevenueRecovery\backend> python -m pytest -q
.....F..F........F..........                                                                                                   [100%]
============================================================= FAILURES ==============================================================
______________ test_core_scenarios[I can't pay until my salary comes.-FINANCIAL-FINANCIAL_DIFFICULTY-HUMAN_ESCALATION] ______________

message = "I can't pay until my salary comes.", problem = <ProblemType.FINANCIAL: 'FINANCIAL'>
intent = <CustomerIntent.FINANCIAL_DIFFICULTY: 'FINANCIAL_DIFFICULTY'>, action = <RecoveryAction.HUMAN_ESCALATION: 'HUMAN_ESCALATION'>

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
    
>       assert result.problem_type == problem
E       AssertionError: assert <ProblemType....WN: 'UNKNOWN'> == <ProblemType....: 'FINANCIAL'>
E         
E         - FINANCIAL
E         + UNKNOWN

tests\test_diagnosis.py:199: AssertionError
__________________ test_core_scenarios[I forgot to complete the payment.-CHECKOUT_ABANDONMENT-UNKNOWN-OFFER_RETRY] __________________

message = 'I forgot to complete the payment.', problem = <ProblemType.CHECKOUT_ABANDONMENT: 'CHECKOUT_ABANDONMENT'>
intent = <CustomerIntent.UNKNOWN: 'UNKNOWN'>, action = <RecoveryAction.OFFER_RETRY: 'OFFER_RETRY'>

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
    
>       assert result.customer_intent == intent
E       AssertionError: assert <CustomerInte...LLING_TO_PAY'> == <CustomerInte...WN: 'UNKNOWN'>
E         
E         - UNKNOWN
E         + WILLING_TO_PAY

tests\test_diagnosis.py:201: AssertionError
_ test_core_scenarios[I don't have any problem with my bank app. I just forgot to finish the payment.-CHECKOUT_ABANDONMENT-UNKNOWN-OFFER_RETRY] _

message = "I don't have any problem with my bank app. I just forgot to finish the payment."
problem = <ProblemType.CHECKOUT_ABANDONMENT: 'CHECKOUT_ABANDONMENT'>, intent = <CustomerIntent.UNKNOWN: 'UNKNOWN'>
action = <RecoveryAction.OFFER_RETRY: 'OFFER_RETRY'>

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
    
>       assert result.customer_intent == intent
E       AssertionError: assert <CustomerInte...LLING_TO_PAY'> == <CustomerInte...WN: 'UNKNOWN'>
E         
E         - UNKNOWN
E         + WILLING_TO_PAY

tests\test_diagnosis.py:201: AssertionError
====================================================== short test summary info ======================================================
FAILED tests/test_diagnosis.py::test_core_scenarios[I can't pay until my salary comes.-FINANCIAL-FINANCIAL_DIFFICULTY-HUMAN_ESCALATION] - AssertionError: assert <ProblemType....WN: 'UNKNOWN'> == <ProblemType....: 'FINANCIAL'>
FAILED tests/test_diagnosis.py::test_core_scenarios[I forgot to complete the payment.-CHECKOUT_ABANDONMENT-UNKNOWN-OFFER_RETRY] - AssertionError: assert <CustomerInte...LLING_TO_PAY'> == <CustomerInte...WN: 'UNKNOWN'>
FAILED tests/test_diagnosis.py::test_core_scenarios[I don't have any problem with my bank app. I just forgot to finish the payment.-CHECKOUT_ABANDONMENT-UNKNOWN-OFFER_RETRY] - AssertionError: assert <CustomerInte...LLING_TO_PAY'> == <CustomerInte...WN: 'UNKNOWN'>
3 failed, 25 passed in 3.23s