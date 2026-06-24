'use client'

import { useState } from 'react'
import DataFilesTab from './DataFilesTab'
import ConnectionsTab from './ConnectionsTab'

type Tab = 'files' | 'connections'

export default function DataSourcesPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('files')

  return (
    <div className="ds-panel">
      {/* Tab bar */}
      <div className="ds-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === 'files'}
          className={`ds-tab${activeTab === 'files' ? ' active' : ''}`}
          onClick={() => setActiveTab('files')}
        >
          📁 Data Files
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'connections'}
          className={`ds-tab${activeTab === 'connections' ? ' active' : ''}`}
          onClick={() => setActiveTab('connections')}
        >
          🔌 Connections
        </button>
      </div>

      {/* Tab content */}
      <div className="ds-tab-content">
        {activeTab === 'files' ? <DataFilesTab /> : <ConnectionsTab />}
      </div>
    </div>
  )
}
