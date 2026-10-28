"""Feature-owned contracts for Feature A (Curriculum and Resources).

These contracts define the domain types for:
- Learning projects (organizational containers)
- Uploaded resources and lifecycle processing states
- Source chunks and page/section locators
- Study scope selections and free-text requests
- Retrieval diagnostics

Reuses shared contracts and preserves ResourceMatch exactly as defined in app.contracts.domain.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Re-export shared contracts to preserve exact external integration
from app.contracts.domain import Contract, ResourceMatch, CurriculumSnapshot


class ResourceProcessingStatus(str, Enum):
    """Actual runtime processing states for uploaded resources.

    No fake percentages or speculative states.
    """
    received = "received"
    extracting = "extracting"
    extracted = "extracted"
    embedding = "embedding"
    indexed = "indexed"
    failed = "failed"
    archived = "archived"


class ProjectCreate(Contract):
    """Request payload to create a learning project container."""
    title: str = Field(min_length=1, max_length=120, description="Project title")
    curriculum_id: str = Field(min_length=1, description="Associated curriculum ID")
    description: str | None = Field(default=None, max_length=1000, description="Optional project description")

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Project title cannot be blank or whitespace only")
        return s


class ProjectPublic(Contract):
    """Public representation of an owned learning project."""
    project_id: str
    student_id: str
    curriculum_id: str
    title: str
    description: str | None = None
    created_at: str
    updated_at: str
    resource_count: int = Field(default=0, ge=0)


class SourceChunk(Contract):
    """Granular retrieval unit within a resource, preserving provenance."""
    chunk_id: str
    resource_id: str
    text: str = Field(min_length=1)
    source_label: str
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    sequence: int = Field(default=1, ge=1)
    token_estimate: int = Field(default=0, ge=0)


class UploadedResourceDetail(Contract):
    """Detailed metadata and chunks for an uploaded or authored resource."""
    resource_id: str
    project_id: str
    curriculum_id: str
    topic_id: str
    title: str
    source_label: str
    original_filename: str
    mime_type: str
    byte_size: int = Field(ge=0)
    content_hash: str
    processing_status: ResourceProcessingStatus
    error_message: str | None = None
    chunks: list[SourceChunk] = Field(default_factory=list)
    created_at: str


class ResourcePreview(Contract):
    """Compact summary of a resource for lists and previews."""
    resource_id: str
    project_id: str | None = None
    curriculum_id: str
    topic_id: str
    title: str
    source_label: str
    snippet: str
    chunk_count: int = Field(default=0, ge=0)
    processing_status: ResourceProcessingStatus
    byte_size: int = Field(default=0, ge=0)


class StudyScopeSave(Contract):
    """Student study scope selection linking topics, resources, and free-text queries."""
    selected_topic_ids: list[str] = Field(min_length=1, description="At least one target topic is required")
    selected_resource_ids: list[str] = Field(default_factory=list, description="Optional specific resources chosen")
    free_text_request: str | None = Field(default=None, max_length=1000, description="Optional raw study inquiry")

    @field_validator("selected_topic_ids")
    @classmethod
    def unique_topics(cls, topics: list[str]) -> list[str]:
        if len(set(topics)) != len(topics):
            raise ValueError("Selected topics must be unique")
        return topics


class StudyScopeSelection(Contract):
    """Saved, confirmed study scope ready to hand over to Person 3 (Planning)."""
    selection_id: str
    project_id: str
    student_id: str
    selected_topic_ids: list[str]
    selected_resource_ids: list[str]
    free_text_request: str | None = None
    unresolved_queries: list[str] = Field(default_factory=list, description="Queries not matched to known curriculum")
    confirmed_at: str


class RetrievalDiagnostics(Contract):
    """Diagnostic details for semantic retrieval operations."""
    query_text: str
    topic_id: str
    candidates_evaluated: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    fallback_used: bool
    model_fingerprint: str | None = None
    top_scores: list[float] = Field(default_factory=list)
