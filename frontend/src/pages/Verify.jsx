import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { setToken } from '@/api/client'
import apiFetch from '@/api/client'

export default function Verify() {
  const [params]   = useSearchParams()
  const navigate   = useNavigate()
  const [status, setStatus] = useState('loading') // loading | success | error
  const [error, setError]   = useState(null)

  useEffect(() => {
    const token = params.get('token')
    if (!token) { setStatus('error'); setError('Missing verification token'); return }

    apiFetch(`/api/v1/auth/verify?token=${encodeURIComponent(token)}`)
      .then(res => {
        setToken(res.access_token)
        localStorage.setItem('qs_user', JSON.stringify({ user_id: res.user_id, name: res.name }))
        setStatus('success')
        setTimeout(() => navigate('/'), 2000)
      })
      .catch(err => {
        setStatus('error')
        setError('This link is invalid or has already been used.')
      })
  }, [])

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-card border border-border rounded-xl p-8 text-center space-y-4">
        {status === 'loading' && (
          <>
            <div className="text-3xl animate-pulse">⏳</div>
            <p className="text-muted-foreground text-sm">Verifying your email…</p>
          </>
        )}
        {status === 'success' && (
          <>
            <div className="text-3xl">✅</div>
            <h3 className="font-semibold">Email verified!</h3>
            <p className="text-sm text-muted-foreground">Redirecting you to the app…</p>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="text-3xl">❌</div>
            <h3 className="font-semibold">Verification failed</h3>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Link to="/register" className="text-sm text-primary hover:underline block">
              Register again
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
