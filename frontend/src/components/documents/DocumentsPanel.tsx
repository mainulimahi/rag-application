'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { documentApi } from '@/lib/api/client'
import type { DocumentListItem } from '@/lib/types'

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md']
const MAX_SIZE_MB = 20

export default function DocumentsPanel() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDragging, setIsDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState<string | null>(null)
  // Map of document_id → interval handle for status polling
  const pollingRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await documentApi.list()
      setDocuments(docs)
      // Resume polling for any documents still in 'processing' state
      for (const doc of docs) {
        if (doc.status === 'processing') {
          startPolling(doc.id)
        }
      }
    } catch (err) {
      console.error('Failed to load documents', err)
    } finally {
      setIsLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadDocuments()
    return () => {
      // Clear all polling intervals on unmount
      for (const id of pollingRefs.current.values()) clearInterval(id)
    }
  }, [loadDocuments])

  function startPolling(documentId: string) {
    if (pollingRefs.current.has(documentId)) return
    const handle = setInterval(async () => {
      try {
        const status = await documentApi.getStatus(documentId)
        if (status.status !== 'processing') {
          clearInterval(pollingRefs.current.get(documentId))
          pollingRefs.current.delete(documentId)
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === documentId
                ? {
                    ...d,
                    status: status.status,
                    processing_error: status.processing_error,
                    chunk_count: status.chunk_count,
                  }
                : d,
            ),
          )
        }
      } catch {
        clearInterval(pollingRefs.current.get(documentId))
        pollingRefs.current.delete(documentId)
      }
    }, 2500)
    pollingRefs.current.set(documentId, handle)
  }

  function validateFile(file: File): string | null {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file type "${ext}". Allowed: PDF, DOCX, TXT, MD`
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is ${MAX_SIZE_MB} MB.`
    }
    return null
  }

  async function handleUpload(file: File) {
    const error = validateFile(file)
    if (error) {
      setUploadError(error)
      return
    }
    setUploadError(null)
    setUploadingFile(file.name)

    try {
      const response = await documentApi.upload(file)
      const newDoc: DocumentListItem = {
        id: response.id,
        filename: response.filename,
        content_type: response.content_type,
        status: response.status,
        processing_error: null,
        chunk_count: 0,
        uploaded_at: response.uploaded_at,
      }
      setDocuments((prev) => [newDoc, ...prev])
      startPolling(response.id)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
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

  async function handleDelete(documentId: string, filename: string) {
    if (!window.confirm(`Delete "${filename}"? This cannot be undone.`)) return
    try {
      await documentApi.delete(documentId)
      clearInterval(pollingRefs.current.get(documentId))
      pollingRefs.current.delete(documentId)
      setDocuments((prev) => prev.filter((d) => d.id !== documentId))
    } catch (err) {
      console.error('Failed to delete document', err)
    }
  }

  return (
    <div className="docs-panel">
      {/* Drop zone */}
      <div
        className={`docs-dropzone${isDragging ? ' dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
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
            <p className="docs-dropzone-hint">PDF, DOCX, TXT, MD — max 20 MB</p>
          </>
        )}
      </div>

      {uploadError && (
        <div className="docs-error" role="alert">
          {uploadError}
          <button className="docs-error-dismiss" onClick={() => setUploadError(null)}>×</button>
        </div>
      )}

      {/* Document list */}
      <div className="docs-list">
        {isLoading ? (
          <p className="docs-list-empty">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="docs-list-empty">No documents uploaded yet.</p>
        ) : (
          documents.map((doc) => (
            <div key={doc.id} className="docs-list-item">
              <FileIcon contentType={doc.content_type} />
              <div className="docs-item-info">
                <span className="docs-item-name" title={doc.filename}>{doc.filename}</span>
                <span className="docs-item-meta">
                  {formatDate(doc.uploaded_at)}
                  {doc.status === 'ready' && ` · ${doc.chunk_count} chunk${doc.chunk_count !== 1 ? 's' : ''}`}
                </span>
                {doc.status === 'processing' && (
                  <span className="docs-status processing">
                    <span className="docs-spinner" /> Processing…
                  </span>
                )}
                {doc.status === 'failed' && (
                  <span className="docs-status failed" title={doc.processing_error ?? undefined}>
                    Failed — {doc.processing_error ?? 'unknown error'}
                  </span>
                )}
              </div>
              {doc.status === 'ready' && (
                <span className="docs-status ready">Ready</span>
              )}
              <button
                className="docs-delete-btn"
                title="Delete document"
                onClick={() => handleDelete(doc.id, doc.filename)}
                disabled={uploadingFile !== null}
              >
                <TrashIcon />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
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

function FileIcon({ contentType }: { contentType: string }) {
  const label = contentType.includes('pdf')
    ? 'PDF'
    : contentType.includes('word') || contentType.includes('docx')
    ? 'DOC'
    : 'TXT'
  return <span className="docs-file-icon">{label}</span>
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
