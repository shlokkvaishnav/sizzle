export default function ComboCard({ combo }) {
  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>🔗 {combo.name || combo.combo_id}</span>
        <span className="tag tag-star">Margin {combo.margin_pct}%</span>
      </div>
      <div className="card-body">
        {/* Items in combo */}
        <div style={{ marginBottom: 12 }}>
          {combo.items?.map((item, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 13 }}>
              <span>{item.name}</span>
              <span style={{ color: 'var(--text-muted)' }}>₹{item.price}</span>
            </div>
          ))}
        </div>

        {/* Pricing breakdown */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
            <span style={{ color: 'var(--text-muted)' }}>Individual total</span>
            <span style={{ textDecoration: 'line-through', color: 'var(--text-muted)' }}>₹{combo.individual_total}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 700 }}>
            <span style={{ color: 'var(--orange)' }}>Combo price</span>
            <span style={{ color: 'var(--orange)' }}>₹{combo.combo_price}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--green)', marginTop: 4 }}>
            <span>Save {combo.discount_pct}%</span>
            <span>Expected margin: ₹{combo.expected_margin}</span>
          </div>
        </div>

        {/* Stats */}
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)' }}>
          Co-ordered {combo.co_order_count} times • Support: {(combo.support * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  )
}
