import { useState, useEffect } from 'react'
import { getCombos } from '../api/client'
import ComboCard from '../components/ComboCard'

export default function ComboEngine() {
  const [combos, setCombos] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCombos()
      .then(data => setCombos(data.combos || []))
      .catch(err => console.error('Combos failed:', err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="loading"><div className="spinner" /> Mining combos from sales data...</div>
  }

  return (
    <div>
      <div className="page-header">
        <h1>Combo Engine</h1>
        <p>AI-generated combo recommendations from frequently co-ordered items</p>
      </div>

      {combos.length === 0 ? (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 40 }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>🔗</div>
            <p style={{ color: 'var(--text-muted)' }}>No combos generated yet. Make sure the database is seeded.</p>
          </div>
        </div>
      ) : (
        <div className="grid-2">
          {combos.map((combo, idx) => (
            <ComboCard key={combo.combo_id || idx} combo={combo} />
          ))}
        </div>
      )}
    </div>
  )
}
