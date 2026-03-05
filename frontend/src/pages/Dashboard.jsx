import { useState, useEffect } from 'react'
import { getFullAnalysis } from '../api/client'
import MetricCard from '../components/MetricCard'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFullAnalysis()
      .then(setData)
      .catch(err => console.error('Analysis failed:', err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="loading"><div className="spinner" /> Loading analysis...</div>
  }

  if (!data) {
    return <div className="loading">Failed to load data. Is the backend running?</div>
  }

  const { summary, matrix, hidden_stars, combos } = data

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Revenue intelligence overview — all metrics at a glance</p>
      </div>

      {/* KPI Cards */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <MetricCard
          label="Menu Health Score"
          value={summary.health_score}
          suffix="/100"
          color="var(--orange)"
          icon="📊"
        />
        <MetricCard
          label="Avg. Margin"
          value={`${summary.avg_margin_pct}%`}
          color="var(--green)"
          icon="💰"
        />
        <MetricCard
          label="Star Items"
          value={summary.stars}
          color="var(--green)"
          icon="⭐"
        />
        <MetricCard
          label="Hidden Stars"
          value={summary.hidden_stars_count}
          color="var(--amber)"
          icon="🔍"
        />
      </div>

      <div className="grid-4" style={{ marginBottom: 24 }}>
        <MetricCard
          label="Total Items"
          value={summary.total_items}
          color="var(--blue)"
          icon="🍽️"
        />
        <MetricCard
          label="Dog Items"
          value={summary.dogs}
          color="var(--red)"
          icon="🐕"
        />
        <MetricCard
          label="Combos Suggested"
          value={summary.combos_suggested}
          color="var(--purple)"
          icon="🔗"
        />
        <MetricCard
          label="Price Actions"
          value={summary.price_actions}
          color="var(--cyan)"
          icon="📈"
        />
      </div>

      {/* Quick glance: quadrant distribution */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">⭐ Top Stars</div>
          <div className="card-body">
            {matrix && matrix
              .filter(i => i.quadrant === 'star')
              .slice(0, 5)
              .map(item => (
                <div key={item.item_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 13 }}>{item.name}</span>
                  <span style={{ fontSize: 12, color: 'var(--green)' }}>{item.margin_pct}% margin</span>
                </div>
              ))
            }
          </div>
        </div>

        <div className="card">
          <div className="card-header">🔍 Hidden Stars (Boost These!)</div>
          <div className="card-body">
            {hidden_stars && hidden_stars.slice(0, 5).map(item => (
              <div key={item.item_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: 13 }}>{item.name}</span>
                <span style={{ fontSize: 12, color: 'var(--amber)' }}>Opportunity: {item.opportunity_score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
