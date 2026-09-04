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
    RevenueObligation,
    RevenuePlan,
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