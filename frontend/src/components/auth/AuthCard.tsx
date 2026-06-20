'use client'

import type { CSSProperties, ReactNode } from 'react'

interface AuthCardProps {
  title: string
  subtitle?: string
  children: ReactNode
}

const cardStyle: CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius)',
  boxShadow: 'var(--shadow-card)',
  padding: '2rem',
  width: '100%',
  maxWidth: '400px',
}

const titleStyle: CSSProperties = {
  fontSize: '1.25rem',
  fontWeight: 600,
  color: 'var(--color-text)',
  marginBottom: '0.25rem',
}

const subtitleStyle: CSSProperties = {
  fontSize: '0.875rem',
  color: 'var(--color-text-muted)',
  marginBottom: '1.5rem',
}

export function AuthCard({ title, subtitle, children }: AuthCardProps) {
  return (
    <div style={cardStyle}>
      <h2 style={titleStyle}>{title}</h2>
      {subtitle && <p style={subtitleStyle}>{subtitle}</p>}
      {children}
    </div>
  )
}

interface FieldProps {
  label: string
  id: string
  type?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  autoComplete?: string
  disabled?: boolean
}

export function Field({
  label,
  id,
  type = 'text',
  value,
  onChange,
  placeholder,
  autoComplete,
  disabled,
}: FieldProps) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <label
        htmlFor={id}
        style={{
          display: 'block',
          fontSize: '0.875rem',
          fontWeight: 500,
          marginBottom: '0.375rem',
          color: 'var(--color-text)',
        }}
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        style={{
          display: 'block',
          width: '100%',
          padding: '0.5rem 0.75rem',
          fontSize: '0.9375rem',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          outline: 'none',
          background: disabled ? 'var(--color-bg)' : 'var(--color-surface)',
          color: 'var(--color-text)',
          transition: 'border-color 0.15s',
        }}
        onFocus={(e) => (e.target.style.borderColor = 'var(--color-border-focus)')}
        onBlur={(e) => (e.target.style.borderColor = 'var(--color-border)')}
      />
    </div>
  )
}

interface SubmitButtonProps {
  label: string
  loading?: boolean
  disabled?: boolean
}

export function SubmitButton({ label, loading, disabled }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={disabled || loading}
      style={{
        display: 'block',
        width: '100%',
        padding: '0.625rem 1rem',
        fontSize: '0.9375rem',
        fontWeight: 500,
        background: disabled || loading ? '#93c5fd' : 'var(--color-primary)',
        color: '#fff',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        marginTop: '0.25rem',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => {
        if (!disabled && !loading)
          (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-primary-hover)'
      }}
      onMouseLeave={(e) => {
        if (!disabled && !loading)
          (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-primary)'
      }}
    >
      {loading ? 'Please wait…' : label}
    </button>
  )
}

interface AlertProps {
  type: 'error' | 'success'
  message: string
}

export function Alert({ type, message }: AlertProps) {
  return (
    <div
      role="alert"
      style={{
        padding: '0.625rem 0.875rem',
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.875rem',
        marginBottom: '1rem',
        background: type === 'error' ? 'var(--color-error-bg)' : 'var(--color-success-bg)',
        color: type === 'error' ? 'var(--color-error)' : 'var(--color-success)',
        border: `1px solid ${type === 'error' ? '#fecaca' : '#bbf7d0'}`,
      }}
    >
      {message}
    </div>
  )
}
