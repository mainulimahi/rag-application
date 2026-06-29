'use client'

import { useEffect, useRef, useState } from 'react'
import { dataSourcesApi } from '@/lib/api/client'
import type { DataSource, DataSourceType } from '@/lib/types'

const SOURCE_TYPES: { value: DataSourceType; label: string }[] = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'sqlite', label: 'SQLite' },
  { value: 's3', label: 'Amazon S3' },
  { value: 'gcs', label: 'Google Cloud Storage' },
  { value: 'azure_blob', label: 'Azure Blob Storage' },
  { value: 'api', label: 'REST API' },
]

interface Props {
  source: DataSource | null  // null = create mode
  onSave: (source: DataSource) => void
  onClose: () => void
}

export default function ConnectionModal({ source, onSave, onClose }: Props) {
  const [name, setName] = useState(source?.name ?? '')
  const [sourceType, setSourceType] = useState<DataSourceType>(source?.source_type ?? 'postgresql')
  const [config, setConfig] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nameRef = useRef<HTMLInputElement>(null)

  // When editing, pre-fill config fields with placeholder for password fields
  useEffect(() => {
    if (source) {
      const defaultConfig = getDefaultConfig(source.source_type)
      // Start with empty strings — password fields show placeholder "••••••••"
      setConfig(defaultConfig)
    } else {
      setConfig(getDefaultConfig(sourceType))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Reset config when source type changes (create mode only)
  useEffect(() => {
    if (!source) {
      setConfig(getDefaultConfig(sourceType))
    }
  }, [sourceType]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setTimeout(() => nameRef.current?.focus(), 50)
  }, [])

  function setField(key: string, value: string) {
    setConfig((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required'); return }
    setError(null)
    setSaving(true)

    // Build final config: in edit mode, omit blank password fields (server keeps old value)
    const finalConfig: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(config)) {
      if (source && isPasswordField(k) && v === '') continue  // unchanged password
      if (v !== '') finalConfig[k] = v
    }

    try {
      let saved: DataSource
      if (source) {
        saved = await dataSourcesApi.update(source.id, {
          name: name.trim(),
          connection_config: finalConfig as Record<string, unknown>,
        })
      } else {
        saved = await dataSourcesApi.create({
          name: name.trim(),
          source_type: sourceType,
          connection_config: finalConfig as Record<string, unknown>,
        })
      }
      onSave(saved)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  // Close on Escape or backdrop click
  function handleBackdrop(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose()
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="ds-modal-backdrop" onClick={handleBackdrop} role="dialog" aria-modal="true" aria-labelledby="conn-modal-title">
      <div className="ds-modal">
        <div className="ds-modal-header">
          <h2 id="conn-modal-title" className="ds-modal-title">{source ? 'Edit Connection' : 'Add Connection'}</h2>
          <button className="ds-modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <form className="ds-modal-body" onSubmit={handleSubmit}>
          {/* Name */}
          <div className="ds-field">
            <label className="ds-label" htmlFor="conn-name">Name <span className="ds-required">*</span></label>
            <input
              ref={nameRef}
              id="conn-name"
              className="ds-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Database"
              required
            />
          </div>

          {/* Source type — read-only in edit mode */}
          {!source && (
            <div className="ds-field">
              <label className="ds-label" htmlFor="conn-type">Source Type</label>
              <select
                id="conn-type"
                className="ds-input ds-select"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as DataSourceType)}
              >
                {SOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          )}

          {/* Dynamic config fields */}
          <ConfigFields
            sourceType={source?.source_type ?? sourceType}
            config={config}
            onChange={setField}
            isEdit={!!source}
          />

          {error && <p className="ds-modal-error">{error}</p>}

          <div className="ds-modal-footer">
            <button type="button" className="ds-modal-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="ds-modal-save" disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Config fields per source type ─────────────────────────────────────────────

function ConfigFields({
  sourceType,
  config,
  onChange,
  isEdit,
}: {
  sourceType: DataSourceType
  config: Record<string, string>
  onChange: (key: string, value: string) => void
  isEdit: boolean
}) {
  const pwdPlaceholder = isEdit ? '••••••••' : ''

  function field(key: string, label: string, opts?: { type?: string; placeholder?: string; required?: boolean }) {
    const isPassword = opts?.type === 'password'
    return (
      <div className="ds-field" key={key}>
        <label className="ds-label" htmlFor={`cf-${key}`}>{label}{opts?.required !== false && <span className="ds-required"> *</span>}</label>
        <input
          id={`cf-${key}`}
          className="ds-input"
          type={opts?.type ?? 'text'}
          value={config[key] ?? ''}
          onChange={(e) => onChange(key, e.target.value)}
          placeholder={isPassword ? pwdPlaceholder : (opts?.placeholder ?? '')}
          required={!isEdit && opts?.required !== false}
          autoComplete={isPassword ? 'new-password' : undefined}
        />
      </div>
    )
  }

  function toggle(key: string, label: string) {
    return (
      <div className="ds-field ds-field-toggle" key={key}>
        <label className="ds-label ds-toggle-label" htmlFor={`cf-${key}`}>
          <input
            id={`cf-${key}`}
            type="checkbox"
            className="ds-checkbox"
            checked={config[key] === 'true'}
            onChange={(e) => onChange(key, String(e.target.checked))}
          />
          {label}
        </label>
      </div>
    )
  }

  if (sourceType === 'postgresql' || sourceType === 'mysql') {
    return (
      <>
        {field('host', 'Host')}
        {field('port', 'Port', { type: 'number', placeholder: sourceType === 'postgresql' ? '5432' : '3306' })}
        {field('database', 'Database')}
        {field('username', 'Username')}
        {field('password', 'Password', { type: 'password' })}
        {toggle('ssl', 'Use SSL')}
      </>
    )
  }

  if (sourceType === 'sqlite') {
    return field('file_path', 'File Path', { placeholder: '/data/mydb.sqlite' })
  }

  if (sourceType === 's3') {
    return (
      <>
        {field('bucket', 'Bucket')}
        {field('prefix', 'Prefix (optional)', { required: false, placeholder: 'data/' })}
        {field('region', 'Region', { placeholder: 'us-east-1' })}
        {field('access_key_id', 'Access Key ID')}
        {field('secret_access_key', 'Secret Access Key', { type: 'password' })}
      </>
    )
  }

  if (sourceType === 'gcs') {
    return (
      <>
        {field('bucket', 'Bucket')}
        {field('prefix', 'Prefix (optional)', { required: false })}
        <div className="ds-field" key="service_account_json">
          <label className="ds-label" htmlFor="cf-service_account_json">Service Account JSON <span className="ds-required">*</span></label>
          <textarea
            id="cf-service_account_json"
            className="ds-input ds-textarea"
            value={config['service_account_json'] ?? ''}
            onChange={(e) => onChange('service_account_json', e.target.value)}
            placeholder={isEdit ? '••••••••' : '{"type":"service_account",...}'}
            rows={4}
            required={!isEdit}
          />
        </div>
      </>
    )
  }

  if (sourceType === 'azure_blob') {
    return (
      <>
        {field('account_name', 'Account Name')}
        {field('account_key', 'Account Key', { type: 'password' })}
        {field('container', 'Container')}
        {field('prefix', 'Prefix (optional)', { required: false })}
      </>
    )
  }

  if (sourceType === 'api') {
    return (
      <>
        {field('base_url', 'Base URL', { placeholder: 'https://api.example.com/data' })}
        <div className="ds-field" key="auth_type">
          <label className="ds-label" htmlFor="cf-auth_type">Auth Type</label>
          <select
            id="cf-auth_type"
            className="ds-input ds-select"
            value={config['auth_type'] ?? 'none'}
            onChange={(e) => onChange('auth_type', e.target.value)}
          >
            <option value="none">None</option>
            <option value="bearer">Bearer Token</option>
            <option value="api_key">API Key</option>
          </select>
        </div>
        {(config['auth_type'] === 'bearer' || config['auth_type'] === 'api_key') && (
          field('auth_value', config['auth_type'] === 'bearer' ? 'Bearer Token' : 'API Key', { type: 'password' })
        )}
      </>
    )
  }

  return null
}

function isPasswordField(key: string): boolean {
  return ['password', 'secret_access_key', 'account_key', 'service_account_json', 'auth_value'].includes(key)
}

function getDefaultConfig(type: DataSourceType): Record<string, string> {
  switch (type) {
    case 'postgresql': return { host: '', port: '5432', database: '', username: '', password: '', ssl: 'false' }
    case 'mysql':      return { host: '', port: '3306', database: '', username: '', password: '', ssl: 'false' }
    case 'sqlite':     return { file_path: '' }
    case 's3':         return { bucket: '', prefix: '', region: '', access_key_id: '', secret_access_key: '' }
    case 'gcs':        return { bucket: '', prefix: '', service_account_json: '' }
    case 'azure_blob': return { account_name: '', account_key: '', container: '', prefix: '' }
    case 'api':        return { base_url: '', auth_type: 'none', auth_value: '' }
  }
}
