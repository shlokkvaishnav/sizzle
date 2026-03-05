export default function OrderSummary({ order }) {
  if (!order) return null

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>🛒 Order Summary</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{order.order_id}</span>
      </div>
      <div className="card-body">
        {order.items?.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <span style={{ fontSize: 13, fontWeight: 600 }}>
                {item.quantity}× {item.name}
              </span>
              {item.is_veg !== undefined && (
                <span className={`tag ${item.is_veg ? 'tag-veg' : 'tag-nonveg'}`} style={{ marginLeft: 8 }}>
                  {item.is_veg ? 'VEG' : 'NON-VEG'}
                </span>
              )}
              {/* Modifiers */}
              {item.modifiers && Object.keys(item.modifiers).some(k => {
                const v = item.modifiers[k]
                return v && v !== 'medium' && v !== 'regular' && (Array.isArray(v) ? v.length > 0 : v)
              }) && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {item.modifiers.spice_level && item.modifiers.spice_level !== 'medium' && `🌶️ ${item.modifiers.spice_level} `}
                  {item.modifiers.add_ons?.map(a => a.replace('_', ' ')).join(', ')}
                </div>
              )}
            </div>
            <span style={{ fontWeight: 600 }}>₹{item.line_total}</span>
          </div>
        ))}

        {/* Totals */}
        <div style={{ marginTop: 12, paddingTop: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
            <span>Subtotal</span>
            <span>₹{order.subtotal}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
            <span>GST (5%)</span>
            <span>₹{order.tax}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 16, fontWeight: 800, color: 'var(--orange)', borderTop: '1px solid var(--border)', paddingTop: 8 }}>
            <span>Total</span>
            <span>₹{order.total}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
