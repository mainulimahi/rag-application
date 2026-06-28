'use client'

import { useMemo, useState } from 'react'

interface Props {
  columns: string[]
  rows: unknown[][]
  truncated: boolean
  row_count: number
  total_row_count: number
}

const PAGE_SIZE = 25

function isNumericColumn(colIdx: number, rows: unknown[][]): boolean {
  const nonNullVals = rows
    .map((row) => row[colIdx])
    .filter((v) => v !== null && v !== undefined && v !== '')
  if (nonNullVals.length === 0) return false
  return nonNullVals.every((v) => !isNaN(Number(v)))
}

function formatCellValue(value: unknown): string {
  if (typeof value !== 'number') return String(value)
  if (Number.isInteger(value)) {
    return value.toLocaleString('en-US')
  }
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

function buildCsv(columns: string[], rows: unknown[][]): string {
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"`
      : s
  }
  return [columns.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\n')
}

export default function DataTable({ columns, rows, truncated, row_count, total_row_count }: Props) {
  const [page, setPage] = useState(1)

  const numericCols = useMemo(
    () => columns.map((_, i) => isNumericColumn(i, rows)),
    [columns, rows],
  )

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function downloadCsv() {
    const csv = buildCsv(columns, rows)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const ts = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    a.download = `data_results_${ts}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (rows.length === 0) {
    return <div className="data-table-empty">No results returned for this query.</div>
  }

  return (
    <div className="data-table-wrapper">
      {truncated && (
        <div className="data-table-truncation-warning">
          ⚠️ Showing first 500 of {total_row_count.toLocaleString()} rows
        </div>
      )}

      <div className="data-table-toolbar">
        <span className="data-table-row-label">{row_count.toLocaleString()} rows</span>
        <button className="data-table-download-btn" onClick={downloadCsv}>
          ⬇️ Download CSV
        </button>
      </div>

      <div className="data-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th key={i} style={{ textAlign: numericCols[i] ? 'right' : 'left' }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, ri) => (
              <tr key={ri}>
                {(row as unknown[]).map((cell, ci) => (
                  <td key={ci} style={{ textAlign: numericCols[ci] ? 'right' : 'left' }}>
                    {cell === null || cell === undefined ? (
                      <span className="data-table-null">null</span>
                    ) : (
                      formatCellValue(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="data-table-pagination">
          <button
            className="data-table-page-btn"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span className="data-table-page-indicator">
            Page {page} of {totalPages}
          </span>
          <button
            className="data-table-page-btn"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
