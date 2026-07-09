from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AuthMethod = Literal["oauth2", "api_key", "basic", "token", "other"]
AccessTier = Literal[
    "self_serve_free",
    "self_serve_trial",
    "paid_plan_required",
    "admin_approval_required",
    "partner_gated_contact_sales",
]
ApiSurfaceType = Literal["REST", "GraphQL", "Both", "None"]
BuildabilityVerdict = Literal["ready_today", "ready_with_workaround", "blocked"]


class AppInput(BaseModel):
    """One app from the assignment-provided apps.json file."""

    model_config = ConfigDict(extra="allow")

    id: int
    app: str
    category: str
    hint_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "app" not in normalized:
            for key in ("name", "app_name", "tool", "service"):
                if normalized.get(key):
                    normalized["app"] = normalized[key]
                    break
        if "hint_url" not in normalized:
            for key in (
                "hint",
                "url",
                "website",
                "homepage",
                "docs_url",
                "developer_url",
                "api_docs_url",
            ):
                if normalized.get(key):
                    normalized["hint_url"] = normalized[key]
                    break
        return normalized

    @field_validator("hint_url", mode="before")
    @classmethod
    def normalize_hint_url(cls, value: Any) -> str | None:
        if value is None or not str(value).strip():
            return None
        cleaned = str(value).strip()
        if cleaned.startswith(("http://", "https://")):
            return cleaned
        return f"https://{cleaned}"


class ApiSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ApiSurfaceType
    breadth: str
    mcp_exists: bool
    mcp_notes: str


class AppResearchResult(BaseModel):
    """Exact per-app output schema consumed by the downstream web app."""

    model_config = ConfigDict(extra="forbid")

    id: int
    app: str
    category: str
    description: str
    auth_methods: list[AuthMethod]
    auth_notes: str
    access_tier: AccessTier
    gating_reason: str
    api_surface: ApiSurface
    buildability_verdict: BuildabilityVerdict
    blocker: str | None
    evidence_urls: list[str]
    rate_limit_notes: str
    notable_signals: str
    agent_confidence: int = Field(ge=0, le=100)
    needs_human_review: bool
    human_review_reason: str

    @field_validator("app", "category", "description")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field cannot be blank")
        return value

    @field_validator(
        "auth_notes",
        "gating_reason",
        "rate_limit_notes",
        "notable_signals",
        "human_review_reason",
        mode="before",
    )
    @classmethod
    def blankable_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("auth_methods")
    @classmethod
    def auth_methods_nonempty(cls, value: list[AuthMethod]) -> list[AuthMethod]:
        if not value:
            raise ValueError("auth_methods must contain at least one method")
        deduped: list[AuthMethod] = []
        for method in value:
            if method not in deduped:
                deduped.append(method)
        return deduped

    @field_validator("evidence_urls")
    @classmethod
    def evidence_urls_are_http(cls, value: list[str]) -> list[str]:
        deduped: list[str] = []
        for url in value:
            cleaned = str(url).strip()
            if not cleaned:
                continue
            if not cleaned.startswith(("http://", "https://")):
                raise ValueError(f"evidence URL must be absolute HTTP(S): {cleaned}")
            if cleaned not in deduped:
                deduped.append(cleaned)
        return deduped

    @model_validator(mode="after")
    def evidence_or_review_required(self) -> AppResearchResult:
        if not self.evidence_urls and not self.needs_human_review:
            raise ValueError("missing evidence_urls requires needs_human_review=true")
        if self.needs_human_review and not self.human_review_reason:
            raise ValueError("needs_human_review=true requires human_review_reason")
        if self.buildability_verdict == "ready_today" and self.blocker:
            raise ValueError("ready_today rows must not have a blocker")
        if self.buildability_verdict != "ready_today" and not self.blocker:
            raise ValueError("non-ready verdicts require a blocker")
        return self


class VerificationGroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: int
    app: str
    verified_result: AppResearchResult
    evidence_checked: list[str]
    verification_notes: str

    @field_validator("evidence_checked")
    @classmethod
    def evidence_checked_are_http(cls, value: list[str]) -> list[str]:
        checked: list[str] = []
        for url in value:
            cleaned = str(url).strip()
            if cleaned.startswith(("http://", "https://")) and cleaned not in checked:
                checked.append(cleaned)
        return checked

    @model_validator(mode="after")
    def verified_identity_and_evidence_match(self) -> VerificationGroundTruth:
        if self.verified_result.id != self.app_id:
            raise ValueError("verified_result.id must match app_id")
        if self.verified_result.app != self.app:
            raise ValueError("verified_result.app must match app")
        unchecked = set(self.verified_result.evidence_urls) - set(self.evidence_checked)
        if unchecked:
            raise ValueError(
                "verified_result.evidence_urls must be a subset of evidence_checked: "
                f"{sorted(unchecked)}"
            )
        return self


COMPARISON_FIELDS = [
    "description",
    "auth_methods",
    "auth_notes",
    "access_tier",
    "gating_reason",
    "api_surface.type",
    "api_surface.breadth",
    "api_surface.mcp_exists",
    "api_surface.mcp_notes",
    "buildability_verdict",
    "blocker",
    "evidence_urls",
    "rate_limit_notes",
    "notable_signals",
    "needs_human_review",
    "human_review_reason",
]


def get_nested_field(model: BaseModel | dict[str, Any], dotted_field: str) -> Any:
    value: Any = model.model_dump(mode="json") if isinstance(model, BaseModel) else model
    for part in dotted_field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
