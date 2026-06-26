'use client'

import { useState } from 'react'

interface RateLimitBannerProps {
  error_type: 'rate_limit' | 'provider_error'
  provider?: string
  message: string
  onDismiss: () => void
}

export default function RateLimitBanner({ error_type, provider, message, onDismiss }: RateLimitBannerProps) {
  const [expanded, setExpanded] = useState(false)
  const isWarning = error_type === 'rate_limit'

  return (
    <div className={isWarning ? 'rate-limit-banner' : 'provider-error-banner'} role="alert">
      <span className="rate-limit-banner-icon" aria-hidden="true">⚠️</span>

      <div className="rate-limit-banner-content">
        <div className="rate-limit-banner-title">
          {isWarning ? 'AI Provider Limit Reached' : 'AI Provider Error'}
        </div>
        <div className="rate-limit-banner-subtitle">{message}</div>

        {isWarning && (
          <>
            <button
              className="rate-limit-expand-btn"
              onClick={() => setExpanded((v) => !v)}
              aria-expanded={expanded}
            >
              What can I do? {expanded ? '▴' : '▾'}
            </button>
            <div className={`rate-limit-expand${expanded ? ' open' : ''}`}>
              <div className="rate-limit-expand-box">
                <p>Your AI provider ({provider ?? 'unknown'}) has reached its daily free limit.</p>
                <br />
                <p>Options:</p>
                <ul>
                  <li>Wait until midnight UTC — quota resets daily</li>
                  <li>Contact your administrator to switch the AI provider</li>
                  <li>Current provider: {provider ?? 'unknown'}</li>
                </ul>
              </div>
            </div>
          </>
        )}
      </div>

      <button className="rate-limit-dismiss" onClick={onDismiss} aria-label="Dismiss">
        ✕
      </button>
    </div>
  )
}
