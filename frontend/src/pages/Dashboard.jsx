import { useState, useEffect } from 'react'
import {
  getDashboardMetrics,
  getHiddenStars,
  getRisks,
  getCategoryBreakdown,
  getTrends,
  getWowMom,
  getPriceElasticity,
  getCannibalization,
  getPriceSensitivity,
  getWasteAnalysis,
  getCustomerReturns,
  getMenuComplexity,
  getOperationalMetrics,
} from '../api/client'
import MetricCard from '../components/MetricCard'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend, CartesianGrid, Area, AreaChart,
} from 'recharts'

const CHART_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
const TOOLTIP_STYLE = { backgroundColor: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)', fontSize: 12 }
const TICK_STYLE = { fill: 'var(--text-muted)', fontSize: 11 }

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [hiddenStars, setHiddenStars] = useState([])
  const [riskItems, setRiskItems] = useState([])
  const [categoryData, setCategoryData] = useState([])
  const [trends, setTrends] = useState(null)
  const [wowMom, setWowMom] = useState([])
  const [elasticity, setElasticity] = useState([])
  const [cannibalization, setCannibalization] = useState([])
  const [priceSensitivity, setPriceSensitivity] = useState([])
  const [waste, setWaste] = useState(null)
  const [customerReturns, setCustomerReturns] = useState(null)
  const [menuComplexity, setMenuComplexity] = useState([])
  const [showHealthBreakdown, setShowHealthBreakdown] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getDashboardMetrics(),
      getHiddenStars().catch(() => ({ items: [] })),
      getRisks().catch(() => ({ items: [] })),
      getCategoryBreakdown().catch(() => ({ categories: [] })),
      getTrends().catch(() => null),
      getWowMom().catch(() => ({ items: [] })),
      getPriceElasticity().catch(() => ({ items: [] })),
      getCannibalization().catch(() => ({ items: [] })),
      getPriceSensitivity().catch(() => ({ items: [] })),
      getWasteAnalysis().catch(() => null),
      getCustomerReturns().catch(() => null),
      getMenuComplexity().catch(() => ({ categories: [] })),
    ])
      .then(([m, hs, ri, cb, tr, wm, el, cn, ps, wa, cr, mc]) => {
        setMetrics(m)
        setHiddenStars((hs.items || hs || []).slice(0, 5))
        setRiskItems((ri.items || ri || []).slice(0, 5))
        setCategoryData(cb.categories || cb || [])
        setTrends(tr)
        setWowMom((wm.items || []).slice(0, 10))
        setElasticity((el.items || []).slice(0, 10))
        setCannibalization((cn.items || []).slice(0, 8))
        setPriceSensitivity((ps.items || []).slice(0, 8))
        setWaste(wa)
        setCustomerReturns(cr)
        setMenuComplexity(mc.categories || [])
      })
      .catch(err => console.error('Dashboard load failed:', err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="loading"><div className="spinner" /> Loading dashboard...</div>
  }

  if (!metrics) {
    return <div className="loading">Failed to load data. Is the backend running?</div>
  }

  const healthBreakdown = metrics.health_score_breakdown || {}
  const driftItems = trends?.quadrant_drift || []
  const peakHours = metrics.peak_hours || []
  const seasonalPatterns = trends?.seasonal_patterns || []

  // Prepare category pie data
  const categoryPieData = categoryData.slice(0, 6).map((c, i) => ({
    name: c.category_name || c.category,
    value: c.total_revenue || 0,
    fill: CHART_COLORS[i % CHART_COLORS.length],
  }))

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Revenue intelligence overview — all metrics at a glance</p>
      </div>

      {/* ─── KPI Cards Row 1: Strategic ─── */}
      <div className="grid-4" style={{ marginBottom: 16 }}>
        <MetricCard label="Total Revenue" value={`₹${metrics.total_revenue?.toLocaleString() || 0}`} color="var(--blue)" icon="💰" />
        <MetricCard label="Avg CM%" value={`${metrics.avg_cm_percent || 0}%`} color="var(--green)" icon="📈" />
        <MetricCard label="Items At Risk" value={metrics.items_at_risk_count || 0} color="var(--red)" icon="⚠️" />
        <MetricCard label="Uplift Potential" value={`₹${metrics.uplift_potential?.toLocaleString() || 0}`} color="var(--amber)" icon="🚀" />
      </div>

      {/* ─── KPI Cards Row 2: Operational ─── */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <MetricCard label="Avg Order Value" value={`₹${metrics.avg_order_value?.toLocaleString() || 0}`} color="var(--purple)" icon="🧾" />
        <MetricCard label="Total Orders (30d)" value={metrics.total_orders || 0} color="var(--blue)" icon="📋" />
        <div className="card" style={{ cursor: 'pointer' }} onClick={() => setShowHealthBreakdown(!showHealthBreakdown)}>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 16 }}>
            <div>
              <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: 1 }}>
                Health Score <span style={{ fontSize: 10, opacity: 0.7 }}>ⓘ click</span>
              </div>
              <div style={{ fontSize: 26, fontWeight: 700, color: metrics.health_score >= 60 ? 'var(--green)' : metrics.health_score >= 40 ? 'var(--amber)' : 'var(--red)' }}>
                {metrics.health_score || 0}
              </div>
            </div>
            <div style={{ fontSize: 28 }}>🏥</div>
          </div>
        </div>
        <MetricCard label="Peak Hour" value={peakHours[0]?.label || '—'} suffix={peakHours[0] ? ` (${peakHours[0].order_count} orders)` : ''} color="var(--amber)" icon="⏰" />
      </div>

      {/* ─── Health Score Breakdown (collapsible) ─── */}
      {showHealthBreakdown && healthBreakdown.components && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">🏥 Health Score Breakdown</div>
          <div className="card-body">
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
              {healthBreakdown.explanation}
            </p>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {healthBreakdown.components.map((c, i) => (
                <div key={i} style={{ flex: '1 1 200px', padding: 12, background: 'var(--surface2)', borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{c.name}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: c.score >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {c.score > 0 ? '+' : ''}{c.score} <span style={{ fontSize: 11, fontWeight: 400 }}>/ {c.max}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{c.detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ─── Charts Row 1: Category CM% + Peak Hours ─── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header">📊 Average CM% per Category</div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={categoryData} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="category_name" tick={TICK_STYLE} />
                <YAxis tick={TICK_STYLE} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="avg_cm_pct" fill="var(--blue)" radius={[4, 4, 0, 0]} name="CM%" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-header">⏰ Orders by Hour</div>
          <div className="card-body">
            {peakHours.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>No hourly data available.</div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={[...peakHours].sort((a, b) => a.hour - b.hour)} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={TICK_STYLE} />
                  <YAxis tick={TICK_STYLE} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Area type="monotone" dataKey="order_count" fill="rgba(139, 92, 246, 0.3)" stroke="var(--purple)" strokeWidth={2} name="Orders" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* ─── Charts Row 2: Revenue Pie + Orders by Type ─── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header">🥧 Revenue by Category</div>
          <div className="card-body" style={{ display: 'flex', justifyContent: 'center' }}>
            {categoryPieData.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: 40 }}>No data.</div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={categoryPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {categoryPieData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => `₹${v.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {metrics.orders_by_type?.length > 0 && (
          <div className="card">
            <div className="card-header">📦 Orders by Type (30d)</div>
            <div className="card-body">
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {metrics.orders_by_type.map((t, i) => (
                  <div key={i} style={{ flex: '1 1 80px', padding: 16, background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{t.type?.replace('_', ' ')}</div>
                    <div style={{ fontSize: 22, fontWeight: 700 }}>{t.count}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>₹{t.revenue?.toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ─── Quick Lists: Hidden Stars + Risk Items ─── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header" style={{ color: 'var(--purple)' }}>🔍 Top Hidden Stars</div>
            <div className="card-body">
              {hiddenStars.length === 0 ? <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No hidden stars found.</div> : hiddenStars.map((item, i) => (
                <div key={item.item_id || i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 13 }}>{item.name}</span>
                  <div>
                    <span style={{ fontSize: 12, color: 'var(--purple)', fontWeight: 600 }}>CM: {item.cm_percent || item.margin_pct}%</span>
                    {item.estimated_monthly_uplift && (
                      <span style={{ fontSize: 11, color: 'var(--green)', marginLeft: 8 }}>+₹{item.estimated_monthly_uplift.toLocaleString()}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header" style={{ color: 'var(--red)' }}>⚠️ Top Risk Items</div>
            <div className="card-body">
              {riskItems.length === 0 ? <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No items at risk.</div> : riskItems.map((item, i) => (
                <div key={item.item_id || i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 13 }}>{item.name}</span>
                  <div>
                    <span style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600 }}>CM: {item.cm_percent || item.margin_pct}%</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>Risk: {item.risk_score}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Quadrant Drift Alerts */}
        <div className="card">
          <div className="card-header" style={{ color: 'var(--amber)' }}>📈 Quadrant Drift Alerts</div>
          <div className="card-body">
            {driftItems.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No significant quadrant shifts detected.</div>
            ) : driftItems.slice(0, 6).map((item, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{item.name}</span>
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 4,
                    background: item.drift_direction?.includes('dog') ? 'var(--red)' : 'var(--amber)',
                    color: '#fff',
                  }}>
                    {item.drift_direction}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {item.drift_warning} • Pop: {item.popularity_trend_pct}% {item.trend_arrow}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ─── WoW / MoM Revenue Changes ─── */}
      {wowMom.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">📅 Week-over-Week / Month-over-Month Revenue Changes</div>
          <div className="card-body">
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>WoW Change</th>
                    <th>MoM Change</th>
                    <th>This Week Revenue</th>
                    <th>Last Week Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {wowMom.map((item, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{item.name}</td>
                      <td style={{ color: (item.wow_change_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                        {(item.wow_change_pct || 0) > 0 ? '+' : ''}{item.wow_change_pct?.toFixed(1) || '—'}%
                      </td>
                      <td style={{ color: (item.mom_change_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                        {(item.mom_change_pct || 0) > 0 ? '+' : ''}{item.mom_change_pct?.toFixed(1) || '—'}%
                      </td>
                      <td>₹{item.this_week_revenue?.toLocaleString() || '—'}</td>
                      <td>₹{item.last_week_revenue?.toLocaleString() || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── Price Elasticity ─── */}
      {elasticity.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">📐 Price Elasticity Estimates</div>
          <div className="card-body">
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>Items where price changes affected demand volume.</p>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Price Change</th>
                    <th>Volume Change</th>
                    <th>Elasticity</th>
                    <th>Classification</th>
                  </tr>
                </thead>
                <tbody>
                  {elasticity.map((item, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{item.name}</td>
                      <td>{item.price_change_pct?.toFixed(1) || '—'}%</td>
                      <td style={{ color: (item.volume_change_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        {item.volume_change_pct?.toFixed(1) || '—'}%
                      </td>
                      <td>{item.elasticity?.toFixed(2) || '—'}</td>
                      <td>
                        <span className={`tag tag-${item.classification === 'elastic' ? 'red' : item.classification === 'inelastic' ? 'green' : 'blue'}`}>
                          {item.classification || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── Advanced Analytics: Cannibalization + Price Sensitivity ─── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        {cannibalization.length > 0 && (
          <div className="card">
            <div className="card-header" style={{ color: 'var(--red)' }}>🔀 Cannibalization Alerts</div>
            <div className="card-body">
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>New items that may be eating into existing sales.</p>
              {cannibalization.map((item, i) => (
                <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{item.new_item || item.name}</span>
                    <span style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600 }}>
                      {item.cannibalization_pct?.toFixed(0) || item.overlap_pct?.toFixed(0) || '—'}% overlap
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    Affected: {item.affected_item || item.victim || '—'} • {item.recommendation || ''}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {priceSensitivity.length > 0 && (
          <div className="card">
            <div className="card-header" style={{ color: 'var(--amber)' }}>💲 Price Sensitivity — Plowhorse Items</div>
            <div className="card-body">
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>High-volume, low-margin items that could absorb a price increase.</p>
              {priceSensitivity.map((item, i) => (
                <div key={i} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{item.name}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--green)' }}>
                      +₹{item.projected_revenue_gain?.toLocaleString() || item.revenue_impact?.toLocaleString() || '—'}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    Current: ₹{item.current_price} → Suggested: ₹{item.suggested_price || item.recommended_price || '—'} | {item.recommendation || ''}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ─── Waste & Voids + Customer Returns ─── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        {waste && (
          <div className="card">
            <div className="card-header" style={{ color: 'var(--red)' }}>🗑️ Waste & Void Analysis (30d)</div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div style={{ padding: 12, background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Total Waste Cost</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--red)' }}>₹{waste.total_waste_cost?.toLocaleString() || 0}</div>
                </div>
                <div style={{ padding: 12, background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Void Rate</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--amber)' }}>{waste.void_rate_pct?.toFixed(1) || 0}%</div>
                </div>
              </div>
              {waste.top_voided_items?.length > 0 && (
                <>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>Top Voided Items</div>
                  {waste.top_voided_items.slice(0, 5).map((item, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13, borderBottom: '1px solid var(--border)' }}>
                      <span>{item.name}</span>
                      <span style={{ color: 'var(--red)', fontWeight: 600 }}>{item.void_count || item.count} voids</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}

        {customerReturns && (
          <div className="card">
            <div className="card-header" style={{ color: 'var(--green)' }}>🔄 Customer Return Rates</div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div style={{ padding: 12, background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Repeat Rate</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>{customerReturns.repeat_rate_pct?.toFixed(1) || 0}%</div>
                </div>
                <div style={{ padding: 12, background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Unique Tables</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{customerReturns.unique_tables || customerReturns.unique_customers || 0}</div>
                </div>
              </div>
              {customerReturns.top_returning_tables?.length > 0 && (
                <>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>Most Frequent Tables</div>
                  {customerReturns.top_returning_tables.slice(0, 5).map((t, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13, borderBottom: '1px solid var(--border)' }}>
                      <span>{t.table_id || t.table || `Table ${i + 1}`}</span>
                      <span style={{ fontWeight: 600 }}>{t.visit_count || t.visits} visits</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ─── Menu Complexity ─── */}
      {menuComplexity.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">🧩 Menu Complexity by Category</div>
          <div className="card-body">
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>Categories with more than 7 items may suffer from decision fatigue.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
              {menuComplexity.map((cat, i) => (
                <div key={i} style={{
                  padding: 16, background: 'var(--surface2)', borderRadius: 8,
                  border: `1px solid ${cat.item_count > 7 || cat.alert ? 'var(--amber)' : 'var(--border)'}`,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{cat.category_name || cat.name}</div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>{cat.item_count || cat.count}</div>
                  <div style={{ fontSize: 11, color: (cat.item_count > 7 || cat.alert) ? 'var(--amber)' : 'var(--text-muted)' }}>
                    {(cat.item_count > 7 || cat.alert) ? '⚠️ Consider trimming' : 'Optimal range'}
                  </div>
                  {cat.complexity_score != null && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Score: {cat.complexity_score}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ─── Seasonal Patterns ─── */}
      {seasonalPatterns.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">🌦️ Seasonal / Day-of-Week Patterns</div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={seasonalPatterns} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={TICK_STYLE} />
                <YAxis tick={TICK_STYLE} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="avg_revenue" fill="var(--amber)" radius={[4, 4, 0, 0]} name="Avg Revenue" />
                <Bar dataKey="avg_orders" fill="var(--blue)" radius={[4, 4, 0, 0]} name="Avg Orders" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
