'use client'

import { useState } from 'react'

interface Props {
  sql: string
}

export default function SqlDisplay({ sql }: Props) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard unavailable
    }
  }

  return (
    <div className="sql-display">
      <button className="sql-display-toggle" onClick={() => setOpen((o) => !o)}>
        🔍 {open ? 'Hide SQL Query' : 'View SQL Query'}
      </button>
      {open && (
        <div className="sql-display-body">
          <button className="sql-display-copy" onClick={handleCopy}>
            {copied ? '✓ Copied' : '⎘ Copy'}
          </button>
          <pre className="sql-display-pre">{sql}</pre>
        </div>
      )}
    </div>
  )
}
