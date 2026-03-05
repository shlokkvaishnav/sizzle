/**
 * MenuMatrix.jsx — 2×2 BCG Quadrant Scatter Chart
 * Plots items based on popularity (x) vs margin (y)
 */

import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const QUADRANT_COLORS = {
  star: '#4ade80',
  plowhorse: '#60a5fa',
  puzzle: '#ffb347',
  dog: '#f87171',
}

export default function MenuMatrix({ items }) {
  if (!items || items.length === 0) return null

  const chartData = items.map(item => ({
    x: item.popularity_score,
    y: item.margin_pct,
    name: item.name,
    quadrant: item.quadrant,
    emoji: item.emoji,
  }))

  return (
    <div style={{ position: 'relative' }}>
      {/* Quadrant labels */}
      <div style={{ position: 'absolute', top: 8, left: 60, fontSize: 11, color: 'var(--text-muted)', zIndex: 1 }}>
        🧩 Puzzles (High Margin, Low Pop)
      </div>
      <div style={{ position: 'absolute', top: 8, right: 16, fontSize: 11, color: 'var(--text-muted)', zIndex: 1 }}>
        ⭐ Stars (High Margin, High Pop)
      </div>
      <div style={{ position: 'absolute', bottom: 30, left: 60, fontSize: 11, color: 'var(--text-muted)', zIndex: 1 }}>
        🐕 Dogs (Low Margin, Low Pop)
      </div>
      <div style={{ position: 'absolute', bottom: 30, right: 16, fontSize: 11, color: 'var(--text-muted)', zIndex: 1 }}>
        🐴 Plowhorses (Low Margin, High Pop)
      </div>

      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 30, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            type="number"
            name="Popularity"
            domain={[0, 1]}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            label={{ value: 'Popularity →', position: 'bottom', fill: 'var(--text-muted)', fontSize: 11 }}
          />
          <YAxis
            dataKey="y"
            type="number"
            name="Margin %"
            domain={[0, 100]}
            tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
            label={{ value: 'Margin % →', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 11 }}
          />
          <Tooltip
            content={({ payload }) => {
              if (!payload || !payload[0]) return null
              const item = payload[0].payload
              return (
                <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
                  <div style={{ fontWeight: 600 }}>{item.emoji} {item.name}</div>
                  <div style={{ color: 'var(--text-muted)' }}>Popularity: {(item.x * 100).toFixed(0)}%</div>
                  <div style={{ color: 'var(--text-muted)' }}>Margin: {item.y.toFixed(1)}%</div>
                </div>
              )
            }}
          />
          <Scatter data={chartData}>
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={QUADRANT_COLORS[entry.quadrant] || '#888'} opacity={0.8} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
