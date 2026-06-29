'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import { API_URL, chatApi, usersApi } from '@/lib/api/client'
import type { User, UserStats } from '@/lib/types'
import { showToast } from '@/components/Toast'

export default function ProfilePage() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [loadError, setLoadError] = useState('')
  const [stats, setStats] = useState<UserStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)

  // Theme state
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  // Name edit state
  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState('')
  const [nameSaving, setNameSaving] = useState(false)
  const [nameError, setNameError] = useState('')

  // Avatar state
  const [avatarVersion, setAvatarVersion] = useState(0)
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [avatarError, setAvatarError] = useState('')
  const avatarInputRef = useRef<HTMLInputElement>(null)

  // Delete all chats state
  const [showDeleteChatsDialog, setShowDeleteChatsDialog] = useState(false)
  const [deleteChatsPassword, setDeleteChatsPassword] = useState('')
  const [deleteChatsError, setDeleteChatsError] = useState('')
  const [deleteChatsLoading, setDeleteChatsLoading] = useState(false)

  // Delete account state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)

  // Password change state
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState('')

  useEffect(() => {
    usersApi.me()
      .then(setUser)
      .catch((err) => setLoadError(err instanceof Error ? err.message : 'Failed to load profile'))

    usersApi.stats()
      .then(setStats)
      .catch(() => setStats({
        documents_count: 0, total_chunks: 0, responses_generated: 0,
        total_input_tokens: 0, total_output_tokens: 0, total_tokens: 0,
      }))
      .finally(() => setStatsLoading(false))

    const t = document.documentElement.getAttribute('data-theme')
    if (t === 'dark' || t === 'light') setTheme(t)
  }, [])

  function applyTheme(next: 'light' | 'dark') {
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('theme', next)
  }

  function startEditName() {
    if (!user) return
    setNameValue(user.name)
    setNameError('')
    setEditingName(true)
  }

  function cancelEditName() {
    setEditingName(false)
    setNameError('')
  }

  async function saveName() {
    if (!nameValue.trim()) {
      setNameError('Name cannot be empty')
      return
    }
    setNameSaving(true)
    setNameError('')
    try {
      const updated = await usersApi.updateName(nameValue.trim())
      setUser(updated)
      setEditingName(false)
    } catch (err) {
      setNameError(err instanceof Error ? err.message : 'Failed to save name')
    } finally {
      setNameSaving(false)
    }
  }

  function handleNameKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') saveName()
    if (e.key === 'Escape') cancelEditName()
  }

  async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setAvatarError('Only JPEG, PNG, and WebP images are supported')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setAvatarError('Image must be 5 MB or smaller')
      return
    }
    setAvatarError('')
    setAvatarUploading(true)
    try {
      const updated = await usersApi.uploadAvatar(file)
      setUser(updated)
      setAvatarVersion((v) => v + 1)
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setAvatarUploading(false)
      if (avatarInputRef.current) avatarInputRef.current.value = ''
    }
  }

  async function handleDeleteAllChats(e: React.FormEvent) {
    e.preventDefault()
    setDeleteChatsError('')
    if (!deleteChatsPassword) {
      setDeleteChatsError('Password is required')
      return
    }
    setDeleteChatsLoading(true)
    try {
      const result = await chatApi.deleteAllChats(deleteChatsPassword)
      setShowDeleteChatsDialog(false)
      setDeleteChatsPassword('')
      showToast(`Deleted ${result.deleted_count} chat${result.deleted_count !== 1 ? 's' : ''}`, 'success')
    } catch (err) {
      setDeleteChatsError(err instanceof Error ? err.message : 'Failed to delete chats')
    } finally {
      setDeleteChatsLoading(false)
    }
  }

  async function handleDeleteAccount(e: React.FormEvent) {
    e.preventDefault()
    setDeleteError('')
    if (!deletePassword) {
      setDeleteError('Password is required')
      return
    }
    setDeleteLoading(true)
    try {
      await usersApi.deleteAccount(deletePassword)
      router.push('/login')
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete account')
    } finally {
      setDeleteLoading(false)
    }
  }

  function cancelPasswordForm() {
    setShowPasswordForm(false)
    setCurrentPassword('')
    setNewPassword('')
    setConfirmNewPassword('')
    setPasswordError('')
    setPasswordSuccess('')
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault()
    setPasswordError('')
    setPasswordSuccess('')
    if (!currentPassword || !newPassword || !confirmNewPassword) {
      setPasswordError('All fields are required')
      return
    }
    if (newPassword !== confirmNewPassword) {
      setPasswordError('New passwords do not match')
      return
    }
    setPasswordSaving(true)
    try {
      const result = await usersApi.changePassword(currentPassword, newPassword, confirmNewPassword)
      setPasswordSuccess(result.message)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmNewPassword('')
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : 'Failed to change password')
    } finally {
      setPasswordSaving(false)
    }
  }

  if (loadError) {
    return (
      <div className="profile-page">
        <div className="profile-page-header">
          <BackLink />
          <h1 className="profile-title">Profile</h1>
        </div>
        <p style={{ color: 'var(--color-error)', padding: '2rem' }}>{loadError}</p>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="profile-page">
        <div className="profile-page-header">
          <BackLink />
          <h1 className="profile-title">Profile</h1>
        </div>
        <p style={{ color: 'var(--color-text-muted)', padding: '2rem' }}>Loading…</p>
      </div>
    )
  }

  const avatarSrc = user.profile_picture_url
    ? `${API_URL}${user.profile_picture_url}?v=${avatarVersion}`
    : null
  const initials = user.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  function fmtTokens(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return String(n)
  }

  return (
    <div className="profile-page">
      <div className="profile-page-header">
        <BackLink />
        <h1 className="profile-title">Profile</h1>
      </div>

      <div className="profile-card">
        {/* Avatar section */}
        <div className="profile-avatar-section">
          <div className="profile-avatar-wrap">
            {avatarSrc ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatarSrc}
                alt="Profile picture"
                className="profile-avatar-img"
                crossOrigin="use-credentials"
              />
            ) : (
              <div className="profile-avatar-placeholder">{initials}</div>
            )}
            {avatarUploading && <div className="profile-avatar-overlay"><span className="docs-spinner" /></div>}
          </div>

          <input
            ref={avatarInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={handleAvatarChange}
          />
          <button
            className="profile-avatar-btn"
            onClick={() => avatarInputRef.current?.click()}
            disabled={avatarUploading}
          >
            {avatarUploading ? 'Uploading…' : 'Change photo'}
          </button>
          {avatarError && <p className="profile-field-error">{avatarError}</p>}
        </div>

        {/* Name field */}
        <div className="profile-field">
          <label className="profile-field-label">Name</label>
          {editingName ? (
            <div className="profile-field-edit">
              <input
                className="profile-field-input"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onKeyDown={handleNameKeyDown}
                autoFocus
                disabled={nameSaving}
              />
              {nameError && <p className="profile-field-error">{nameError}</p>}
              <div className="profile-field-actions">
                <button className="msg-action-btn" onClick={cancelEditName} disabled={nameSaving}>
                  Cancel
                </button>
                <button className="msg-action-btn primary" onClick={saveName} disabled={nameSaving}>
                  {nameSaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          ) : (
            <div className="profile-field-row">
              <span className="profile-field-value">{user.name}</span>
              <button className="profile-edit-btn" onClick={startEditName}>Edit</button>
            </div>
          )}
        </div>

        {/* Email field (read-only) */}
        <div className="profile-field">
          <label className="profile-field-label">Email</label>
          <div className="profile-field-row">
            <span className="profile-field-value">{user.email}</span>
            <span className="profile-field-readonly-note">Cannot be changed</span>
          </div>
        </div>

        {/* Stats section */}
        <div className="profile-field">
          <label className="profile-field-label">Usage</label>
          {statsLoading ? (
            <div className="profile-stats-grid">
              <div className="skeleton skeleton-stat" />
              <div className="skeleton skeleton-stat" />
              <div className="skeleton skeleton-stat" />
              <div className="skeleton skeleton-stat" />
              <div className="skeleton skeleton-stat" />
              <div className="skeleton skeleton-stat" />
            </div>
          ) : (
            <div className="profile-stats-grid">
              <div className="profile-stat-card">
                <span className="profile-stat-value">{stats?.documents_count ?? 0}</span>
                <span className="profile-stat-label">📄 Documents</span>
              </div>
              <div className="profile-stat-card">
                <span className="profile-stat-value">{stats?.total_chunks ?? 0}</span>
                <span className="profile-stat-label">🧩 Chunks indexed</span>
              </div>
              <div className="profile-stat-card">
                <span className="profile-stat-value">{stats?.responses_generated ?? 0}</span>
                <span className="profile-stat-label">💬 Responses</span>
              </div>
              <div className="profile-stat-card">
                <span className="profile-stat-value">{fmtTokens(stats?.total_input_tokens ?? 0)}</span>
                <span className="profile-stat-label">⬆ Input tokens</span>
              </div>
              <div className="profile-stat-card">
                <span className="profile-stat-value">{fmtTokens(stats?.total_output_tokens ?? 0)}</span>
                <span className="profile-stat-label">⬇ Output tokens</span>
              </div>
              <div className="profile-stat-card">
                <span className="profile-stat-value">{fmtTokens(stats?.total_tokens ?? 0)}</span>
                <span className="profile-stat-label">🔢 Total tokens</span>
              </div>
            </div>
          )}
        </div>

        {/* Appearance section */}
        <div className="profile-field">
          <label className="profile-field-label">Appearance</label>
          <div className="profile-theme-row">
            <button
              className={`profile-theme-card${theme === 'light' ? ' active' : ''}`}
              onClick={() => applyTheme('light')}
              type="button"
            >
              <span style={{ fontSize: '1.25rem' }}>☀️</span>
              <span>Light</span>
              {theme === 'light' && <span className="profile-theme-check">✓</span>}
            </button>
            <button
              className={`profile-theme-card${theme === 'dark' ? ' active' : ''}`}
              onClick={() => applyTheme('dark')}
              type="button"
            >
              <span style={{ fontSize: '1.25rem' }}>🌙</span>
              <span>Dark</span>
              {theme === 'dark' && <span className="profile-theme-check">✓</span>}
            </button>
          </div>
        </div>

        {/* Password section */}
        <div className="profile-field">
          <label className="profile-field-label">Password</label>
          {!showPasswordForm ? (
            <div className="profile-field-row">
              <span className="profile-field-value" style={{ color: 'var(--color-text-muted)' }}>
                ••••••••
              </span>
              <button className="profile-edit-btn" onClick={() => setShowPasswordForm(true)}>
                Change
              </button>
            </div>
          ) : (
            <form className="profile-password-form" onSubmit={savePassword}>
              <input
                className="profile-field-input"
                type="password"
                placeholder="Current password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                disabled={passwordSaving}
                autoComplete="current-password"
              />
              <input
                className="profile-field-input"
                type="password"
                placeholder="New password (8+ chars, upper, lower, digit)"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                disabled={passwordSaving}
                autoComplete="new-password"
              />
              <input
                className="profile-field-input"
                type="password"
                placeholder="Confirm new password"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                disabled={passwordSaving}
                autoComplete="new-password"
              />
              {passwordError && <p className="profile-field-error">{passwordError}</p>}
              {passwordSuccess && (
                <p className="profile-field-success">{passwordSuccess}</p>
              )}
              <div className="profile-field-actions">
                <button
                  type="button"
                  className="msg-action-btn"
                  onClick={cancelPasswordForm}
                  disabled={passwordSaving}
                >
                  Cancel
                </button>
                <button type="submit" className="msg-action-btn primary" disabled={passwordSaving}>
                  {passwordSaving ? 'Saving…' : 'Update password'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Danger zone */}
      <div className="profile-card" style={{ borderColor: 'var(--color-error)', marginTop: '1.5rem' }}>
        <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--color-error)', marginBottom: '1rem' }}>
          Danger zone
        </h2>

        {/* Delete all chats */}
        <div style={{ marginBottom: '1.25rem', paddingBottom: '1.25rem', borderBottom: '1px solid var(--color-border)' }}>
          {!showDeleteChatsDialog ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
              <div>
                <p style={{ fontSize: '0.875rem', fontWeight: 500, margin: 0 }}>Delete all chats</p>
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '0.25rem 0 0' }}>
                  Delete all non-pinned conversations. Pinned threads are kept.
                </p>
              </div>
              <button
                className="msg-action-btn"
                style={{ color: 'var(--color-error)', borderColor: 'var(--color-error)', whiteSpace: 'nowrap' }}
                onClick={() => { setShowDeleteChatsDialog(true); setDeleteChatsError('') }}
              >
                Delete all chats
              </button>
            </div>
          ) : (
            <form onSubmit={handleDeleteAllChats}>
              <p style={{ fontSize: '0.875rem', marginBottom: '0.75rem', color: 'var(--color-text-muted)' }}>
                Enter your password to confirm deletion of all non-pinned chats.
              </p>
              <input
                className="profile-field-input"
                type="password"
                placeholder="Your current password"
                value={deleteChatsPassword}
                onChange={(e) => setDeleteChatsPassword(e.target.value)}
                disabled={deleteChatsLoading}
                autoComplete="current-password"
                autoFocus
              />
              {deleteChatsError && <p className="profile-field-error" style={{ marginTop: '0.5rem' }}>{deleteChatsError}</p>}
              <div className="profile-field-actions" style={{ marginTop: '0.75rem' }}>
                <button
                  type="button"
                  className="msg-action-btn"
                  onClick={() => { setShowDeleteChatsDialog(false); setDeleteChatsPassword(''); setDeleteChatsError('') }}
                  disabled={deleteChatsLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="msg-action-btn"
                  style={{ color: '#fff', background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
                  disabled={deleteChatsLoading}
                >
                  {deleteChatsLoading ? 'Deleting…' : 'Yes, delete all chats'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Delete account */}
        {!showDeleteDialog ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
            <div>
              <p style={{ fontSize: '0.875rem', fontWeight: 500, margin: 0 }}>Delete account</p>
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '0.25rem 0 0' }}>
                Permanently remove your account and all data. This cannot be undone.
              </p>
            </div>
            <button
              className="msg-action-btn"
              style={{ color: 'var(--color-error)', borderColor: 'var(--color-error)', whiteSpace: 'nowrap' }}
              onClick={() => { setShowDeleteDialog(true); setDeleteError('') }}
            >
              Delete account
            </button>
          </div>
        ) : (
          <form onSubmit={handleDeleteAccount}>
            <p style={{ fontSize: '0.875rem', marginBottom: '0.75rem', color: 'var(--color-text-muted)' }}>
              Enter your password to confirm. <strong style={{ color: 'inherit' }}>This will permanently delete all your data.</strong>
            </p>
            <input
              className="profile-field-input"
              type="password"
              placeholder="Your current password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              disabled={deleteLoading}
              autoComplete="current-password"
              autoFocus
            />
            {deleteError && <p className="profile-field-error" style={{ marginTop: '0.5rem' }}>{deleteError}</p>}
            <div className="profile-field-actions" style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="msg-action-btn"
                onClick={() => { setShowDeleteDialog(false); setDeletePassword(''); setDeleteError('') }}
                disabled={deleteLoading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="msg-action-btn"
                style={{ color: '#fff', background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
                disabled={deleteLoading}
              >
                {deleteLoading ? 'Deleting…' : 'Yes, delete my account'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function BackLink() {
  return (
    <Link href="/chat" className="docs-back-link">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <polyline points="15 18 9 12 15 6" />
      </svg>
      Back to Chat
    </Link>
  )
}
