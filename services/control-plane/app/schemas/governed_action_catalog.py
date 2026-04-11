"""Governed Action Catalog v1 — safe launch metadata for Command Center + voice (no secrets)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GovernedActionFieldRead(BaseModel):
    name: str
    type: str = Field(
        ...,
        description="text | textarea | comma_list | email_list | checkbox | select | number",
    )
    required: bool = False
    label: str
    placeholder: str | None = None
    help_hint: str | None = None
    validation_hint: str | None = None
    voice_prompt: str | None = Field(
        None,
        description="Spoken prompt when collecting this field in voice (governed_action_voice).",
    )
    options: list[dict[str, str]] | None = Field(
        None,
        description="For select: [{\"value\": \"...\", \"label\": \"...\"}]",
    )


class GovernedActionCatalogEntryRead(BaseModel):
    action_kind: str
    provider: str = Field(..., description="github | gmail")
    title: str
    description: str
    route_method: str = "POST"
    route_path_suffix: str = Field(
        ...,
        description="Relative to /api/v1/missions/{mission_id}/ — e.g. integrations/github/create-issue",
    )
    surfaces: dict[str, bool] = Field(
        default_factory=lambda: {"command_center": True, "voice": True},
    )
    approval_action_type: str
    risk_class: str = "red"
    field_order: list[str]
    fields: list[GovernedActionFieldRead]
    summary_template: str = Field(
        ...,
        description="Template for voice confirm step; {field} placeholders.",
    )
    voice_internal_kind: str | None = Field(
        None,
        description="Voice draft kind key (gh_issue, gh_pr, …) — matches governed_action_voice.",
    )
    voice_intro: str | None = Field(None, description="Spoken line when starting this flow in voice.")
    enabled: bool = True


class GovernedActionCatalogResponse(BaseModel):
    catalog_version: int = 1
    generated_at: str
    actions: list[GovernedActionCatalogEntryRead]
