import { useState, useEffect } from 'react'
import { getMenuMatrix } from '../api/client'
import MenuMatrix from '../components/MenuMatrix'
import ItemTable from '../components/ItemTable'

export default function MenuAnalysis() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    getMenuMatrix()
      .then(setData)
      .catch(err => console.error('Matrix failed:', err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="loading"><div className="spinner" /> Analyzing menu...</div>
  }

  if (!data) {
    return <div className="loading">Failed to load data.</div>
  }

  const { items, summary } = data
  const filtered = filter === 'all' ? items : items.filter(i => i.quadrant === filter)

  return (
    <div>
      <div className="page-header">
        <h1>Menu Analysis</h1>
        <p>BCG matrix classification — Stars, Plowhorses, Puzzles, Dogs</p>
      </div>

      {/* Quadrant Summary */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {['star', 'plowhorse', 'puzzle', 'dog'].map(q => (
          <div
            key={q}
            className="card"
            style={{ cursor: 'pointer', borderColor: filter === q ? 'var(--orange)' : undefined }}
            onClick={() => setFilter(filter === q ? 'all' : q)}
          >
            <div className="card-body" style={{ textAlign: 'center', padding: 16 }}>
              <div style={{ fontSize: 28, marginBottom: 4 }}>
                {{ star: '⭐', plowhorse: '🐴', puzzle: '🧩', dog: '🐕' }[q]}
              </div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>
                {summary?.[q]?.count || 0}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                {q === 'plowhorse' ? 'Plowhorses' : q + 's'}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* BCG Matrix Chart */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">BCG Menu Matrix</div>
        <div className="card-body">
          <MenuMatrix items={items} />
        </div>
      </div>

      {/* Items Table */}
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Menu Items {filter !== 'all' && `— ${filter}s`}</span>
          {filter !== 'all' && (
            <button className="btn btn-secondary" onClick={() => setFilter('all')}>
              Show All
            </button>
          )}
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          <ItemTable items={filtered} />
        </div>
      </div>
    </div>
  )
}
