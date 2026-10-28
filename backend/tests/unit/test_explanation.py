import uuid

from clauselens.domain.comparison import compare
from clauselens.domain.errors import ErrorCategory, LLMError
from clauselens.domain.models import Criterion, Priority
from clauselens.ports.llm import LLMRequest, LLMResponse
from clauselens.services.explanation import comparison_facts, generate_explanation, validate_explanation
from tests.unit.test_comparison import policy, refund


class OneShot:
    name, model, is_demo = "one", "m", False

    def __init__(self, text: str | None = None, error: LLMError | None = None) -> None:
        self.text, self.error = text, error
        self.seen: LLMRequest | None = None

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.seen = request
        if self.error:
            raise self.error
        return LLMResponse(text=self.text or "", model="m", provider="one")

    def health_check(self) -> None:
        return None


REPORT = compare([policy("A", refund(14)), policy("B", refund(30))], [Priority(criterion=Criterion.LONGEST_REFUND_WINDOW)])


def test_valid_explanation_is_accepted() -> None:
    llm = OneShot("B offers 30 days versus 14 days for A, so B fits a longer refund window best.")
    text, status = generate_explanation(llm, REPORT)
    assert status == "generated" and text is not None
    assert llm.seen is not None and "Comparison facts" in llm.seen.messages[1].content


def test_invented_numbers_are_rejected() -> None:
    text, status = generate_explanation(OneShot("B gives you 90 days to get a refund."), REPORT)
    assert (text, status) == (None, "rejected")


def test_provider_failure_is_reported_not_hidden() -> None:
    text, status = generate_explanation(OneShot(error=LLMError("down", category=ErrorCategory.UNAVAILABLE)), REPORT)
    assert (text, status) == (None, "failed")


def test_facts_never_include_raw_sources() -> None:
    facts = comparison_facts(REPORT)
    assert set(facts) == {"vendors", "terms", "priorities", "recommendation", "recommended_vendor", "confidence",
                          "reasoning", "conflicts", "missing"}


def test_validate_rejects_empty_and_long() -> None:
    assert validate_explanation("", "{}") == "empty"
    assert validate_explanation("x" * 2000, "{}") == "too long"
    assert uuid  # keep import used
