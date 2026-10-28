import httpx
import pytest

from clauselens.adapters.http import send_with_retries
from clauselens.domain.errors import ErrorCategory, ResearchError


def responses(*items: httpx.Response | Exception):  # type: ignore[no-untyped-def]
    queue = list(items)
    calls = {"n": 0}

    def send() -> httpx.Response:
        calls["n"] += 1
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return send, calls


def call(send, max_retries: int = 2):  # type: ignore[no-untyped-def]
    sleeps: list[float] = []
    resp = send_with_retries(send, provider="p", operation="op", max_retries=max_retries, error_cls=ResearchError,
                             sleep=sleeps.append)
    return resp, sleeps


def test_transient_errors_are_retried_then_succeed() -> None:
    send, calls = responses(httpx.Response(503), httpx.ReadTimeout("t"), httpx.Response(200, json={}))
    resp, sleeps = call(send)
    assert resp.status_code == 200 and calls["n"] == 3 and len(sleeps) == 2


def test_retry_after_header_is_respected_and_capped() -> None:
    send, _ = responses(httpx.Response(429, headers={"retry-after": "120"}), httpx.Response(200))
    _, sleeps = call(send)
    assert sleeps == [30.0]


@pytest.mark.parametrize("status,category", [(401, ErrorCategory.AUTHENTICATION), (402, ErrorCategory.QUOTA),
                                             (403, ErrorCategory.BLOCKED), (400, ErrorCategory.INVALID_REQUEST)])
def test_non_transient_errors_fail_fast(status: int, category: ErrorCategory) -> None:
    send, calls = responses(httpx.Response(status, json={"error": {"code": "X", "message": "nope"}}))
    with pytest.raises(ResearchError) as exc:
        call(send)
    assert exc.value.category is category and calls["n"] == 1
    assert "X: nope" in exc.value.message


def test_retry_budget_is_bounded() -> None:
    send, calls = responses(*[httpx.Response(500)] * 5)
    with pytest.raises(ResearchError) as exc:
        call(send, max_retries=2)
    assert calls["n"] == 3 and exc.value.category is ErrorCategory.UNAVAILABLE


def test_network_error_translated() -> None:
    send, _ = responses(httpx.ConnectError("refused"))
    with pytest.raises(ResearchError) as exc:
        call(send, max_retries=0)
    assert exc.value.category is ErrorCategory.UNAVAILABLE and exc.value.provider == "p"
