// Mirrors backend/askboard/models.py.

export const PG_TYPES = [
  'text',
  'bigint',
  'numeric',
  'boolean',
  'date',
  'timestamp',
  'timestamptz',
] as const
export type PgType = (typeof PG_TYPES)[number]

export type SemanticType =
  | 'id'
  | 'categorical'
  | 'numeric'
  | 'currency'
  | 'temporal'
  | 'boolean'
  | 'text'

export type DatasetStatus = 'pending' | 'loaded' | 'failed'

export interface Workspace {
  id: string
  name: string
  schema_name: string
  created_at: string
}

export interface ColumnInfo {
  position: number
  name: string
  original_name: string
  pg_type: PgType
  semantic_type: SemanticType
  sample_values: string[]
  null_ratio: number | null
  distinct_count: number | null
  min_value: string | null
  max_value: string | null
  is_unique: boolean
}

export interface LoadError {
  line: number
  column: string | null
  value: string | null
  message: string
}

export interface Dataset {
  id: string
  workspace_id: string
  table_name: string
  original_filename: string
  status: DatasetStatus
  row_count: number | null
  rejected_rows: number
  source_format: { encoding: string; delimiter: string }
  columns: ColumnInfo[]
  load_errors: LoadError[]
  created_at: string
}

export interface DatasetPreview extends Dataset {
  preview_rows: string[][]
}

export interface ColumnOverride {
  position: number
  name?: string
  pg_type?: PgType
}

export interface ConfirmRequest {
  table_name?: string
  columns?: ColumnOverride[]
}

export type ColumnKind = 'number' | 'text' | 'boolean' | 'date' | 'timestamp'
export type CellValue = string | number | boolean | null

export interface TablePanel {
  id: string
  type: 'table'
  title: string
  sql: string
  columns: { name: string; type: ColumnKind }[]
  rows: CellValue[][]
  truncated: boolean
}

export interface FailedStep {
  question: string
  sql: string | null
  error: string
}

export interface AskRecord {
  id: string
  created_at: string
  question: string
  title: string
  summary: string[]
  panels: TablePanel[]
  follow_ups: string[]
  failed_steps: FailedStep[]
  error: string | null
}
