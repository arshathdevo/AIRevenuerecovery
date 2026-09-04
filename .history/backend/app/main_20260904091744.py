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
from fastapi import FastAPI

from app.models.revenue import (
    Customer,
    Frequency,
    RevenueObligation,
    RevenuePlan,
)

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