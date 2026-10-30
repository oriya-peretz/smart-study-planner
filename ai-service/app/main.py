"""Smart Study Planner AI service: builds a study plan. It stores nothing."""

from fastapi import FastAPI

from app.planner import make_plan
from app.schemas import PlanRequest, PlanResponse

app = FastAPI(title="Smart Study Planner AI service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan")
def plan(body: PlanRequest) -> PlanResponse:
    # Step 1: the deterministic baseline only. The model (step 2) will propose
    # a plan, checked against the same rules, with this one as its fallback.
    return make_plan(body)
