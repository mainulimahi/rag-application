'use client'

import { useCallback, useEffect, useState } from 'react'
import { dataSourcesApi } from '@/lib/api/client'
import type { DataSource, DataSourceType, TestConnectionResult } from '@/lib/types'
import { showToast } from '@/components/Toast'
import ConnectionModal from './ConnectionModal'

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const SOURCE_TYPE_LABELS: Record<DataSourceType, string> = {
  postgresql: 'PostgreSQL',
  mysql: 'MySQL',
  sqlite: 'SQLite',
  s3: 'Amazon S3',
  gcs: 'Google Cloud Storage',
  azure_blob: 'Azure Blob Storage',
  api: 'REST API',
}

const SOURCE_TYPE_COLORS: Record<DataSourceType, string> = {
  postgresql: 'ds-badge-blue',
  mysql: 'ds-badge-orange',
  sqlite: 'ds-badge-slate',
  s3: 'ds-badge-amber',
  gcs: 'ds-badge-red',
  azure_blob: 'ds-badge-teal',
  api: 'ds-badge-purple',
}

export default function ConnectionsTab() {
  const [sources, setSources] = useState<DataSource[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSource, setEditingSource] = useState<DataSource | null>(null)
  // Per-source test state: { [id]: { loading, result } }
  const [testState, setTestState] = useState<
    Record<string, { loading: boolean; result: TestConnectionResult | null }>
  >({})

  const loadSources = useCallback(async () => {
    try {
      const data = await dataSourcesApi.list()
      setSources(data)
    } catch (err) {
      console.error('Failed to load data sources', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { loadSources() }, [loadSources])

  async function handleTest(source: DataSource) {
    setTestState((prev) => ({ ...prev, [source.id]: { loading: true, result: null } }))
    try {
      const result = await dataSourcesApi.test(source.id)
      setTestState((prev) => ({ ...prev, [source.id]: { loading: false, result } }))
      // Update last_test_status locally to match
      setSources((prev) =>
        prev.map((s) =>
          s.id === source.id ? { ...s, last_test_status: result.status, last_tested_at: new Date().toISOString() } : s,
        ),
      )
    } catch (e) {
      const errResult: TestConnectionResult = {
        status: 'error',
        message: e instanceof Error ? e.message : 'Test failed',
      }
      setTestState((prev) => ({ ...prev, [source.id]: { loading: false, result: errResult } }))
    }
  }

  function handleEdit(source: DataSource) {
    setEditingSource(source)
    setModalOpen(true)
  }

  async function handleDelete(source: DataSource) {
    if (!window.confirm(`Delete "${source.name}"? This cannot be undone.`)) return
    try {
      await dataSourcesApi.delete(source.id)
      setSources((prev) => prev.filter((s) => s.id !== source.id))
      setTestState((prev) => { const n = { ...prev }; delete n[source.id]; return n })
      showToast('Connection deleted', 'success')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed', 'error')
    }
  }

  function handleModalClose() {
    setModalOpen(false)
    setEditingSource(null)
  }

  async function handleModalSave(source: DataSource) {
    setSources((prev) => {
      const exists = prev.find((s) => s.id === source.id)
      return exists ? prev.map((s) => (s.id === source.id ? source : s)) : [source, ...prev]
    })
    handleModalClose()
    showToast(editingSource ? 'Connection updated' : 'Connection created', 'success')
  }

  return (
    <div className="ds-connections-tab">
      {/* Header row */}
      <div className="ds-conn-header">
        <p className="ds-conn-count">
          {sources.length} connection{sources.length !== 1 ? 's' : ''}
        </p>
        <button className="ds-add-btn" onClick={() => setModalOpen(true)}>
          <PlusIcon /> Add Connection
        </button>
      </div>

      {/* Connection list */}
      <div className="ds-conn-list">
        {isLoading ? (
          <p className="docs-list-empty">Loading…</p>
        ) : sources.length === 0 ? (
          <p className="docs-list-empty">
            Connect a database or cloud storage to query your live data
          </p>
        ) : (
          sources.map((source) => {
            const ts = testState[source.id]
            return (
              <div key={source.id} className="ds-conn-card">
                <div className="ds-conn-row">
                  {/* Status dot */}
                  <span className={`ds-status-dot ${source.last_test_status === 'ok' ? 'ok' : source.last_test_status === 'error' ? 'err' : 'untested'}`} title={source.last_test_status ?? 'Untested'} />

                  {/* Name + meta */}
                  <div className="ds-conn-info">
                    <span className="ds-conn-name">{source.name}</span>
                    <span className="docs-item-meta">
                      Tested: {relativeTime(source.last_tested_at)}
                      {source.last_test_error && ` · ${source.last_test_error}`}
                    </span>
                  </div>

                  {/* Type badge */}
                  <span className={`ds-type-tag ${SOURCE_TYPE_COLORS[source.source_type as DataSourceType]}`}>
                    {SOURCE_TYPE_LABELS[source.source_type as DataSourceType] ?? source.source_type}
                  </span>

                  {/* Actions */}
                  <div className="ds-conn-actions">
                    <button
                      className="ds-conn-btn"
                      onClick={() => handleTest(source)}
                      disabled={ts?.loading}
                      title="Test connection"
                    >
                      {ts?.loading ? <span className="docs-spinner" /> : <PlayIcon />}
                      Test
                    </button>
                    <button className="ds-conn-btn" onClick={() => handleEdit(source)} title="Edit">
                      <PencilIcon />
                    </button>
                    <button className="ds-conn-btn danger" onClick={() => handleDelete(source)} title="Delete">
                      <TrashIcon />
                    </button>
                  </div>
                </div>

                {/* Test result */}
                {ts?.result && (
                  <div className={`ds-test-result ${ts.result.status}`}>
                    {ts.result.status === 'ok' ? <CheckIcon /> : <XIcon />}
                    <span>{ts.result.message}</span>
                    {ts.result.tables_found != null && (
                      <span className="ds-test-extra">· {ts.result.tables_found} table{ts.result.tables_found !== 1 ? 's' : ''} found</span>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Add / Edit modal */}
      {modalOpen && (
        <ConnectionModal
          source={editingSource}
          onSave={handleModalSave}
          onClose={handleModalClose}
        />
      )}
    </div>
  )
}

// ── Icons ──────────────────────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function PlayIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PencilIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
