import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Sidebar from '@/components/layout/Sidebar'
import Dashboard from '@/pages/Dashboard'
import Strength from '@/pages/Strength'
import Training from '@/pages/Training'
import Sleep from '@/pages/Sleep'
import Running from '@/pages/Running'
import CheckIn from '@/pages/CheckIn'
import Journal from '@/pages/Journal'
import Profile from '@/pages/Profile'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Verify from '@/pages/Verify'
import { triggerSync } from '@/api/sync'
import { fetchReadiness, saveReadiness } from '@/api/checkin'
import { clearToken } from '@/api/client'
import { Sun } from 'lucide-react'

// ── auth helpers ──────────────────────────────────────────────────────────────

function isLoggedIn() {
  return !!localStorage.getItem('qs_token')
}

function ProtectedRoute({ children }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />
  return children
}

// ── morning check-in gate ─────────────────────────────────────────────────────

function getToday() { return new Date().toLocaleDateString('en-CA') }

function shouldShowGate() {
  const h = new Date().getHours()
  return h >= 5 && h < 23
}

function SliderField({ label, value, onChange }) {
  const color = value >= 8 ? '#00cc7a' : value >= 5 ? '#fdcb6e' : '#ff6b6b'
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums" style={{ color }}>{value}/10</span>
      </div>
      <input type="range" min={1} max={10} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-primary" />
    </div>
  )
}

// Routes where the morning gate should never appear
const GATE_EXCLUDED = ['/profile']

function MorningGate() {
  const location = useLocation()
  const qc = useQueryClient()
  const today = getToday()
  const [vals, setVals]   = useState({ overall: 7, legs: 7, upper: 7, joints: 8 })
  const [injuryNote, setInjuryNote] = useState('')
  const [timeAvail, setTimeAvail]   = useState('medium')
  const [goingOut, setGoingOut]     = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['readiness', today],
    queryFn: async () => {
      try { return await fetchReadiness(today) }
      catch { return null }
    },
    staleTime: Infinity,
    retry: false,
  })

  const mut = useMutation({
    mutationFn: saveReadiness,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['readiness', today] }),
  })

  if (isLoading || data || !shouldShowGate() || GATE_EXCLUDED.includes(location.pathname)) return null

  function set(k, v) { setVals(p => ({ ...p, [k]: v })) }

  function submit(e) {
    e.preventDefault()
    mut.mutate({
      entry_date:        today,
      overall_feel:      vals.overall,
      legs_feel:         vals.legs,
      upper_body_feel:   vals.upper,
      joint_feel:        vals.joints,
      injury_note:       vals.joints <= 6 ? injuryNote || null : null,
      time_available:    timeAvail,
      going_out_tonight: goingOut,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-md">
        <div className="flex items-center gap-3 px-6 pt-5 pb-4 border-b border-border">
          <Sun size={18} className="text-yellow-400 shrink-0" />
          <div>
            <p className="font-semibold">Good morning!</p>
            <p className="text-sm text-muted-foreground">Complete today's check-in to get started.</p>
          </div>
        </div>

        <form onSubmit={submit} className="px-6 py-5 space-y-5">
          <SliderField label="Overall feel"    value={vals.overall} onChange={v => set('overall', v)} />
          <SliderField label="Legs"            value={vals.legs}    onChange={v => set('legs', v)} />
          <SliderField label="Upper body"      value={vals.upper}   onChange={v => set('upper', v)} />
          <SliderField label="Joints / injury" value={vals.joints}  onChange={v => set('joints', v)} />

          {vals.joints <= 6 && (
            <input type="text" value={injuryNote} onChange={e => setInjuryNote(e.target.value)}
              placeholder="What's bothering you? (e.g. left knee slight ache)"
              className="text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground w-full" />
          )}

          <div className="flex gap-6 flex-wrap">
            {['short', 'medium', 'long'].map(opt => (
              <label key={opt} className="flex items-center gap-2 cursor-pointer text-sm">
                <input type="radio" name="gate-time" value={opt}
                  checked={timeAvail === opt} onChange={() => setTimeAvail(opt)}
                  className="accent-primary" />
                {opt.charAt(0).toUpperCase() + opt.slice(1)} time
              </label>
            ))}
          </div>

          <label className="flex items-center gap-3 cursor-pointer text-sm">
            <input type="checkbox" checked={goingOut} onChange={e => setGoingOut(e.target.checked)}
              className="accent-primary w-4 h-4" />
            Going out tonight?
          </label>

          <button type="submit" disabled={mut.isPending}
            className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
            {mut.isPending ? 'Saving…' : 'Start Training Day'}
          </button>
          {mut.isError && <p className="text-xs text-red-400 text-center">Save failed — please try again.</p>}
        </form>
      </div>
    </div>
  )
}

// ── protected shell ───────────────────────────────────────────────────────────

function AppShell() {
  const queryClient = useQueryClient()

  useEffect(() => {
    triggerSync()
      .then(() => queryClient.invalidateQueries({ predicate: q => q.queryKey[0] !== 'me' }))
      .catch(() => {})
  }, [])

  return (
    <div className="flex min-h-screen bg-background">
      <MorningGate />
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/"         element={<Dashboard />} />
          <Route path="/strength" element={<Strength />} />
          <Route path="/training" element={<Training />} />
          <Route path="/sleep"    element={<Sleep />} />
          <Route path="/running"  element={<Running />} />
          <Route path="/checkin"  element={<CheckIn />} />
          <Route path="/journal"  element={<Journal />} />
          <Route path="/profile"  element={<Profile />} />
        </Routes>
      </main>
    </div>
  )
}

// ── root ──────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <Routes>
      <Route path="/login"    element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify"   element={<Verify />} />
      <Route path="/*" element={
        <ProtectedRoute>
          <AppShell />
        </ProtectedRoute>
      } />
    </Routes>
  )
}
