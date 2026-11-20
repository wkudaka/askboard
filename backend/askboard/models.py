"""Domain models shared by services and the HTTP API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

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
