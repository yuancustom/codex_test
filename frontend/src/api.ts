export type Sheet = {
  sheet_no: string
  sheet_name: string
  drawing_no: string
  ratio: string
  bounding_box: [number, number, number, number]
  source_entity_count: number
  output_file: string
  dxf_available: boolean
}

export type Layer = { name: string; entity_count: number }
export type Entity = Record<string, any> & { type: string; layer: string; handle?: string | null }
export type SourceStatus = { available: boolean; path: string; size_bytes?: number; sha256?: string; dxf_version?: string }
export type SplitStatus = {
  state: 'idle' | 'queued' | 'running' | 'completed' | 'failed'
  processed: number
  total: number
  current_sheet?: string | null
  error?: string | null
  result?: { drawing_count: number; standard_frame_count: number; directory_count: number; unassigned_modelspace_entities: number } | null
}

async function checked(res: Response) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchSource(): Promise<SourceStatus> {
  return checked(await fetch('/api/source'))
}

export async function uploadSource(file: File): Promise<SourceStatus> {
  const body = new FormData()
  body.append('file', file)
  return checked(await fetch('/api/source/upload', { method: 'POST', body }))
}

export async function startSplit(): Promise<SplitStatus> {
  return checked(await fetch('/api/source/split', { method: 'POST' }))
}

export async function fetchSplitStatus(): Promise<SplitStatus> {
  return checked(await fetch('/api/source/split-status'))
}

export async function fetchSheets(): Promise<Sheet[]> {
  const body = await checked(await fetch('/api/sheets'))
  return body.sheets
}

export async function fetchSheet(no: string): Promise<Sheet & { layers: Layer[] }> {
  return checked(await fetch(`/api/sheets/${no}`))
}

export async function fetchEntities(no: string): Promise<{ bounding_box: number[]; entities: Entity[]; returned: number; truncated: boolean }> {
  return checked(await fetch(`/api/sheets/${no}/entities?limit=50000&expand_blocks=true`))
}
