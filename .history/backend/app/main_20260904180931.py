# from fastapi import FastAPI

# app = FastAPI(
#     title="Revenue Recovery API",
#     description="AI-powered revenue recovery platform",
#     version="0.1.0"
# )


# @app.get("/")
# def root():
#     return {
#         "message": "Revenue Recovery API is running 🚀"
#     }

import uuid
from app.models.revenue import (
    Customer,
    CustomerCreate,
    Frequency,
    Payment,
    PaymentCreate,
    PaymentStatus,
    RevenueObligation,
    RevenueObligationCreate,
    RevenuePlan,
    RevenuePlanCreate,
    RevenueStatus,
)
from fastapi import FastAPI


app = FastAPI(
    title="AI Revenue Recovery",
    description="AI-powered revenue recovery platform",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "AI Revenue Recovery API is running 🚀"
    }


@app.get("/test-revenue")
def test_revenue():

    customer = Customer(
        customer_id="CUS_001",
        name="Rahul",
        email="rahul@example.com",
    )

    plan = RevenuePlan(
        plan_id="PLAN_001",
        customer_id=customer.customer_id,
        amount=20000,
        frequency=Frequency.MONTHLY,
        start_date="2026-09-10",
    )

    obligation = RevenueObligation(
        revenue_id="REV_001",
        customer_id=customer.customer_id,
        plan_id=plan.plan_id,
        expected_amount=20000,
        due_date="2026-09-10",
    )

    return {
        "customer": customer.model_dump(),
        "plan": plan.model_dump(),
        "obligation": {
            **obligation.model_dump(),
            "remaining_amount": obligation.remaining_amount,
        },
    }


customers = {}
revenue_plans = {}
revenue_obligations = {}
payments = {}

@app.post("/customers", response_model=Customer)
def create_customer(customer_data: CustomerCreate):

    customer_id = f"CUS_{uuid.uuid4().hex[:8].upper()}"

    customer = Customer(
        customer_id=customer_id,
        name=customer_data.name,
        email=customer_data.email,
        phone=customer_data.phone,
    )

    customers[customer_id] = customer

    return customer

@app.get("/customers", response_model=list[Customer])
def get_customers():
    return list(customers.values())


@app.post("/revenue-plans", response_model=RevenuePlan)
def create_revenue_plan(plan_data: RevenuePlanCreate):

    print("DEBUG - Received customer ID:", repr(plan_data.customer_id))
    print("DEBUG - Stored customer IDs:", list(customers.keys()))

    if plan_data.customer_id not in customers:
        raise ValueError("Customer not found")

    plan_id = f"PLAN_{uuid.uuid4().hex[:8].upper()}"

    plan = RevenuePlan(
        plan_id=plan_id,
        customer_id=plan_data.customer_id,
        amount=plan_data.amount,
        frequency=plan_data.frequency,
        start_date=plan_data.start_date,
    )

    revenue_plans[plan_id] = plan

    return plan

@app.get("/revenue-plans", response_model=list[RevenuePlan])
def get_revenue_plans():
    return list(revenue_plans.values())

@app.post("/revenue-obligations", response_model=RevenueObligation)
def create_revenue_obligation(
    obligation_data: RevenueObligationCreate
):

    if obligation_data.customer_id not in customers:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    if (
        obligation_data.plan_id is not None
        and obligation_data.plan_id not in revenue_plans
    ):
        raise HTTPException(
            status_code=404,
            detail="Revenue plan not found"
        )

    revenue_id = f"REV_{uuid.uuid4().hex[:8].upper()}"

    obligation = RevenueObligation(
        revenue_id=revenue_id,
        customer_id=obligation_data.customer_id,
        plan_id=obligation_data.plan_id,
        expected_amount=obligation_data.expected_amount,
        due_date=obligation_data.due_date,
    )

    revenue_obligations[revenue_id] = obligation

    return obligation


@app.get("/revenue-obligations", response_model=list[RevenueObligation])
def get_revenue_obligations():
    return list(revenue_obligations.values())

@app.post("/payments", response_model=Payment)
def create_payment(payment_data: PaymentCreate):

    if payment_data.revenue_id not in revenue_obligations:
        raise HTTPException(
            status_code=404,
            detail="Revenue obligation not found"
        )

    obligation = revenue_obligations[payment_data.revenue_id]

    payment_id = f"PAY_{uuid.uuid4().hex[:8].upper()}"

    payment = Payment(
        payment_id=payment_id,
        revenue_id=payment_data.revenue_id,
        customer_id=obligation.customer_id,
        amount=payment_data.amount,
        status=payment_data.status,
    )

    payments[payment_id] = payment

    if payment_data.status == PaymentStatus.SUCCESS:
        obligation.received_amount += payment_data.amount

        if obligation.received_amount >= obligation.expected_amount:
            obligation.status = RevenueStatus.RECEIVED
        else:
            obligation.status = RevenueStatus.PARTIAL

    elif payment_data.status == PaymentStatus.PARTIAL:
        obligation.received_amount += payment_data.amount
        obligation.status = RevenueStatus.PARTIAL

    elif payment_data.status == PaymentStatus.FAILED:
        obligation.status = RevenueStatus.AT_RISK

    return payment

@app.get("/payments", response_model=list[Payment])
def get_payments():
    return list(payments.values())

@app.get("/revenue-summary")
def get_revenue_summary():

    total_expected = sum(
        obligation.expected_amount
        for obligation in revenue_obligations.values()
    )

    total_collected = sum(
        obligation.received_amount
        for obligation in revenue_obligations.values()
    )

    total_at_risk = sum(
        obligation.remaining_amount
        for obligation in revenue_obligations.values()
        if obligation.status == RevenueStatus.AT_RISK
    )

    total_outstanding = sum(
        obligation.remaining_amount
        for obligation in revenue_obligations.values()
    )

    return {
        "total_expected_revenue": total_expected,
        "total_collected_revenue": total_collected,
        "total_at_risk_revenue": total_at_risk,
        "total_outstanding_revenue": total_outstanding
    }

 