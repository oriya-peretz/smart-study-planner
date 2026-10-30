"""Smart Study Planner AI service: builds a study plan. It stores nothing."""

import asyncio
import logging
import os

from fastapi import FastAPI
from pydantic_ai import (
    ModelAPIError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
    UserError,
)

from app.agent import LIMITS, PlanDeps, plan_agent, user_prompt
from app.planner import make_plan
from app.schemas import FallbackReason, PlanRequest, PlanResponse

logger = logging.getLogger("ai-service")

# A wall-clock cap on the model; a local model may need more than the default.
MODEL_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "25"))

app = FastAPI(title="Smart Study Planner AI service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan")
async def plan(body: PlanRequest) -> PlanResponse:
    """The model's week if it keeps every rule, otherwise the baseline plan."""
    baseline = make_plan(body)
    if not any(day.blocks for day in baseline.days):
        return baseline  # nothing to arrange, so nothing to pay for

    def fallback(reason: FallbackReason) -> PlanResponse:
        # Logs hold the reason only, never the user's tasks or note.
        logger.warning("plan fallback: reason=%s", reason.value)
        return baseline.model_copy(update={"fallback_reason": reason})

    deps = PlanDeps(body, baseline)
    try:
        async with asyncio.timeout(MODEL_TIMEOUT_SECONDS):
            result = await plan_agent.run(
                user_prompt(body), deps=deps, usage_limits=LIMITS
            )
    except UsageLimitExceeded:
        return fallback(FallbackReason.BUDGET_EXCEEDED)
    except UnexpectedModelBehavior:  # still invalid after the agent's retries
        return fallback(FallbackReason.INVALID_OUTPUT)
    except ModelAPIError, UserError:  # no answer, or a missing key or model
        return fallback(FallbackReason.PROVIDER_ERROR)
    except TimeoutError:
        return fallback(FallbackReason.TIMEOUT)

    usage = result.usage
    logger.info(
        "plan from model: requests=%d total_tokens=%d",
        usage.requests,
        usage.total_tokens,
    )
    return make_plan(body, result.output)
