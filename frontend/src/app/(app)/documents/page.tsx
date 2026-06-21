import Link from 'next/link'
import DocumentsPanel from '@/components/documents/DocumentsPanel'

export default function DocumentsPage() {
  return (
    <div className="docs-page">
      <div className="docs-page-header">
        <Link href="/chat" className="docs-back-link">
          <BackIcon />
          Back to Chat
        </Link>
        <h1 className="docs-page-title">Documents</h1>
        <p className="docs-page-subtitle">
          Upload documents to use as context in your chats. Supported formats: PDF, DOCX, TXT, MD.
        </p>
      </div>
      <div className="docs-page-body">
        <DocumentsPanel />
      </div>
    </div>
  )
}

function BackIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}
