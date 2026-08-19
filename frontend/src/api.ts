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
export type Entity = Record<string, any> & { type: string; layer: string }

export async function fetchSheets(): Promise<Sheet[]> {
  const res = await fetch('/api/sheets')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()).sheets
}

export async function fetchSheet(no: string): Promise<Sheet & { layers: Layer[] }> {
  const res = await fetch(`/api/sheets/${no}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchEntities(no: string, layers: string[]): Promise<{ bounding_box: number[]; entities: Entity[] }> {
  const qs = new URLSearchParams()
  layers.forEach(layer => qs.append('layer', layer))
  const res = await fetch(`/api/sheets/${no}/entities?${qs.toString()}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
