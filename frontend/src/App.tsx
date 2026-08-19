import { useEffect, useMemo, useState } from 'react'
import { Entity, fetchEntities, fetchSheet, fetchSheets, Layer, Sheet } from './api'

function Drawing({ sheet, entities }: { sheet: Sheet; entities: Entity[] }) {
  const [minX, minY, maxX, maxY] = sheet.bounding_box
  const width = Math.max(1, maxX - minX)
  const height = Math.max(1, maxY - minY)
  const flip = (y: number) => maxY - (y - minY)

  return (
    <svg className="drawing" viewBox={`${minX} ${minY} ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      <g className="cad-geometry">
        {entities.map((e, i) => {
          if (e.type === 'LINE') return <line key={i} x1={e.start[0]} y1={flip(e.start[1])} x2={e.end[0]} y2={flip(e.end[1])} stroke="currentColor" />
          if (e.type === 'LWPOLYLINE' || e.type === 'POLYLINE') {
            const points = (e.points || []).map((p: number[]) => `${p[0]},${flip(p[1])}`).join(' ')
            return e.closed ? <polygon key={i} points={points} fill="none" stroke="currentColor" /> : <polyline key={i} points={points} fill="none" stroke="currentColor" />
          }
          if (e.type === 'CIRCLE') return <circle key={i} cx={e.center[0]} cy={flip(e.center[1])} r={e.radius} fill="none" stroke="currentColor" />
          if ((e.type === 'TEXT' || e.type === 'MTEXT') && e.text) return <text key={i} x={e.insert[0]} y={flip(e.insert[1])} fontSize={Math.max(e.height || 120, 80)} fill="currentColor">{String(e.text).slice(0, 50)}</text>
          return null
        })}
      </g>
    </svg>
  )
}

export default function App() {
  const [sheets, setSheets] = useState<Sheet[]>([])
  const [selected, setSelected] = useState('J01')
  const [detail, setDetail] = useState<(Sheet & { layers: Layer[] }) | null>(null)
  const [enabledLayers, setEnabledLayers] = useState<string[]>([])
  const [entities, setEntities] = useState<Entity[]>([])
  const [message, setMessage] = useState('正在读取图纸目录…')

  useEffect(() => {
    fetchSheets().then(data => { setSheets(data); setMessage(`${data.length} 张图纸已识别`) }).catch(err => setMessage(err.message))
  }, [])

  useEffect(() => {
    setEntities([])
    fetchSheet(selected).then(data => {
      setDetail(data)
      setEnabledLayers(data.layers.map(layer => layer.name))
      if (!data.dxf_available) setMessage(`${selected} 已识别；请运行拆图脚本生成 DXF 后预览`)
    }).catch(err => setMessage(err.message))
  }, [selected])

  useEffect(() => {
    if (!detail?.dxf_available) return
    fetchEntities(selected, enabledLayers).then(data => {
      setEntities(data.entities)
      setMessage(`${selected} · ${data.entities.length.toLocaleString()} 个可视实体`)
    }).catch(err => setMessage(err.message))
  }, [detail?.dxf_available, selected, enabledLayers.join('|')])

  const current = useMemo(() => sheets.find(s => s.sheet_no === selected), [sheets, selected])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">DXF</span><div><strong>Sheet Explorer</strong><small>建筑施工图解析台</small></div></div>
        <div className="status"><span className="status-dot" />{message}</div>
        <nav className="sheet-list">
          {sheets.map(sheet => <button className={sheet.sheet_no === selected ? 'sheet active' : 'sheet'} key={sheet.sheet_no} onClick={() => setSelected(sheet.sheet_no)}><span>{sheet.sheet_no}</span><em>{sheet.sheet_name}</em><i>{sheet.source_entity_count}</i></button>)}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div><span className="eyebrow">CURRENT SHEET</span><h1>{current?.sheet_no} · {current?.sheet_name}</h1></div>
          <div className="metrics"><span>图号 <b>{current?.drawing_no}</b></span><span>比例 <b>{current?.ratio || '—'}</b></span><span>实体 <b>{current?.source_entity_count ?? 0}</b></span></div>
        </header>
        <section className="canvas-panel">
          <div className="canvas-toolbar"><span>MODEL SPACE</span><span>CAD 图元预览</span></div>
          <div className="cad-canvas">
            {current && entities.length > 0 ? <Drawing sheet={current} entities={entities} /> : <div className="empty-state"><div className="frame-icon" /><h2>{current?.sheet_no || 'DXF'}</h2><p>{detail?.dxf_available ? '正在生成预览…' : '图框和图签已识别。将拆分 DXF 放入 data/sheets 后即可在线渲染。'}</p></div>}
          </div>
        </section>
      </main>

      <aside className="inspector">
        <div className="panel-title"><span>LAYERS</span><b>{detail?.layers.length ?? 0}</b></div>
        <div className="layer-list">
          {(detail?.layers || []).map(layer => {
            const on = enabledLayers.includes(layer.name)
            return <label className="layer" key={layer.name}><input type="checkbox" checked={on} onChange={() => setEnabledLayers(prev => on ? prev.filter(x => x !== layer.name) : [...prev, layer.name])} /><span className="layer-eye">{on ? '●' : '○'}</span><em>{layer.name}</em><i>{layer.entity_count}</i></label>
          })}
          {!detail?.layers.length && <div className="layer-placeholder">拆图后自动读取图层</div>}
        </div>
        <div className="meta-card"><span>BOUNDING BOX</span><code>{current?.bounding_box?.join('\n') || '—'}</code></div>
      </aside>
    </div>
  )
}
