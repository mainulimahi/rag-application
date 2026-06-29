'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { dataFilesApi } from '@/lib/api/client'
import type { DataFile, DataFileSchemaColumn } from '@/lib/types'
import { showToast } from '@/components/Toast'


const ALLOWED_EXTENSIONS = ['.csv', '.tsv', '.parquet', '.xlsx', '.xls', '.json']
const MAX_SIZE_MB = 20

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function DataFilesTab() {
  const [files, setFiles] = useState<DataFile[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [schemaCache, setSchemaCache] = useState<Record<string, DataFileSchemaColumn[]>>({})
  const [schemaLoading, setSchemaLoading] = useState<Record<string, boolean>>({})

  const pollingRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadFiles = useCallback(async () => {
    try {
      const data = await dataFilesApi.list()
      setFiles(data)
      for (const f of data) {
        if (f.status === 'processing') startPolling(f.id)
      }
    } catch {
      showToast('Failed to load data files', 'error')
    } finally {
      setIsLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadFiles()
    return () => {
      for (const id of pollingRefs.current.values()) clearInterval(id)
    }
  }, [loadFiles])

  function startPolling(fileId: string) {
    if (pollingRefs.current.has(fileId)) return
    const handle = setInterval(async () => {
      try {
        const st = await dataFilesApi.getStatus(fileId)
        if (st.status !== 'processing') {
          clearInterval(pollingRefs.current.get(fileId))
          pollingRefs.current.delete(fileId)
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileId
                ? { ...f, status: st.status, processing_error: st.processing_error, row_count: st.row_count, column_count: st.column_count }
                : f,
            ),
          )
        }
      } catch {
        clearInterval(pollingRefs.current.get(fileId))
        pollingRefs.current.delete(fileId)
      }
    }, 3000)
    pollingRefs.current.set(fileId, handle)
  }

  function validateFile(file: File): string | null {
    const ext = '.' + (file.name.split('.').pop()?.toLowerCase() ?? '')
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported type "${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is ${MAX_SIZE_MB} MB.`
    }
    return null
  }

  async function handleUpload(file: File) {
    const err = validateFile(file)
    if (err) { setUploadError(err); return }
    setUploadError(null)
    setUploadingFile(file.name)
    try {
      const response = await dataFilesApi.upload(file)
      setFiles((prev) => [response, ...prev])
      startPolling(response.id)
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  async function handleToggleExpand(file: DataFile) {
    if (file.status !== 'ready') return
    if (expandedId === file.id) {
      setExpandedId(null)
      return
    }
    setExpandedId(file.id)
    if (schemaCache[file.id]) return
    setSchemaLoading((prev) => ({ ...prev, [file.id]: true }))
    try {
      const full = await dataFilesApi.getSchema(file.id)
      setSchemaCache((prev) => ({ ...prev, [file.id]: full.columns ?? [] }))
    } catch {
      showToast('Failed to load schema', 'error')
    } finally {
      setSchemaLoading((prev) => ({ ...prev, [file.id]: false }))
    }
  }

  async function handleDelete(file: DataFile) {
    if (!window.confirm(`Delete "${file.filename}"? This cannot be undone.`)) return
    try {
      await dataFilesApi.delete(file.id)
      clearInterval(pollingRefs.current.get(file.id))
      pollingRefs.current.delete(file.id)
      setFiles((prev) => prev.filter((f) => f.id !== file.id))
      if (expandedId === file.id) setExpandedId(null)
      showToast('File deleted', 'success')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed', 'error')
    }
  }

  return (
    <div className="ds-files-tab">
      {/* Drop zone */}
      <div
        className={`docs-dropzone${isDragging ? ' dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => { if (!uploadingFile) fileInputRef.current?.click() }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(',')}
          style={{ display: 'none' }}
          onChange={handleFileInputChange}
        />
        {uploadingFile ? (
          <p className="docs-dropzone-text">
            <span className="docs-spinner" /> Uploading <strong>{uploadingFile}</strong>…
          </p>
        ) : (
          <>
            <UploadIcon />
            <p className="docs-dropzone-text">
              Drag & drop a file here, or <span className="docs-dropzone-link">browse</span>
            </p>
            <p className="docs-dropzone-hint">CSV, TSV, Parquet, Excel, JSON — max 20 MB</p>
          </>
        )}
      </div>

      {uploadError && (
        <div className="docs-error" role="alert">
          {uploadError}
          <button className="docs-error-dismiss" onClick={() => setUploadError(null)}>×</button>
        </div>
      )}

      {/* File list */}
      <div className="ds-file-list">
        {isLoading ? (
          <p className="docs-list-empty">Loading…</p>
        ) : files.length === 0 ? (
          <p className="docs-list-empty">
            Upload a CSV, Excel, or Parquet file to start asking questions about your data
          </p>
        ) : (
          files.map((file) => (
            <div key={file.id} className="ds-file-card">
              {/* Main row */}
              <div
                className={`ds-file-row${file.status === 'ready' ? ' clickable' : ''}`}
                onClick={() => handleToggleExpand(file)}
              >
                <span className="ds-file-icon">{fileExt(file.filename)}</span>

                <div className="ds-file-info">
                  <span className="docs-item-name" title={file.filename}>{file.filename}</span>
                  <span className="docs-item-meta">
                    {formatBytes(file.file_size)} · {formatDate(file.uploaded_at)}
                    {file.status === 'ready' && ` · ${file.row_count?.toLocaleString() ?? 0} rows · ${file.column_count} cols`}
                  </span>
                  {file.status === 'failed' && file.processing_error && (
                    <span className="ds-file-error">{file.processing_error}</span>
                  )}
                </div>

                <StatusBadge status={file.status} error={file.processing_error} />

                {file.status === 'ready' && (
                  <span className="ds-expand-hint">{expandedId === file.id ? '▲' : '▼'}</span>
                )}

                <button
                  className="docs-delete-btn"
                  title="Delete file"
                  aria-label={`Delete ${file.filename}`}
                  onClick={(e) => { e.stopPropagation(); handleDelete(file) }}
                >
                  <TrashIcon />
                </button>
              </div>

              {/* Schema panel */}
              {expandedId === file.id && (
                <div className="ds-schema-panel">
                  {schemaLoading[file.id] ? (
                    <p className="ds-schema-loading"><span className="docs-spinner" /> Loading schema…</p>
                  ) : schemaCache[file.id]?.length ? (
                    <div className="ds-schema-table-wrap">
                      <table className="ds-schema-table">
                        <thead>
                          <tr>
                            <th>Column Name</th>
                            <th>Type</th>
                            <th>Sample Values</th>
                            <th>Nulls</th>
                            <th>Unique</th>
                          </tr>
                        </thead>
                        <tbody>
                          {schemaCache[file.id].map((col) => (
                            <tr key={col.column_name}>
                              <td className="ds-col-name">{col.column_name}</td>
                              <td><span className="ds-type-badge">{col.column_type}</span></td>
                              <td className="ds-samples">
                                {col.sample_values?.map(String).join(', ') ?? '—'}
                              </td>
                              <td>{col.null_count ?? '—'}</td>
                              <td>{col.unique_count ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="ds-schema-loading">No schema available</p>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status, error }: { status: string; error: string | null }) {
  if (status === 'processing') {
    return <span className="ds-status-badge processing"><span className="docs-spinner" /> Processing</span>
  }
  if (status === 'ready') {
    return <span className="ds-status-badge ready">Ready</span>
  }
  return (
    <span className="ds-status-badge failed">Failed</span>
  )
}

function fileExt(filename: string): string {
  return (filename.split('.').pop()?.toUpperCase() ?? 'FILE').slice(0, 4)
}

function UploadIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginBottom: '0.5rem', color: 'var(--color-text-muted)' }}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}
