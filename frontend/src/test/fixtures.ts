import type { AskRecord, ColumnInfo, Conversation, Dataset, DatasetPreview, Workspace } from '../api/types'

export const answer: AskRecord = {
  id: 'q-1',
  conversation_id: 'c-1',
  created_at: '2026-11-20T11:00:00Z',
  question: 'Quanto cada cliente gastou?',
  title: 'Receita por cliente',
  summary: ['Ana concentra 99% da receita', 'Carla não tem valor registrado'],
  panels: [
    {
      id: 'p1',
      type: 'table',
      title: 'Quanto cada cliente gastou?',
      sql: 'SELECT cliente, sum(valor_total) AS total FROM pedidos GROUP BY cliente',
      columns: [
        { name: 'cliente', type: 'text' },
        { name: 'total', type: 'number' },
      ],
      rows: [
        ['Ana', 1341.71],
        ['Bruno', 10],
        ['Carla', null],
      ],
      truncated: false,
      encoding: { x: 'cliente', y: ['total'], series: null },
      alternatives: [],
      formats: { total: 'number' },
    },
  ],
  follow_ups: ['E por mês?'],
  failed_steps: [],
  currency: null,
  error: null,
}

export const conversation: Conversation = {
  id: 'c-1',
  workspace_id: 'ws-1',
  title: 'Quanto cada cliente gastou?',
  created_at: '2026-11-20T11:00:00Z',
  updated_at: '2026-11-20T11:00:00Z',
}

export const workspace: Workspace = {
  id: 'ws-1',
  name: 'Sales',
  schema_name: 'ws_abc',
  created_at: '2026-11-20T10:00:00Z',
}

function column(partial: Partial<ColumnInfo> & Pick<ColumnInfo, 'position' | 'name'>): ColumnInfo {
  return {
    original_name: partial.name,
    pg_type: 'text',
    semantic_type: 'text',
    sample_values: [],
    null_ratio: null,
    distinct_count: null,
    min_value: null,
    max_value: null,
    is_unique: false,
    ...partial,
  }
}

export const preview: DatasetPreview = {
  id: 'ds-1',
  workspace_id: 'ws-1',
  table_name: 'pedidos',
  original_filename: 'pedidos.csv',
  status: 'pending',
  row_count: 5,
  rejected_rows: 1,
  source_format: { encoding: 'cp1252', delimiter: ';' },
  columns: [
    column({ position: 1, name: 'id', original_name: 'ID', pg_type: 'bigint', semantic_type: 'id', sample_values: ['1', '2'] }),
    column({ position: 2, name: 'cliente', original_name: 'Cliente', semantic_type: 'categorical', sample_values: ['Ana', 'Bruno'] }),
    column({ position: 3, name: 'valor_total', original_name: 'Valor Total', pg_type: 'numeric', semantic_type: 'currency', sample_values: ['R$ 1.234,56'] }),
    column({ position: 4, name: 'data_do_pedido', original_name: 'Data do Pedido', pg_type: 'date', semantic_type: 'temporal', sample_values: ['15/01/2024'] }),
  ],
  load_errors: [{ line: 6, column: null, value: null, message: 'Row has a different number of columns than the header' }],
  created_at: '2026-11-20T10:01:00Z',
  preview_rows: [
    ['1', 'Ana', 'R$ 1.234,56', '15/01/2024'],
    ['2', 'Bruno', 'R$ 10,00', '03/02/2024'],
  ],
}

export const loaded: Dataset = {
  ...preview,
  status: 'loaded',
  row_count: 4,
  rejected_rows: 2,
  load_errors: [
    { line: 6, column: null, value: null, message: 'Row has a different number of columns than the header' },
    { line: 4, column: 'id', value: 'A3', message: "Not a number: 'A3'" },
  ],
}
