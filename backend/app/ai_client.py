"""Backend -> AI service client: explicit timeouts, typed errors, bounded retries.

Routes see one method and two errors; they never see httpx.
"""

import os
from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends
from pydantic import ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.ai_contract import PlanRequest, PlanResponse, answer_problems

# 127.0.0.1 rather than localhost: on Windows, localhost tries IPv6 first and
# adds about 2 seconds to every request.
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001")

# A timeout per phase. Connect fast; let the model think. The AI service stops
# its model after 25 s (AI_TIMEOUT_SECONDS) and answers with its baseline plan,
# so a 30 s read leaves it time to answer.
TIMEOUT = httpx.Timeout(connect=2.0, read=30.0, write=5.0, pool=2.0)

# Retries live in this layer only: the agent already retries the model inside
# the AI service. Only "busy" (503) and "timed out" (504) are worth another try.
# Repeating POST /plan is safe: the AI service stores nothing, and the backend
# saves only the answer it finally accepts. Each attempt may cost model work.
TRANSIENT_STATUS = {503, 504}


class AIServiceUnavailable(Exception):
    """The AI service is unreachable, too slow, or failing with a 5xx."""


class AIServiceBadOutput(Exception):
    """The AI service answered, but not with a plan the backend can accept."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in TRANSIENT_STATUS
    )


class AIClient:
    def __init__(
        self,
        base_url: str = AI_SERVICE_URL,
        transport: httpx.BaseTransport | None = None,  # tests pass MockTransport
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url, timeout=TIMEOUT, transport=transport
        )

    def close(self) -> None:
        self._http.close()

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),  # bounded: 1 try + 2 retries
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,  # give up with the real httpx error, not RetryError
    )
    def _post_plan(self, body: dict) -> httpx.Response:
        response = self._http.post("/plan", json=body)
        response.raise_for_status()
        return response

    def make_plan(self, request: PlanRequest) -> PlanResponse:
        try:
            response = self._post_plan(request.model_dump(mode="json"))
        except httpx.HTTPStatusError as exc:  # it answered, with an error status
            code = exc.response.status_code
            if code < 500:  # 4xx: it rejected our request, so the contract broke
                raise AIServiceBadOutput(f"AI service returned {code}") from exc
            raise AIServiceUnavailable(f"AI service returned {code}") from exc
        except httpx.HTTPError as exc:  # timeouts, refused connections, DNS
            raise AIServiceUnavailable(f"AI service unreachable: {exc!r}") from exc
        try:
            answer = PlanResponse.model_validate_json(response.content)
        except ValidationError as exc:
            raise AIServiceBadOutput("AI service answer broke the contract") from exc
        if problems := answer_problems(request, answer):
            raise AIServiceBadOutput("; ".join(problems))
        return answer


def get_ai_client() -> Iterator[AIClient]:
    client = AIClient()
    try:
        yield client
    finally:
        client.close()


AIClientDep = Annotated[AIClient, Depends(get_ai_client)]
