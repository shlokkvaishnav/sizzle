import { useEffect, useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { getOpsTablesFiltered, previewTableMerge, updateTableStatus } from '../api/client'

const statusStyles = {
  empty: { color: '#2A7A50', bg: 'var(--success-subtle)', label: 'Available' },
  occupied: { color: '#C07A20', bg: 'var(--warning-subtle)', label: 'Occupied' },
  reserved: { color: '#2A5A8C', bg: 'var(--info-subtle)', label: 'Reserved' },
  cleaning: { color: '#7A7A84', bg: 'rgba(122, 122, 132, 0.15)', label: 'Needs Cleaning' },
}

function formatOrderRef(table) {
  if (!table.current_order_id) return 'N/A'
  const compact = String(table.current_order_id).replace(/-/g, '').toUpperCase()
  return `#${compact.slice(0, 8)}`
}

function formatSeatedTime(table) {
  const value = table.seated_at || table.updated_at || table.created_at
  if (!value || table.status === 'empty') return 'Not seated'
  const dt = new Date(value)
  if (Number.isNaN(dt.valueOf())) return 'Unknown'
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function Tables() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')
  const [section, setSection] = useState('')
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState('floor')
  const [selectedTableId, setSelectedTableId] = useState(null)
  const [orderInputs, setOrderInputs] = useState({})
  const [mergeSelection, setMergeSelection] = useState([])
  const [mergeNote, setMergeNote] = useState('')
  const [error, setError] = useState('')

  const params = useMemo(
    () => ({
      status: status || undefined,
      section: section || undefined,
      search: search || undefined,
    }),
    [status, section, search],
  )

  useEffect(() => {
    setLoading(true)
    getOpsTablesFiltered(params)
      .then(setData)
      .finally(() => setLoading(false))
  }, [params])

  const refreshTables = () => getOpsTablesFiltered(params).then(setData)

  const handleStatusUpdate = async (table, nextStatus, nextOrderId = table.current_order_id || null) => {
    await updateTableStatus(table.table_id, {
      status: nextStatus,
      current_order_id: nextStatus === 'empty' ? null : nextOrderId,
    })
    await refreshTables()
  }

  const toggleMerge = (tableId) => {
    setMergeSelection((prev) => {
      if (prev.includes(tableId)) return prev.filter((id) => id !== tableId)
      if (prev.length >= 2) return [prev[1], tableId]
      return [...prev, tableId]
    })
  }

  const applyMerge = async () => {
    if (mergeSelection.length < 2) return
    setError('')
    try {
      const preview = await previewTableMerge(mergeSelection)
      setMergeNote(
        `Merge ready for tables ${preview.table_numbers.join(' + ')} (capacity ${preview.combined_capacity}). Token: ${preview.merge_token}`,
      )
      setMergeSelection([])
    } catch (err) {
      setError(err?.detail || err?.message || 'Merge preview failed')
    }
  }

  if (loading) return <div className="loading">Loading tables...</div>
  if (!data) return <div className="loading">Failed to load tables.</div>

  const { summary, tables } = data
  const hasTables = tables.length > 0
  const selectedTable = tables.find((table) => table.table_id === selectedTableId) || null
  const sectionOptions = Array.from(new Set(tables.map((table) => table.section).filter(Boolean)))

  return (
    <div className="app-page">
      <div className="app-hero">
        <div>
          <div className="app-hero-eyebrow">Operations</div>
          <h1 className="app-hero-title">Tables</h1>
          <p className="app-hero-sub">Visual floor plan and live table management.</p>
        </div>
        <div className="app-hero-metrics">
          <div className="app-kpi">
            <div className="app-kpi-label">Total Tables</div>
            <div className="app-kpi-value">{summary.total_tables}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label">Occupied</div>
            <div className="app-kpi-value">{summary.occupied}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label">Reserved</div>
            <div className="app-kpi-value">{summary.reserved}</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">Floor Controls</div>
        <div className="card-body">
          <div className="tables-toolbar">
            <div className="filters-row tables-filters-row">
              <input
                className="input"
                placeholder="Search table number"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All Statuses</option>
                <option value="empty">Available</option>
                <option value="occupied">Occupied</option>
                <option value="reserved">Reserved</option>
                <option value="cleaning">Needs Cleaning</option>
              </select>
              <select className="input" value={section} onChange={(e) => setSection(e.target.value)}>
                <option value="">All Sections</option>
                {sectionOptions.map((sectionName) => (
                  <option key={sectionName} value={sectionName}>
                    {sectionName}
                  </option>
                ))}
              </select>
            </div>
            <div className="tables-view-toggle">
              <button
                className={`btn ${viewMode === 'floor' ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setViewMode('floor')}
              >
                Floor Plan
              </button>
              <button
                className={`btn ${viewMode === 'list' ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setViewMode('list')}
              >
                List View
              </button>
            </div>
          </div>
        </div>
      </div>

      {mergeNote ? (
        <div className="tables-merge-note">
          <span>{mergeNote}</span>
          <button className="btn btn-ghost" onClick={() => setMergeNote('')}>Dismiss</button>
        </div>
      ) : null}

      {error ? (
        <div className="card">
          <div className="card-body" style={{ color: 'var(--danger)', fontSize: 12 }}>{error}</div>
        </div>
      ) : null}

      {!hasTables ? (
        <div className="card">
          <div className="card-body">
            <div className="tables-empty-state">
              <div className="tables-empty-icon">🪑</div>
              <h3>No tables configured</h3>
              <p>Add tables in setup to start managing occupancy and reservations.</p>
            </div>
          </div>
        </div>
      ) : viewMode === 'floor' ? (
        <>
          <div className="tables-floor-grid">
            {tables.map((table) => {
              const style = statusStyles[table.status] || statusStyles.empty
              const isMergeSelected = mergeSelection.includes(table.table_id)
              return (
                <motion.button
                  type="button"
                  key={table.table_id}
                  className={`tables-floor-card ${selectedTableId === table.table_id ? 'tables-floor-card--active' : ''}`}
                  style={{ '--table-accent': style.color }}
                  onClick={() => setSelectedTableId(table.table_id)}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <div className="tables-floor-card-head">
                    <strong>Table {table.table_number}</strong>
                    <span className="status-pill" style={{ color: style.color, borderColor: style.color, background: style.bg }}>
                      {style.label}
                    </span>
                  </div>
                  <div className="tables-floor-card-meta">
                    <span>{table.capacity}-seater</span>
                    <span>{table.section || 'Main Hall'}</span>
                  </div>
                  <div className="tables-floor-card-meta">
                    <span>Order: {formatOrderRef(table)}</span>
                    <span>Seated: {formatSeatedTime(table)}</span>
                  </div>
                  <div className="tables-floor-card-actions" onClick={(event) => event.stopPropagation()}>
                    <button className="btn btn-ghost" onClick={() => handleStatusUpdate(table, 'cleaning')}>Mark Dirty</button>
                    <button className="btn btn-ghost" onClick={() => handleStatusUpdate(table, 'empty')}>Mark Available</button>
                  </div>
                  <label className="tables-merge-check" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isMergeSelected}
                      onChange={() => toggleMerge(table.table_id)}
                    />
                    Merge select
                  </label>
                </motion.button>
              )
            })}
          </div>
          <div className="tables-merge-bar">
            <div>
              <strong>Merge tables</strong>
              <p>Select two tables to mark a merged seating group.</p>
            </div>
            <button className="btn btn-primary" onClick={applyMerge} disabled={mergeSelection.length < 2}>
              Merge Selected ({mergeSelection.length}/2)
            </button>
          </div>
        </>
      ) : (
        <div className="card">
          <div className="card-header">Table List</div>
          <div className="card-body" style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Section</th>
                  <th>Capacity</th>
                  <th>Status</th>
                  <th>Current Order</th>
                  <th>Time Seated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tables.map((table) => {
                  const style = statusStyles[table.status] || statusStyles.empty
                  return (
                    <tr key={table.table_id}>
                      <td style={{ fontWeight: 700 }}>Table {table.table_number}</td>
                      <td>{table.section || 'Main Hall'}</td>
                      <td>{table.capacity}</td>
                      <td>
                        <span className="status-pill" style={{ color: style.color, borderColor: style.color, background: style.bg }}>
                          {style.label}
                        </span>
                      </td>
                      <td>{formatOrderRef(table)}</td>
                      <td>{formatSeatedTime(table)}</td>
                      <td>
                        <div className="orders-row-actions">
                          <button className="btn btn-ghost" onClick={() => setSelectedTableId(table.table_id)}>View</button>
                          <button className="btn btn-ghost" onClick={() => handleStatusUpdate(table, 'occupied')}>Occupied</button>
                          <button className="btn btn-ghost" onClick={() => handleStatusUpdate(table, 'empty')}>Clear</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedTable ? (
        <div className="tables-drawer-backdrop" onClick={() => setSelectedTableId(null)}>
          <aside className="tables-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="tables-drawer-head">
              <div>
                <h3>Table {selectedTable.table_number}</h3>
                <p>{selectedTable.section || 'Main Hall'} section</p>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedTableId(null)}>Close</button>
            </div>
            <div className="tables-drawer-meta">
              <div><span>Capacity</span><strong>{selectedTable.capacity} seats</strong></div>
              <div><span>Status</span><strong>{(statusStyles[selectedTable.status] || statusStyles.empty).label}</strong></div>
              <div><span>Current Order</span><strong>{formatOrderRef(selectedTable)}</strong></div>
            </div>
            <div className="tables-drawer-actions">
              <button className="btn btn-ghost" onClick={() => handleStatusUpdate(selectedTable, 'reserved')}>Reserve</button>
              <button className="btn btn-ghost" onClick={() => handleStatusUpdate(selectedTable, 'occupied')}>Mark Occupied</button>
              <button className="btn btn-ghost" onClick={() => handleStatusUpdate(selectedTable, 'cleaning')}>Mark Dirty</button>
              <button className="btn btn-primary" onClick={() => handleStatusUpdate(selectedTable, 'empty')}>Mark Available</button>
            </div>
            <div className="table-order-edit">
              <input
                className="input"
                placeholder="Attach order ID"
                value={orderInputs[selectedTable.table_id] || ''}
                onChange={(e) => setOrderInputs((prev) => ({ ...prev, [selectedTable.table_id]: e.target.value }))}
              />
              <button
                className="btn btn-primary"
                onClick={() =>
                  handleStatusUpdate(
                    selectedTable,
                    selectedTable.status,
                    orderInputs[selectedTable.table_id] || null,
                  )
                }
              >
                Save
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  )
}
