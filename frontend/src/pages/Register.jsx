import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { register } from '@/api/auth'
import SportPicker from '@/components/SportPicker'

const GOALS = [
  { key: 'athlete',     label: 'Multi-sport athlete' },
  { key: 'strength',    label: 'Strength' },
  { key: 'hypertrophy', label: 'Hypertrophy' },
]

function StepCredentials({ data, onChange, onNext }) {
  const [error, setError] = useState(null)

  function submit(e) {
    e.preventDefault()
    if (data.password.length < 6) { setError('Password must be at least 6 characters'); return }
    if (data.password !== data.confirm) { setError('Passwords do not match'); return }
    setError(null)
    onNext()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">Name</label>
        <input type="text" required value={data.name}
          onChange={e => onChange('name', e.target.value)}
          className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Email</label>
        <input type="email" required value={data.email}
          onChange={e => onChange('email', e.target.value)}
          className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Password</label>
        <input type="password" required value={data.password}
          onChange={e => onChange('password', e.target.value)}
          className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Confirm password</label>
        <input type="password" required value={data.confirm}
          onChange={e => onChange('confirm', e.target.value)}
          className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <button type="submit"
        className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition-opacity">
        Continue →
      </button>
      <p className="text-xs text-center text-muted-foreground">
        Have an account? <Link to="/login" className="text-primary hover:underline">Sign in</Link>
      </p>
    </form>
  )
}

function StepProfile({ data, onChange, onSubmit, loading, error }) {
  // Own state for sports so it never depends on parent render timing
  const [sports, setSports] = useState(() => ({ ...(data.primary_sports || {}) }))

  function handleSportsChange(updated) {
    setSports(updated)
    onChange('primary_sports', updated)
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {/* Goal */}
      <div className="space-y-1">
        <label className="text-sm font-medium">Training goal</label>
        <select value={data.goal} onChange={e => onChange('goal', e.target.value)}
          className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer">
          {GOALS.map(g => <option key={g.key} value={g.key}>{g.label}</option>)}
        </select>
      </div>

      {/* Gym days */}
      <div className="space-y-1">
        <label className="text-sm font-medium">Gym sessions per week</label>
        <select value={data.gym_days_week} onChange={e => onChange('gym_days_week', Number(e.target.value))}
          className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer">
          {[2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n} sessions</option>)}
        </select>
      </div>

      {/* Sports */}
      <div className="space-y-2">
        <div>
          <label className="text-sm font-medium">Active sports</label>
          <p className="text-xs text-muted-foreground mt-0.5">
            Check each sport you train. Set priority 1 (light) → 5 (primary focus).
          </p>
        </div>
        <SportPicker value={sports} onChange={handleSportsChange} />
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <button type="submit" disabled={loading}
        className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
        {loading ? 'Creating account…' : 'Create account'}
      </button>
    </form>
  )
}

export default function Register() {
  const navigate = useNavigate()
  const [step, setStep]       = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [data, setData]       = useState({
    name: '', email: '', password: '', confirm: '',
    goal: 'athlete', gym_days_week: 3, primary_sports: {},
  })

  function onChange(k, v) { setData(p => ({ ...p, [k]: v })) }

  async function submit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await register({
        name:           data.name,
        email:          data.email,
        password:       data.password,
        goal:           data.goal,
        gym_days_week:  data.gym_days_week,
        primary_sports: data.primary_sports,
      })
      setStep(3)
    } catch (err) {
      const msg = err.message.includes('400') ? 'Email already registered' : 'Registration failed — please try again'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background py-8 flex flex-col items-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">QuantifiedStrides</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {step === 1 ? 'Create your account' : step === 2 ? 'Set up your sport profile' : ''}
          </p>
          <div className="flex justify-center gap-2 mt-3">
            {[1, 2, 3].map(s => (
              <div key={s} className={`h-1 w-8 rounded-full transition-colors ${s <= step ? 'bg-primary' : 'bg-muted'}`} />
            ))}
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6">
          {step === 1 && <StepCredentials data={data} onChange={onChange} onNext={() => setStep(2)} />}
          {step === 2 && <StepProfile data={data} onChange={onChange} onSubmit={submit} loading={loading} error={error} />}
          {step === 3 && (
            <div className="text-center space-y-4 py-4">
              <div className="text-4xl">📬</div>
              <h3 className="font-semibold text-lg">Check your inbox</h3>
              <p className="text-sm text-muted-foreground">
                We sent a verification link to <strong>{data.email}</strong>.<br />
                Click the link to activate your account.
              </p>
              <Link to="/login" className="text-sm text-primary hover:underline block">
                Back to sign in
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
