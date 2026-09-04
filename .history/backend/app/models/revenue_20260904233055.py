from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field



class RevenueStatus(str, Enum):
    EXPECTED = "EXPECTED"
    RECEIVED = "RECEIVED"
    AT_RISK = "AT_RISK"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    RECOVERED = "RECOVERED"
    PARTIAL = "PARTIAL"


class Frequency(str, Enum):
    ONE_TIME = "ONE_TIME"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class CustomerCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None

class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RevenuePlanCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    frequency: Frequency
    start_date: date

class RevenueObligationCreate(BaseModel):
    customer_id: str
    plan_id: str | None = None
    expected_amount: float = Field(gt=0)
    due_date: date    

class RevenuePlan(BaseModel):
    plan_id: str
    customer_id: str
    amount: float = Field(gt=0)
    frequency: Frequency
    start_date: date
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RevenueObligation(BaseModel):
    revenue_id: str
    customer_id: str
    plan_id: str | None = None

    expected_amount: float = Field(gt=0)
    due_date: date

    received_amount: float = Field(default=0, ge=0)

    status: RevenueStatus = RevenueStatus.EXPECTED

    recovery_attempted: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def remaining_amount(self) -> float:
        return max(self.expected_amount - self.received_amount, 0)


class PaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class PaymentCreate(BaseModel):
    revenue_id: str
    amount: float = Field(gt=0)
    status: PaymentStatus


class Payment(BaseModel):
    payment_id: str
    revenue_id: str
    customer_id: str
    amount: float = Field(gt=0)
    status: PaymentStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)    

class CustomerIntent(str, Enum):
    WILLING_TO_PAY = "WILLING_TO_PAY"
    DELAYING_PAYMENT = "DELAYING_PAYMENT"
    FINANCIAL_DIFFICULTY = "FINANCIAL_DIFFICULTY"
    DISPUTE = "DISPUTE"
    SECURITY_CONCERN = "SECURITY_CONCERN"
    UNKNOWN = "UNKNOWN"


class ProblemType(str, Enum):
    TECHNICAL = "TECHNICAL"
    CHECKOUT_ABANDONMENT = "CHECKOUT_ABANDONMENT"
    FINANCIAL = "FINANCIAL"
    TIMING = "TIMING"
    AUTHENTICATION = "AUTHENTICATION"
    SECURITY_ACCESS = "SECURITY_ACCESS"
    DISPUTE = "DISPUTE"
    UNKNOWN = "UNKNOWN"


class RecoveryAction(str, Enum):
    OFFER_RETRY = "OFFER_RETRY"
    SEND_REMINDER = "SEND_REMINDER"
    SCHEDULE_REMINDER = "SCHEDULE_REMINDER"
    OFFER_ALTERNATE_PAYMENT = "OFFER_ALTERNATE_PAYMENT"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    STOP_RECOVERY = "STOP_RECOVERY"


class AIDiagnosis(BaseModel):
    problem_type: ProblemType
    customer_intent: CustomerIntent
    recommended_action: RecoveryAction
    explanation: str    