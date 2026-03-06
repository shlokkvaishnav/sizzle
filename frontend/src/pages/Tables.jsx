import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  getOpsTablesFiltered,
  bookTable,
  settleTable,
  reserveTable,
  unreserveTable,
  seatReservedTable,
  getMenuItemsList,
  addItemToTableOrder,
} from '../api/client'
import { motion, AnimatePresence } from 'motion/react'

/* ── Color mapping for table statuses ── */
const STATUS_CONFIG = {
  empty: {
    label: 'Available',
    color: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.08)',
    border: 'rgba(34, 197, 94, 0.25)',
    glow: 'rgba(34, 197, 94, 0.12)',
  },
  reserved: {
    label: 'Reserved',
    color: '#3b82f6',
    bg: 'rgba(59, 130, 246, 0.08)',
    border: 'rgba(59, 130, 246, 0.25)',
    glow: 'rgba(59, 130, 246, 0.12)',
  },
  occupied: {
    label: 'Occupied',
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.08)',
    border: 'rgba(239, 68, 68, 0.25)',
    glow: 'rgba(239, 68, 68, 0.12)',
  },
  cleaning: {
    label: 'Cleaning',
    color: '#a78bfa',
    bg: 'rgba(167, 139, 250, 0.08)',
    border: 'rgba(167, 139, 250, 0.25)',
    glow: 'rgba(167, 139, 250, 0.12)',
  },
}

