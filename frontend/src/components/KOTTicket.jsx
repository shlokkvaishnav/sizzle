export default function KOTTicket({ kot }) {
  if (!kot) return null

  return (
    <div className="card" style={{ fontFamily: "'Courier New', monospace" }}>
      <div className="card-header" style={{ textAlign: 'center', borderBottom: '2px dashed var(--border)' }}>
        🎫 KITCHEN ORDER TICKET
      </div>
      <div className="card-body" style={{ padding: 16 }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 12, paddingBottom: 8, borderBottom: '1px dashed var(--border)' }}>
          <div style={{ fontSize: 14, fontWeight: 700 }}>{kot.kot_id}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {kot.order_type?.toUpperCase()} • Table: {kot.table || '-'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{kot.timestamp}</div>
        </div>

        {/* Items */}
        {kot.items?.map((item, idx) => (
          <div key={idx} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 700 }}>
              <span>{item.name}</span>
              <span>×{item.qty}</span>
            </div>
            {item.modifiers?.length > 0 && (
              <div style={{ fontSize: 11, color: 'var(--amber)', paddingLeft: 8 }}>
                → {item.modifiers.join(', ')}
              </div>
            )}
            {item.notes && (
              <div style={{ fontSize: 11, color: 'var(--red)', paddingLeft: 8 }}>
                ★ {item.notes}
              </div>
            )}
          </div>
        ))}

        {/* Footer */}
        <div style={{ borderTop: '2px dashed var(--border)', paddingTop: 8, marginTop: 8, textAlign: 'center' }}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>
            Total items: {kot.total_items}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            --- PETPOOJA AI COPILOT ---
          </div>
        </div>
      </div>
    </div>
  )
}
