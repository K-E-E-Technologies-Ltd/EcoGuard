from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator

Category = Literal['wildlife', 'wetland', 'flood']
Role = Literal['reporter','reviewer','publisher','responder','admin']
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Register(Strict):
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=128)

class Login(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class PasswordChange(Strict):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)

class Preferences(Strict):
    name: str = Field(min_length=2, max_length=100)
    followed_areas: list[str] = Field(default_factory=list, max_length=30)
    in_app: bool = True
    phone: str = Field(default='', max_length=20, pattern=r'^(\+[1-9]\d{6,14})?$')
    sms_opt_in: bool = False
    language: Literal['en'] = 'en'

class UserAccess(Strict):
    roles: list[Role] = Field(min_length=1, max_length=5)
    areas: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True

class UserCreate(Register):
    roles: list[Role] = Field(default_factory=lambda: ['reporter'])
    areas: list[str] = Field(default_factory=list)

class ReportWrite(Strict):
    client_id: str = Field(min_length=8, max_length=64)
    category: Category
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    area_id: str = Field(min_length=1, max_length=36)
    species: str = Field(default='Unknown animal', max_length=100)
    observed_at: datetime
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    share_location: bool = False
    consent: bool
    evidence_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator('observed_at')
    @classmethod
    def observation_time(cls, v):
        v = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
        if (v - datetime.now(timezone.utc)).total_seconds() > 600:
            raise ValueError('Observation time cannot be more than ten minutes in the future.')
        return v

    @model_validator(mode='after')
    def consent_and_position(self):
        if not self.consent:
            raise ValueError('Consent is required before transmitting a report.')
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Supply both latitude and longitude, or neither.')
        if self.latitude is not None and not self.share_location:
            raise ValueError('Private location sharing must be explicitly permitted.')
        return self

class ReportUpdate(ReportWrite):
    version: int = Field(ge=1)

class VersionRequest(Strict):
    version: int = Field(ge=1)

class ReviewWrite(VersionRequest):
    decision: Literal['under_review','verified','needs_evidence','rejected']
    notes: str = Field(min_length=5, max_length=3000)
    species: str | None = Field(default=None, max_length=100)

class AssignWrite(VersionRequest):
    assignee_id: str

class CloseWrite(VersionRequest):
    note: str = Field(min_length=5, max_length=3000)

class PredictionWrite(Strict):
    evidence_id: str

class AdvisoryWrite(Strict):
    report_id: str
    title: str = Field(min_length=5, max_length=160)
    body: str = Field(min_length=20, max_length=2000)
    source: str = Field(min_length=5, max_length=250)
    expires_at: datetime

    @field_validator('expires_at')
    @classmethod
    def expiry(cls, v):
        v = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
        delta = (v - datetime.now(timezone.utc)).total_seconds()
        if not 0 < delta <= 30 * 86400:
            raise ValueError('Expiry must be in the future, within 30 days.')
        return v

class PublishWrite(VersionRequest):
    privacy_checked: bool
    evidence_checked: bool

class RetractWrite(VersionRequest):
    reason: str = Field(min_length=5, max_length=2000)

class MessageWrite(Strict):
    body: str = Field(min_length=1, max_length=3000)
