import Link from 'next/link'
import DataSourcesPanel from '@/components/data-sources/DataSourcesPanel'

export default function DataSourcesPage() {
  return (
    <div className="docs-page">
      <div className="docs-page-header">
        <Link href="/chat" className="docs-back-link">
          <BackIcon />
          Back to Chat
        </Link>
        <h1 className="docs-page-title">Data Sources</h1>
        <p className="docs-page-subtitle">
          Upload data files or connect external databases and APIs for analysis.
        </p>
      </div>
      <div className="docs-page-body ds-page-body">
        <DataSourcesPanel />
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
