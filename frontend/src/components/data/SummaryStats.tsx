'use client'

import { useState } from 'react'

interface Props {
  summary_stats: Record<string, Record<string, unknown>>
  sources_used: Array<{ name: string; type: string }>
  row_count: number
}

const MAX_VISIBLE = 6

function fmt(v: unknown): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  if (Number.isInteger(n)) return n.toLocaleString()
  return n.toFixed(2)
}

export default function SummaryStats({ summary_stats, sources_used, row_count }: Props) {
  const [showAll, setShowAll] = useState(false)

  const entries = Object.entries(summary_stats)
  const visible = showAll ? entries : entries.slice(0, MAX_VISIBLE)
  const hasMore = entries.length > MAX_VISIBLE

  return (
    <div className="summary-stats">
      <div className="summary-stats-meta">
        <span className="summary-stats-rows">📊 {row_count.toLocaleString()} rows returned</span>
        <div className="summary-stats-sources">
          {sources_used.map((s, i) => (
            <span key={i} className="summary-source-badge">
              {s.type === 'file' ? '📁' : '🔌'} {s.name}
            </span>
          ))}
        </div>
      </div>

      {visible.length > 0 && (
        <div className="summary-stats-cards">
          {visible.map(([col, stats]) => {
            const isNumeric = 'mean' in stats
            return (
              <div key={col} className="summary-stat-card">
                <div className="summary-stat-col" title={col}>
                  {col}
                </div>
                {isNumeric ? (
                  <div className="summary-stat-value">avg {fmt(stats.mean)}</div>
                ) : (
                  <div className="summary-stat-value">
                    {typeof stats.unique_count === 'number'
                      ? `${stats.unique_count.toLocaleString()} unique`
                      : '—'}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {hasMore && (
        <button className="summary-stats-toggle" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show less' : `Show ${entries.length - MAX_VISIBLE} more`}
        </button>
      )}
    </div>
  )
}