/* ── Settle Bill Modal ── */
function SettleModal({ table, onClose, onSettle }) {
  const [method, setMethod] = useState('cash')
  const [settling, setSettling] = useState(false)

  const handleSettle = async () => {
    setSettling(true)
    try {
      await onSettle(table.table_id, method)
      onClose()
    } catch (err) {
      console.error(err)
    } finally {
      setSettling(false)
    }
  }

  const order = table.order
  const items = order?.items || []

  return (
    <div className="tbl-modal-overlay" onClick={onClose}>
      <motion.div
        className="tbl-modal"
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="tbl-modal-header">
          <h3>Settle Bill — Table {table.table_number}</h3>
          <button className="tbl-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="tbl-modal-body">
          {items.length > 0 ? (
            <div className="tbl-bill-items">
              <div className="tbl-bill-row tbl-bill-head">
                <span>Item</span>
                <span>Qty</span>
                <span>Price</span>
                <span>Total</span>
              </div>
              {items.map((item, i) => (
                <div className="tbl-bill-row" key={i}>
                  <span>{item.name}</span>
                  <span>{item.quantity}</span>
                  <span>₹{item.unit_price?.toFixed(0)}</span>
                  <span>₹{item.line_total?.toFixed(0)}</span>
                </div>
              ))}
              <div className="tbl-bill-row tbl-bill-total">
                <span>Total</span>
                <span></span>
                <span></span>
                <span>₹{order?.total_amount?.toFixed(0) || '0'}</span>
              </div>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: 'var(--space-6)' }}>
              No items on this order yet.
            </p>
          )}

          <div className="tbl-payment-methods">
            <label className="tbl-payment-label">Payment Method</label>
            <div className="tbl-payment-options">
              {['cash', 'card', 'upi'].map((m) => (
                <button
                  key={m}
                  className={`tbl-payment-btn ${method === m ? 'active' : ''}`}
                  onClick={() => setMethod(m)}
                >
                  {m === 'cash' ? '💵' : m === 'card' ? '💳' : '📱'} {m.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="tbl-modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={settling}>Cancel</button>
          <button
            className="tbl-settle-confirm-btn"
            onClick={handleSettle}
            disabled={settling}
          >
            {settling ? 'Processing...' : `Settle ₹${order?.total_amount?.toFixed(0) || '0'}`}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

/* ── Add Item Modal ── */
function AddItemModal({ table, onClose, onItemAdded }) {
  const [menuItems, setMenuItems] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(null)

  useEffect(() => {
    setLoading(true)
    getMenuItemsList(search)
      .then((d) => setMenuItems(d.items || []))
      .finally(() => setLoading(false))
  }, [search])

  const handleAdd = async (itemId) => {
    setAdding(itemId)
    try {
      await addItemToTableOrder(table.table_id, itemId, 1)
      onItemAdded()
    } catch (err) {
      console.error(err)
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className="tbl-modal-overlay" onClick={onClose}>
      <motion.div
        className="tbl-modal tbl-modal-lg"
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.2 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="tbl-modal-header">
          <h3>Add Items — Table {table.table_number}</h3>
          <button className="tbl-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="tbl-modal-body">
          <input
            className="input"
            placeholder="Search menu items..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ marginBottom: 'var(--space-4)' }}
            autoFocus
          />
          {loading ? (
            <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--text-muted)' }}>Loading...</div>
          ) : menuItems.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--text-muted)' }}>No items found.</div>
          ) : (
            <div className="tbl-menu-grid">
              {menuItems.map((item) => (
                <div key={item.id} className="tbl-menu-item">
                  <div className="tbl-menu-item-info">
                    <span className={`tbl-veg-dot ${item.is_veg ? 'veg' : 'non-veg'}`} />
                    <div>
                      <div className="tbl-menu-item-name">{item.name}</div>
                      <div className="tbl-menu-item-cat">{item.category}</div>
                    </div>
                  </div>
                  <div className="tbl-menu-item-right">
                    <span className="tbl-menu-item-price">₹{item.price?.toFixed(0)}</span>
                    <button
                      className="tbl-add-btn"
                      onClick={() => handleAdd(item.id)}
                      disabled={adding === item.id}
                    >
                      {adding === item.id ? '...' : '+'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="tbl-modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Done</button>
        </div>
      </motion.div>
    </div>
  )
}

/* ── Main Tables Component ── */
export default function Tables() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [sectionFilter, setSectionFilter] = useState('')
  const [search, setSearch] = useState('')
  const [settleTarget, setSettleTarget] = useState(null)
  const [addItemTarget, setAddItemTarget] = useState(null)
  const [actionLoading, setActionLoading] = useState({})
  const [toast, setToast] = useState(null)

  const params = useMemo(() => ({
    status: statusFilter || undefined,
    section: sectionFilter || undefined,
    search: search || undefined,
  }), [statusFilter, sectionFilter, search])

  const reload = useCallback(() => {
    setLoading(true)
    getOpsTablesFiltered(params)
      .then(setData)
      .finally(() => setLoading(false))
  }, [params])

  useEffect(() => { reload() }, [reload])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const setTableAction = (id, loading) => setActionLoading((prev) => ({ ...prev, [id]: loading }))

  /* ── Actions ── */
  const handleBook = async (tableId) => {
    setTableAction(tableId, true)
    try {
      await bookTable(tableId)
      showToast('Table booked successfully')
      reload()
    } catch (err) {
      showToast(err?.detail || 'Failed to book table', 'error')
    } finally {
      setTableAction(tableId, false)
    }
  }

  const handleReserve = async (tableId) => {
    setTableAction(tableId, true)
    try {
      await reserveTable(tableId)
      showToast('Table reserved')
      reload()
    } catch (err) {
      showToast(err?.detail || 'Failed to reserve', 'error')
    } finally {
      setTableAction(tableId, false)
    }
  }

  const handleUnreserve = async (tableId) => {
    setTableAction(tableId, true)
    try {
      await unreserveTable(tableId)
      showToast('Reservation removed')
      reload()
    } catch (err) {
      showToast(err?.detail || 'Failed to unreserve', 'error')
    } finally {
      setTableAction(tableId, false)
    }
  }

  const handleSeat = async (tableId) => {
    setTableAction(tableId, true)
    try {
      await seatReservedTable(tableId)
      showToast('Guests seated')
      reload()
    } catch (err) {
      showToast(err?.detail || 'Failed to seat', 'error')
    } finally {
      setTableAction(tableId, false)
    }
  }

  const handleSettle = async (tableId, paymentMethod) => {
    try {
      const res = await settleTable(tableId, { payment_method: paymentMethod })
      showToast(`Bill settled — ₹${res.total_amount} via ${paymentMethod}`)
      reload()
    } catch (err) {
      showToast(err?.detail || 'Failed to settle bill', 'error')
    }
  }

  if (loading && !data) {
    return (
      <div className="app-page">
        <div style={{ padding: 'var(--space-12)' }}>
          <div className="tbl-grid-floor">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 200, borderRadius: 'var(--radius-lg)', animationDelay: `${i * 60}ms` }} />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!data) return <div className="loading">Failed to load tables.</div>

  const { summary, tables } = data
  const sections = [...new Set(tables.map((t) => t.section))]

  return (
    <motion.div
      className="app-page"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      {/* Hero */}
      <div className="app-hero">
        <div>
          <div className="app-hero-eyebrow">Floor Management</div>
          <h1 className="app-hero-title">Tables</h1>
          <p className="app-hero-sub">Real-time table status and order management.</p>
        </div>
        <div className="app-hero-metrics">
          <div className="app-kpi">
            <div className="app-kpi-label">Total</div>
            <div className="app-kpi-value">{summary.total_tables}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label" style={{ color: STATUS_CONFIG.empty.color }}>Available</div>
            <div className="app-kpi-value" style={{ color: STATUS_CONFIG.empty.color }}>{summary.empty || 0}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label" style={{ color: STATUS_CONFIG.occupied.color }}>Occupied</div>
            <div className="app-kpi-value" style={{ color: STATUS_CONFIG.occupied.color }}>{summary.occupied || 0}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label" style={{ color: STATUS_CONFIG.reserved.color }}>Reserved</div>
            <div className="app-kpi-value" style={{ color: STATUS_CONFIG.reserved.color }}>{summary.reserved || 0}</div>
          </div>
        </div>
      </div>

      {/* Status Legend + Filters */}
      <div className="tbl-toolbar">
        <div className="tbl-legend">
          {Object.entries(STATUS_CONFIG).filter(([k]) => k !== 'cleaning').map(([key, cfg]) => (
            <div key={key} className="tbl-legend-item">
              <span className="tbl-legend-dot" style={{ background: cfg.color }} />
              <span>{cfg.label}</span>
            </div>
          ))}
        </div>
        <div className="tbl-filters">
          <input
            className="input"
            placeholder="Search table..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ maxWidth: 180 }}
          />
          <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ maxWidth: 160 }}>
            <option value="">All Statuses</option>
            <option value="empty">Available</option>
            <option value="occupied">Occupied</option>
            <option value="reserved">Reserved</option>
          </select>
          {sections.length > 1 && (
            <select className="input" value={sectionFilter} onChange={(e) => setSectionFilter(e.target.value)} style={{ maxWidth: 160 }}>
              <option value="">All Sections</option>
              {sections.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Table Grid */}
      <div className="tbl-grid-floor">
        <AnimatePresence mode="popLayout">
          {tables.map((t) => {
            const cfg = STATUS_CONFIG[t.status] || STATUS_CONFIG.empty
            const isLoading = actionLoading[t.table_id]
            const order = t.order

            return (
              <motion.div
                key={t.table_id}
                className="tbl-card"
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.25 }}
                style={{
                  '--tbl-accent': cfg.color,
                  '--tbl-bg': cfg.bg,
                  '--tbl-border': cfg.border,
                }}
              >
                {/* Card header */}
                <div className="tbl-card-top">
                  <div className="tbl-card-number">
                    <span className="tbl-status-indicator" style={{ background: cfg.color }} />
                    Table {t.table_number}
                  </div>
                  <div className="tbl-status-badge" style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}>
                    {cfg.label}
                  </div>
                </div>

                {/* Table meta */}
                <div className="tbl-card-meta">
                  <span>{t.capacity} seats</span>
                  <span>{t.section}</span>
                </div>

                {/* Order info for occupied */}
                {t.status === 'occupied' && order && (
                  <div className="tbl-order-info">
                    <div className="tbl-order-info-header">
                      <span>Order {order.order_number || order.order_id?.slice(-8)}</span>
                      <span className="tbl-order-total">₹{order.total_amount?.toFixed(0) || '0'}</span>
                    </div>
                    {order.items && order.items.length > 0 && (
                      <div className="tbl-order-items-preview">
                        {order.items.slice(0, 3).map((item, i) => (
                          <div key={i} className="tbl-order-item-row">
                            <span>{item.quantity}× {item.name}</span>
                            <span>₹{item.line_total?.toFixed(0)}</span>
                          </div>
                        ))}
                        {order.items.length > 3 && (
                          <div className="tbl-order-more">+{order.items.length - 3} more items</div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Actions based on status */}
                <div className="tbl-card-actions">
                  {t.status === 'empty' && (
                    <>
                      <button
                        className="tbl-action-btn tbl-action-book"
                        onClick={() => handleBook(t.table_id)}
                        disabled={isLoading}
                      >
                        {isLoading ? 'Booking...' : 'Book Table'}
                      </button>
                      <button
                        className="tbl-action-btn tbl-action-reserve"
                        onClick={() => handleReserve(t.table_id)}
                        disabled={isLoading}
                      >
                        Reserve
                      </button>
                    </>
                  )}

                  {t.status === 'occupied' && (
                    <>
                      <button
                        className="tbl-action-btn tbl-action-add"
                        onClick={() => setAddItemTarget(t)}
                        disabled={isLoading}
                      >
                        + Add Items
                      </button>
                      <button
                        className="tbl-action-btn tbl-action-settle"
                        onClick={() => setSettleTarget(t)}
                        disabled={isLoading}
                      >
                        Settle Bill
                      </button>
                    </>
                  )}

                  {t.status === 'reserved' && (
                    <>
                      <button
                        className="tbl-action-btn tbl-action-seat"
                        onClick={() => handleSeat(t.table_id)}
                        disabled={isLoading}
                      >
                        {isLoading ? 'Seating...' : 'Seat Guests'}
                      </button>
                      <button
                        className="tbl-action-btn tbl-action-cancel"
                        onClick={() => handleUnreserve(t.table_id)}
                        disabled={isLoading}
                      >
                        Cancel Reservation
                      </button>
                    </>
                  )}
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>

      {tables.length === 0 && (
        <div style={{ textAlign: 'center', padding: 'var(--space-12)', color: 'var(--text-muted)' }}>
          No tables found matching your filters.
        </div>
      )}

      {/* Settle Modal */}
      <AnimatePresence>
        {settleTarget && (
          <SettleModal
            table={settleTarget}
            onClose={() => setSettleTarget(null)}
            onSettle={handleSettle}
          />
        )}
      </AnimatePresence>

      {/* Add Item Modal */}
      <AnimatePresence>
        {addItemTarget && (
          <AddItemModal
            table={addItemTarget}
            onClose={() => { setAddItemTarget(null); reload() }}
            onItemAdded={reload}
          />
        )}
      </AnimatePresence>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            className={`tbl-toast ${toast.type === 'error' ? 'tbl-toast-error' : ''}`}
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 40 }}
            transition={{ duration: 0.25 }}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
