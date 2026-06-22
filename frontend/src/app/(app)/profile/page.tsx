'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { API_URL, usersApi } from '@/lib/api/client'
import type { User } from '@/lib/types'

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null)
  const [loadError, setLoadError] = useState('')

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

  useEffect(() => {
    usersApi.me()
      .then(setUser)
      .catch((err) => setLoadError(err instanceof Error ? err.message : 'Failed to load profile'))
  }, [])

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
