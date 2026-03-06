import { useEffect, useMemo, useState } from 'react'
import { getMenuMatrix, getTrends } from '../api/client'
import MenuMatrix from '../components/MenuMatrix'
import ItemTable from '../components/ItemTable'
import { motion } from 'motion/react'
import { ScrollReveal, fadeInUp } from '../utils/animations'

const QUAD_META = {
  star: { label: 'Stars', color: 'var(--success)', icon: '⭐' },
  puzzle: { label: 'Hidden Gems', color: 'var(--info)', icon: '🔷' },
  plowhorse: { label: 'Plowhorses', color: 'var(--warning)', icon: '🐴' },
  dog: { label: 'Underperformers', color: 'var(--danger)', icon: '📉' },
}

export default function MenuAnalysis() {
  const [data, setData] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(true)
  const [trendsLoading, setTrendsLoading] = useState(true)
  const [quadrantFilter, setQuadrantFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [showAllCategoryTrends, setShowAllCategoryTrends] = useState(false)
  const [trendSortBy, setTrendSortBy] = useState('revenue_last_30d')
  const [trendSortDir, setTrendSortDir] = useState('desc')

  useEffect(() => {
    let active = true

    getMenuMatrix()
      .then((matrixData) => {
        if (!active) return
        setData(matrixData)
      })
      .catch((err) => console.error('Menu Matrix failed:', err))
      .finally(() => {
        if (active) setLoading(false)
      })

    getTrends()
      .then((trendsData) => {
        if (!active) return
        setTrends(trendsData)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setTrendsLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const categoryTrends = useMemo(() => {
    const rows = [...(trends?.category_trends || [])]
      .filter((row) => {
        if (showAllCategoryTrends) return true
        return (row.revenue_last_30d || 0) > 0 || (row.revenue_prev_30d || 0) > 0
      })

    rows.sort((a, b) => {
      const aVal = a[trendSortBy] || 0
      const bVal = b[trendSortBy] || 0
      return trendSortDir === 'desc' ? bVal - aVal : aVal - bVal
    })

    return rows
  }, [trends, showAllCategoryTrends, trendSortBy, trendSortDir])

  if (loading) {
    return <div className="loading"><div className="spinner" />Analyzing menu...</div>
  }

  if (!data || !data.items) {
    return <div className="loading">Failed to load data. Is the backend running?</div>
  }

  const items = data.items || []
  const categories = ['all', ...Array.from(new Set(items.map((i) => i.category)))]

  const itemTrendMap = {}
  if (trends?.item_trends) {
    for (const trend of trends.item_trends) itemTrendMap[trend.item_id] = trend
  }

  const enrichedItems = items.map((item) => {
    const trend = itemTrendMap[item.item_id]
    return {
      ...item,
      revenue_trend_arrow: trend?.revenue_trend_arrow || '',
      popularity_trend_arrow: trend?.popularity_trend_arrow || '',
      revenue_trend_pct: trend?.revenue_trend_pct || 0,
      direction: trend?.direction || '',
    }
  })

  const quadrantCounts = {
    star: items.filter((i) => i.quadrant === 'star').length,
    puzzle: items.filter((i) => i.quadrant === 'puzzle').length,
    plowhorse: items.filter((i) => i.quadrant === 'plowhorse').length,
    dog: items.filter((i) => i.quadrant === 'dog').length,
  }

  const driftItems = trends?.quadrant_drift || []
  const driftByQuadrant = {}
  for (const drift of driftItems) {
    driftByQuadrant[drift.current_quadrant] = (driftByQuadrant[drift.current_quadrant] || 0) + 1
  }

  const handleTrendSort = (column) => {
    if (trendSortBy === column) {
      setTrendSortDir((prev) => (prev === 'desc' ? 'asc' : 'desc'))
    } else {
      setTrendSortBy(column)
      setTrendSortDir('desc')
    }
  }

  const trendSortIcon = (column) => (trendSortBy === column ? (trendSortDir === 'desc' ? ' ↓' : ' ↑') : '')

  return (
    <motion.div
      className="app-page"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <motion.div
        className="app-hero"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div>
          <div className="app-hero-eyebrow">Intelligence</div>
          <h1 className="app-hero-title">Menu Intelligence</h1>
          <p className="app-hero-sub">Menu performance by profitability and popularity. See which items are driving your revenue.</p>
        </div>
      </motion.div>

      {trendsLoading && (
        <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
          <div className="card-body" style={{ fontSize: 12, color: 'var(--text-muted)', padding: 'var(--space-3) var(--space-5)' }}>
            Loading trend overlays...
          </div>
        </div>
      )}

      <div className="quadrant-chip-row">
        {Object.entries(QUAD_META).map(([id, meta]) => {
          const active = quadrantFilter === id
          return (
            <button
              key={id}
              className={`quadrant-chip ${active ? 'quadrant-chip--active' : ''}`}
              style={{ '--quad-color': meta.color }}
              onClick={() => setQuadrantFilter(active ? 'all' : id)}
            >
              <span className="quadrant-chip-icon">{meta.icon}</span>
              <span className="quadrant-chip-count">{quadrantCounts[id]}</span>
              <span className="quadrant-chip-label">{meta.label}</span>
              <span className="quadrant-chip-drift">{driftByQuadrant[id] || 0} drifting</span>
            </button>
          )
        })}
      </div>

      <div className="grid-2">
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">BCG Menu Matrix</div>
          <div className="card-body">
            <MenuMatrix items={items} />
          </div>
        </div>

        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Menu Items</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
                {categories.map((category) => (
                  <option key={category} value={category}>{category === 'all' ? 'All Categories' : category}</option>
                ))}
              </select>
              {quadrantFilter !== 'all' && (
                <button className="btn btn-ghost" onClick={() => setQuadrantFilter('all')} style={{ padding: '4px 8px', fontSize: 12 }}>
                  Clear
                </button>
              )}
            </div>
          </div>
          <div className="card-body" style={{ padding: 0, maxHeight: 460, overflowY: 'auto' }}>
            <ItemTable items={enrichedItems} categoryFilter={categoryFilter} quadrantFilter={quadrantFilter} />
          </div>
        </div>
      </div>

      {categoryTrends.length > 0 && (
        <ScrollReveal variants={fadeInUp}>
          <div className="card" style={{ marginTop: 24 }}>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Category Revenue Trends (30-day)</span>
              <button className="btn btn-ghost" style={{ fontSize: 11 }} onClick={() => setShowAllCategoryTrends((prev) => !prev)}>
                {showAllCategoryTrends ? 'Hide Zero-Revenue Categories' : 'Show All'}
              </button>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Category</th>
                    <th style={{ textAlign: 'right', cursor: 'pointer' }} onClick={() => handleTrendSort('revenue_last_30d')}>
                      Revenue (Last 30d){trendSortIcon('revenue_last_30d')}
                    </th>
                    <th style={{ textAlign: 'right', cursor: 'pointer' }} onClick={() => handleTrendSort('revenue_prev_30d')}>
                      Revenue (Prev 30d){trendSortIcon('revenue_prev_30d')}
                    </th>
                    <th style={{ textAlign: 'right', cursor: 'pointer' }} onClick={() => handleTrendSort('trend_pct')}>
                      Trend{trendSortIcon('trend_pct')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {categoryTrends.map((row, index) => (
                    <tr key={index}>
                      <td style={{ fontWeight: 600 }}>{row.category_name}</td>
                      <td className="col-number">INR {(row.revenue_last_30d || 0).toLocaleString('en-IN')}</td>
                      <td className="col-number">INR {(row.revenue_prev_30d || 0).toLocaleString('en-IN')}</td>
                      <td
                        className="col-number"
                        style={{
                          fontWeight: 700,
                          color: row.trend_pct > 0 ? 'var(--success)' : row.trend_pct < 0 ? 'var(--danger)' : 'var(--text-muted)',
                        }}
                      >
                        {row.trend_arrow} {row.trend_pct > 0 ? '+' : ''}{row.trend_pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </ScrollReveal>
      )}
    </motion.div>
  )
}
