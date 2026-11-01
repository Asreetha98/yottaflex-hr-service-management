from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.constants import AUDIENCE_TYPES
from app.schemas import ORMModel


class AudienceIn(BaseModel):
    audience_type: str = "ALL"
    audience_value: Optional[str] = None

    @model_validator(mode="after")
    def _check(self) -> "AudienceIn":
        if self.audience_type not in AUDIENCE_TYPES:
            raise ValueError("audience_type must be one of %s" % ", ".join(AUDIENCE_TYPES))
        if self.audience_type != "ALL" and not self.audience_value:
            raise ValueError("audience_value is required unless audience_type is ALL")
        return self


class PolicyDocumentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    category_id: Optional[str] = None
    owner_department_id: str


class PolicyVersionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=1)
    summary: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    audiences: List[AudienceIn] = Field(default_factory=lambda: [AudienceIn()])

    @model_validator(mode="after")
    def _window(self) -> "PolicyVersionCreate":
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class PolicyVersionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class PublishRequest(BaseModel):
    effective_from: Optional[date] = None


class PolicyAudienceOut(ORMModel):
    audience_id: str
    audience_type: str
    audience_value: Optional[str] = None


class PolicyCitationOut(ORMModel):
    citation_id: str
    version_id: str
    article_id: Optional[str] = None
    section_reference: str
    excerpt: str


class PolicyVersionOut(ORMModel):
    version_id: str
    policy_id: str
    version_number: int
    title: str
    content: str
    summary: Optional[str] = None
    status: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    supersedes_version_id: Optional[str] = None
    audiences: List[PolicyAudienceOut] = []
    created_at: datetime


class PolicyDocumentOut(ORMModel):
    policy_id: str
    title: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    owner_department_id: str
    status: str
    created_at: datetime


class PolicyValidityOut(BaseModel):
    policy_id: str
    reference_date: date
    version_id: Optional[str] = None
    exception_code: Optional[str] = None
    exception_message: Optional[str] = None
    latest_created: Optional[str] = None
    latest_published: Optional[str] = None
    currently_effective: Optional[str] = None
    historically_effective: Optional[str] = None
    overlap_detected: bool = False
    explanation: str = ""
