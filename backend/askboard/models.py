"""Domain models shared by services and the HTTP API."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from askboard.ingestion.types import PgType

SemanticType = Literal["id", "categorical", "numeric", "currency", "temporal", "boolean", "text"]
DatasetStatus = Literal["pending", "loaded", "failed"]


class Workspace(BaseModel):
    id: UUID
    name: str
    schema_name: str
    created_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SourceFormat(BaseModel):
    encoding: str
    delimiter: str


class ColumnInfo(BaseModel):
    position: int  # 1-based, matches the CSV column order
    name: str
    original_name: str
    pg_type: PgType
    semantic_type: SemanticType
    sample_values: list[str] = []
    null_ratio: float | None = None
    distinct_count: int | None = None
    min_value: str | None = None
    max_value: str | None = None
    is_unique: bool = False


class LoadError(BaseModel):
    line: int  # 1-based line in the source file
    column: str | None = None  # None when the whole row was unusable
    value: str | None = None
    message: str


class Dataset(BaseModel):
    id: UUID
    workspace_id: UUID
    table_name: str
    original_filename: str
    status: DatasetStatus
    row_count: int | None
    rejected_rows: int
    source_format: SourceFormat
    columns: list[ColumnInfo]
    load_errors: list[LoadError]
    created_at: datetime


class DatasetPreview(Dataset):
    preview_rows: list[list[str]]


class ColumnOverride(BaseModel):
    position: int
    name: str | None = None
    pg_type: PgType | None = None


class ConfirmRequest(BaseModel):
    table_name: str | None = None
    columns: list[ColumnOverride] = []


# --- ask -------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be blank")
        return value


class PanelColumn(BaseModel):
    name: str
    type: Literal["number", "text", "boolean", "date", "timestamp"]


PanelType = Literal["kpi", "bar", "line", "pie", "stacked_bar", "scatter", "table"]
ValueFormat = Literal["number", "integer", "currency", "percent"]


class Encoding(BaseModel):
    x: str | None = None
    y: list[str] = []
    series: str | None = None


class Panel(BaseModel):
    id: str
    type: PanelType = "table"
    title: str
    sql: str
    columns: list[PanelColumn]
    rows: list[list[Any]]
    truncated: bool = False
    encoding: Encoding = Encoding()
    alternatives: list[PanelType] = []
    formats: dict[str, ValueFormat] = {}


class FailedStep(BaseModel):
    question: str
    sql: str | None = None
    error: str


class AskResult(BaseModel):
    question: str
    title: str
    summary: list[str] = []
    panels: list[Panel] = []
    follow_ups: list[str] = []
    failed_steps: list[FailedStep] = []
    currency: str | None = None  # ISO 4217 code for 'currency' formats, when known
    error: str | None = None


class AskRecord(AskResult):
    id: UUID
    created_at: datetime


# --- relationships ----------------------------------------------------------------

RelationshipStatus = Literal["suggested", "confirmed", "rejected"]


class Relationship(BaseModel):
    id: UUID
    workspace_id: UUID
    from_dataset_id: UUID
    from_table: str
    from_column: str
    to_dataset_id: UUID
    to_table: str
    to_column: str
    confidence: float
    status: RelationshipStatus


class RelationshipUpdate(BaseModel):
    status: RelationshipStatus
