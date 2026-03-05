import { useState } from 'react'

export default function ItemTable({ items }) {
  const [sortBy, setSortBy] = useState('margin_pct')
  const [sortDir, setSortDir] = useState('desc')

  if (!items || items.length === 0) {
    return <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>No items to display</div>
  }

  const sorted = [...items].sort((a, b) => {
    const aVal = a[sortBy] ?? 0
    const bVal = b[sortBy] ?? 0
    return sortDir === 'desc' ? bVal - aVal : aVal - bVal
  })

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
  }

  const quadrantTag = (q) => {
    const emojis = { star: '⭐', plowhorse: '🐴', puzzle: '🧩', dog: '🐕' }
    return <span className={`tag tag-${q}`}>{emojis[q]} {q}</span>
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Category</th>
          <th style={{ cursor: 'pointer' }} onClick={() => handleSort('selling_price')}>
            Price {sortBy === 'selling_price' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
          </th>
          <th style={{ cursor: 'pointer' }} onClick={() => handleSort('margin_pct')}>
            Margin % {sortBy === 'margin_pct' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
          </th>
          <th style={{ cursor: 'pointer' }} onClick={() => handleSort('popularity_score')}>
            Popularity {sortBy === 'popularity_score' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
          </th>
          <th>Quadrant</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(item => (
          <tr key={item.item_id}>
            <td>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{item.name}</div>
              {item.name_hi && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.name_hi}</div>}
            </td>
            <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.category}</td>
            <td style={{ fontWeight: 600 }}>₹{item.selling_price}</td>
            <td>
              <span style={{ color: item.margin_pct >= 65 ? 'var(--green)' : item.margin_pct >= 50 ? 'var(--amber)' : 'var(--red)' }}>
                {item.margin_pct}%
              </span>
            </td>
            <td>
              <div style={{ width: 60, height: 6, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${(item.popularity_score || 0) * 100}%`, height: '100%', background: 'var(--blue)', borderRadius: 3 }} />
              </div>
            </td>
            <td>{quadrantTag(item.quadrant)}</td>
            <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 200 }}>
              {item.action}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
