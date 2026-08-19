import { useEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent, WheelEvent } from 'react'
import { Entity, fetchEntities, fetchSheet, fetchSheets, fetchSource, fetchSplitStatus, Layer, Sheet, SourceStatus, SplitStatus, startSplit, uploadSource } from './api'

type ViewBox = { x: number; y: number; w: number; h: number }

function arcPath(e: Entity, flip: (y: number) => number) {
  const [cx, cy0] = e.center
  const r = Number(e.radius)
  const start = Number(e.start_angle) * Math.PI / 180
  const end = Number(e.end_angle) * Math.PI / 180
  const sx = cx + r * Math.cos(start)
  const sy = flip(cy0 + r * Math.sin(start))
  const ex = cx + r * Math.cos(end)
  const ey = flip(cy0 + r * Math.sin(end))
  let delta = Number(e.end_angle) - Number(e.start_angle)
  if (delta < 0) delta += 360
  const large = delta > 180 ? 1 : 0
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey}`
}

function EntityShape({ e, flip, onPick, selected }: { e: Entity; flip: (y: number) => number; onPick: (e: Entity) => void; selected: boolean }) {
  const common = { className: selected ? 'entity selected-entity' : 'entity', onPointerDown: (ev: PointerEvent<SVGElement>) => { ev.stopPropagation(); onPick(e) } }
  if (e.type === 'LINE') return <line {...common} x1={e.start[0]} y1={flip(e.start[1])} x2={e.end[0]} y2={flip(e.end[1])} />
  if (e.type === 'LWPOLYLINE' || e.type === 'POLYLINE' || e.type === 'CURVE') {
    const points = (e.points || []).map((p: number[]) => `${p[0]},${flip(p[1])}`).join(' ')
    return e.closed ? <polygon {...common} points={points} /> : <polyline {...common} points={points} />
  }
  if (e.type === 'CIRCLE') return <circle {...common} cx={e.center[0]} cy={flip(e.center[1])} r={e.radius} />
  if (e.type === 'ARC') return <path {...common} d={arcPath(e, flip)} />
  if (e.type === 'SOLID') {
    const points = (e.points || []).map((p: number[]) => `${p[0]},${flip(p[1])}`).join(' ')
    return <polygon {...common} points={points} />
  }
  if (e.type === 'POINT') return <circle {...common} cx={e.point[0]} cy={flip(e.point[1])} r={18} />
  if ((e.type === 'TEXT' || e.type === 'MTEXT') && e.text) {
    return <text {...common} x={e.insert[0]} y={flip(e.insert[1])} fontSize={Math.max(e.height || 120, 70)} transform={`rotate(${-Number(e.rotation || 0)} ${e.insert[0]} ${flip(e.insert[1])})`}>{String(e.text).slice(0, 100)}</text>
  }
  if (e.type === 'INSERT') return <circle {...common} cx={e.insert[0]} cy={flip(e.insert[1])} r={24} />
  return null
}

function Drawing({ sheet, entities, selectedEntity, onPick }: { sheet: Sheet; entities: Entity[]; selectedEntity: Entity | null; onPick: (e: Entity | null) => void }) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [minX, minY, maxX, maxY] = sheet.bounding_box
  const base = useMemo<ViewBox>(() => ({ x: minX, y: minY, w: Math.max(1, maxX - minX), h: Math.max(1, maxY - minY) }), [minX, minY, maxX, maxY])
  const [view, setView] = useState<ViewBox>(base)
  const drag = useRef<{ x: number; y: number; view: ViewBox } | null>(null)
  const flip = (y: number) => maxY - (y - minY)

  useEffect(() => setView(base), [base.x, base.y, base.w, base.h])

  const zoom = (factor: number, clientX?: number, clientY?: number) => {
    const svg = svgRef.current
    let ax = view.x + view.w / 2
    let ay = view.y + view.h / 2
    if (svg && clientX != null && clientY != null) {
      const rect = svg.getBoundingClientRect()
      ax = view.x + ((clientX - rect.left) / rect.width) * view.w
      ay = view.y + ((clientY - rect.top) / rect.height) * view.h
    }
    const nw = view.w * factor
    const nh = view.h * factor
    setView({ x: ax - (ax - view.x) * factor, y: ay - (ay - view.y) * factor, w: nw, h: nh })
  }

  const wheel = (ev: WheelEvent<SVGSVGElement>) => {
    ev.preventDefault()
    zoom(ev.deltaY > 0 ? 1.14 : 0.88, ev.clientX, ev.clientY)
  }

  const pointerDown = (ev: PointerEvent<SVGSVGElement>) => {
    onPick(null)
    drag.current = { x: ev.clientX, y: ev.clientY, view: { ...view } }
    ev.currentTarget.setPointerCapture(ev.pointerId)
  }

  const pointerMove = (ev: PointerEvent<SVGSVGElement>) => {
    if (!drag.current || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const dx = (ev.clientX - drag.current.x) / rect.width * drag.current.view.w
    const dy = (ev.clientY - drag.current.y) / rect.height * drag.current.view.h
    setView({ ...drag.current.view, x: drag.current.view.x - dx, y: drag.current.view.y - dy })
  }

  const pointerUp = (ev: PointerEvent<SVGSVGElement>) => {
    drag.current = null
    try { ev.currentTarget.releasePointerCapture(ev.pointerId) } catch { /* noop */ }
  }

  const zoomPct = Math.round(base.w / view.w * 100)

  return (
    <div className="drawing-wrap">
      <div className="floating-tools">
        <button onClick={() => zoom(.8)} title="放大">＋</button>
        <span>{zoomPct}%</span>
        <button onClick={() => zoom(1.25)} title="缩小">−</button>
        <button onClick={() => setView(base)} title="适配窗口">FIT</button>
      </div>
      <svg ref={svgRef} className="drawing" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} preserveAspectRatio="xMidYMid meet" onWheel={wheel} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp}>
        <g className="cad-geometry">
          {entities.map((e, i) => <EntityShape key={`${e.handle || 'v'}-${i}`} e={e} flip={flip} onPick={onPick} selected={selectedEntity === e} />)}
        </g>
      </svg>
    </div>
  )
}

export default function App() {
  const [sheets, setSheets] = useState<Sheet[]>([])
  const [selected, setSelected] = useState('J01')
  const [detail, setDetail] = useState<(Sheet & { layers: Layer[] }) | null>(null)
  const [enabledLayers, setEnabledLayers] = useState<string[]>([])
  const [entities, setEntities] = useState<Entity[]>([])
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [message, setMessage] = useState('正在读取图纸目录…')
  const [source, setSource] = useState<SourceStatus>({ available: false, path: 'data/source/original.dxf' })
  const [split, setSplit] = useState<SplitStatus>({ state: 'idle', processed: 0, total: 26 })
  const [uploading, setUploading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    fetchSource().then(setSource).catch(() => undefined)
    fetchSplitStatus().then(setSplit).catch(() => undefined)
    fetchSheets().then(data => { setSheets(data); setMessage(`${data.length} 张图纸已识别`) }).catch(err => setMessage(err.message))
  }, [refreshKey])

  useEffect(() => {
    setEntities([])
    setSelectedEntity(null)
    fetchSheet(selected).then(data => {
      setDetail(data)
      setEnabledLayers(data.layers.map(layer => layer.name))
      if (!data.dxf_available) setMessage(`${selected} 已识别；运行拆图脚本后即可在线预览`)
    }).catch(err => setMessage(err.message))
  }, [selected, refreshKey])

  useEffect(() => {
    if (!detail?.dxf_available) return
    setMessage(`${selected} 正在解析 CAD 实体…`)
    fetchEntities(selected).then(data => {
      setEntities(data.entities)
      setMessage(`${selected} · ${data.returned.toLocaleString()} 个可视实体${data.truncated ? '（已截断）' : ''}`)
    }).catch(err => setMessage(err.message))
  }, [detail?.dxf_available, selected])

  const onUpload = async (file?: File) => {
    if (!file) return
    setUploading(true)
    setMessage(`正在上传 ${file.name}…`)
    try {
      const status = await uploadSource(file)
      setSource(status)
      setMessage(`DXF 已上传 · ${(Number(status.size_bytes || 0) / 1024 / 1024).toFixed(1)} MB`)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    } finally {
      setUploading(false)
    }
  }

  const onSplit = async () => {
    try {
      const initial = await startSplit()
      setSplit(initial)
      setMessage('开始识别图框并拆分图纸…')
      const timer = window.setInterval(async () => {
        try {
          const status = await fetchSplitStatus()
          setSplit(status)
          if (status.state === 'running' || status.state === 'queued') {
            setMessage(`拆图进度 ${status.processed}/${status.total}${status.current_sheet ? ` · ${status.current_sheet}` : ''}`)
          }
          if (status.state === 'completed') {
            window.clearInterval(timer)
            setMessage(`拆分完成 · ${status.result?.drawing_count || status.processed} 张图纸`)
            setRefreshKey(v => v + 1)
          }
          if (status.state === 'failed') {
            window.clearInterval(timer)
            setMessage(`拆图失败：${status.error || 'unknown error'}`)
          }
        } catch (err) {
          window.clearInterval(timer)
          setMessage(err instanceof Error ? err.message : String(err))
        }
      }, 1500)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    }
  }

  const current = useMemo(() => sheets.find(s => s.sheet_no === selected), [sheets, selected])
  const visibleEntities = useMemo(() => entities.filter(e => enabledLayers.includes(e.layer)), [entities, enabledLayers])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">DXF</span><div><strong>Sheet Explorer</strong><small>建筑施工图解析台</small></div></div>
        <div className="status"><span className="status-dot" />{message}</div>
        <section className="source-box">
          <div className="source-head"><span>SOURCE DXF</span><b className={source.available ? 'ok' : ''}>{source.available ? 'READY' : 'MISSING'}</b></div>
          <label className="upload-button">
            <input type="file" accept=".dxf" disabled={uploading || split.state === 'running' || split.state === 'queued'} onChange={e => onUpload(e.target.files?.[0])} />
            {uploading ? '上传中…' : '选择并上传 DXF'}
          </label>
          <button className="split-button" disabled={!source.available || split.state === 'running' || split.state === 'queued'} onClick={onSplit}>
            {split.state === 'running' || split.state === 'queued' ? `拆分 ${split.processed}/${split.total}` : '识别图框并拆分'}
          </button>
          {source.sha256 && <code className="source-hash">SHA {source.sha256.slice(0, 12)}…</code>}
        </section>
        <nav className="sheet-list">
          {sheets.map(sheet => <button className={sheet.sheet_no === selected ? 'sheet active' : 'sheet'} key={sheet.sheet_no} onClick={() => setSelected(sheet.sheet_no)}><span>{sheet.sheet_no}</span><em>{sheet.sheet_name}</em><i>{sheet.source_entity_count}</i></button>)}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">CURRENT SHEET</span><h1>{current?.sheet_no} · {current?.sheet_name}</h1></div>
          <div className="metrics"><span>图号 <b>{current?.drawing_no}</b></span><span>比例 <b>{current?.ratio || '—'}</b></span><span>实体 <b>{visibleEntities.length.toLocaleString()}</b></span></div>
        </header>
        <section className="canvas-panel">
          <div className="canvas-toolbar"><span>MODEL SPACE</span><span>滚轮缩放 · 左键拖拽平移 · 点击实体查看属性</span></div>
          <div className="cad-canvas">
            {current && entities.length > 0 ? <Drawing sheet={current} entities={visibleEntities} selectedEntity={selectedEntity} onPick={setSelectedEntity} /> : <div className="empty-state"><div className="frame-icon" /><h2>{current?.sheet_no || 'DXF'}</h2><p>{detail?.dxf_available ? '正在解析并生成预览…' : '图框和图签已识别。将拆分 DXF 放入 data/sheets 后即可在线渲染。'}</p></div>}
          </div>
        </section>
      </main>

      <aside className="inspector">
        <div className="panel-title"><span>LAYERS</span><b>{detail?.layers.length ?? 0}</b></div>
        <div className="layer-actions"><button onClick={() => setEnabledLayers((detail?.layers || []).map(l => l.name))}>全部</button><button onClick={() => setEnabledLayers([])}>清空</button></div>
        <div className="layer-list">
          {(detail?.layers || []).map(layer => {
            const on = enabledLayers.includes(layer.name)
            return <label className="layer" key={layer.name}><input type="checkbox" checked={on} onChange={() => setEnabledLayers(prev => on ? prev.filter(x => x !== layer.name) : [...prev, layer.name])} /><span className="layer-eye">{on ? '●' : '○'}</span><em>{layer.name}</em><i>{layer.entity_count}</i></label>
          })}
          {!detail?.layers.length && <div className="layer-placeholder">拆图后自动读取图层</div>}
        </div>
        {selectedEntity ? <div className="meta-card entity-card"><span>ENTITY</span><strong>{selectedEntity.type}</strong><code>{JSON.stringify(selectedEntity, null, 2)}</code></div> : <div className="meta-card"><span>BOUNDING BOX</span><code>{current?.bounding_box?.join('\n') || '—'}</code></div>}
      </aside>
    </div>
  )
}
