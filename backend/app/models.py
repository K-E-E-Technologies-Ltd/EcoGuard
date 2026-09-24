from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Float, Integer, Boolean, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc).isoformat()

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    roles: Mapped[list] = mapped_column(JSON, default=lambda: ['reporter'])
    areas: Mapped[list] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[float] = mapped_column(Float)

class Area(Base):
    __tablename__ = 'areas'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default='')
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    # Public centroid: never derived from a submitted wildlife position.
    radius_km: Mapped[float] = mapped_column(Float, default=10)

class Report(Base):
    __tablename__ = 'reports'
    __table_args__ = (UniqueConstraint('owner_id', 'client_id', name='uq_report_client'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    client_id: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    area_id: Mapped[str] = mapped_column(ForeignKey('areas.id'), index=True)
    category: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    species: Mapped[str] = mapped_column(String(100), default='Unknown animal')
    observed_at: Mapped[str] = mapped_column(String(40))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    share_location: Mapped[bool] = mapped_column(Boolean, default=False)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(24), default='draft', index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    request_hash: Mapped[str] = mapped_column(String(64), default='')
    __mapper_args__ = {'version_id_col': version}

class Evidence(Base):
    __tablename__ = 'evidence'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey('reports.id'), nullable=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    filename: Mapped[str] = mapped_column(String(100))
    content_type: Mapped[str] = mapped_column(String(30))
    size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Prediction(Base):
    __tablename__ = 'predictions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey('evidence.id'), index=True)
    state: Mapped[str] = mapped_column(String(24), default='queued')
    species: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    boxes: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(100), default='not-configured')
    explanation: Mapped[str] = mapped_column(Text, default='Awaiting image assistance.')
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Review(Base):
    __tablename__ = 'reviews'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey('reports.id'), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    decision: Mapped[str] = mapped_column(String(24))
    notes: Mapped[str] = mapped_column(Text)
    species: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class CaseEvent(Base):
    __tablename__ = 'case_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey('reports.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Advisory(Base):
    __tablename__ = 'advisories'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey('reports.id'), index=True)
    area_id: Mapped[str] = mapped_column(ForeignKey('areas.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    publisher_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    category: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(250))
    state: Mapped[str] = mapped_column(String(20), default='draft', index=True)
    expires_at: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retraction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}

class Receipt(Base):
    __tablename__ = 'receipts'
    __table_args__ = (UniqueConstraint('user_id', 'advisory_id', name='uq_receipt'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    advisory_id: Mapped[str] = mapped_column(ForeignKey('advisories.id'), index=True)
    read_at: Mapped[str] = mapped_column(String(40), default=now)

class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey('reports.id'), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now)

class Outbox(Base):
    __tablename__ = 'outbox'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(24))
    aggregate_id: Mapped[str] = mapped_column(String(36))
    dedupe_key: Mapped[str] = mapped_column(String(100), unique=True)
    state: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(80), default='')
    created_at: Mapped[str] = mapped_column(String(40), default=now)
