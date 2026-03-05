export default function MetricCard({ label, value, suffix = '', color, icon }) {
  return (
    <div className="card">
      <div className="card-body" style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {label}
            </div>
            <div style={{ fontSize: 24, fontWeight: 800, color: color || 'var(--text)' }}>
              {value}{suffix && <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)' }}>{suffix}</span>}
            </div>
          </div>
          <div style={{ fontSize: 28, opacity: 0.7 }}>{icon}</div>
        </div>
      </div>
    </div>
  )
}
