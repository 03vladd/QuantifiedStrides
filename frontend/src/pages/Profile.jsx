import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'
import { getMe, updateMe, deleteMe } from '@/api/auth'
import { clearToken } from '@/api/client'
import SportPicker from '@/components/SportPicker'

const GOALS = [
  { key: 'athlete',     label: 'Multi-sport athlete' },
  { key: 'strength',    label: 'Strength' },
  { key: 'hypertrophy', label: 'Hypertrophy' },
]

export default function Profile() {
  const qc       = useQueryClient()
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({ queryKey: ['me'], queryFn: getMe })

  const [form, setForm]               = useState(null)
  const [showGarminPw, setShowGarminPw] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  // Only initialise once — never reset on background refetch
  useEffect(() => {
    if (!data || form !== null) return
    setForm({
      name:            data.name ?? '',
      goal:            data.goal ?? 'athlete',
      gym_days_week:   data.gym_days_week ?? 3,
      primary_sports:  data.primary_sports ?? {},
      garmin_email:    data.garmin_email ?? '',
      garmin_password: data.garmin_password ?? '',
    })
  }, [data])

  const mut = useMutation({
    mutationFn: updateMe,
    onSuccess: () => {
      toast.success('Profile saved')
      setTimeout(() => window.location.reload(), 800)
    },
    onError: (err) => toast.error(`Save failed: ${err.message}`),
  })

  const deleteMut = useMutation({
    mutationFn: deleteMe,
    onSuccess: () => {
      clearToken()
      qc.clear()
      toast.success('Account deleted')
      navigate('/login')
    },
    onError: () => toast.error('Failed to delete account'),
  })

  if (isLoading || !form) return <div className="p-8 text-muted-foreground animate-pulse">Loading…</div>

  function set(k, v) { setForm(p => ({ ...p, [k]: v })) }

  function save(e) {
    e.preventDefault()
    mut.mutate(form)
  }

  return (
    <div className="p-6 max-w-xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Profile</h2>
        <p className="text-sm text-muted-foreground">{data.email}</p>
      </div>

      <form onSubmit={save} noValidate className="space-y-6">
        {/* Name */}
        <div className="space-y-1">
          <label className="text-sm font-medium">Name</label>
          <input value={form.name} onChange={e => set('name', e.target.value)}
            className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>

        {/* Goal */}
        <div className="space-y-1">
          <label className="text-sm font-medium">Training goal</label>
          <select value={form.goal} onChange={e => set('goal', e.target.value)}
            className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer">
            {GOALS.map(g => <option key={g.key} value={g.key}>{g.label}</option>)}
          </select>
        </div>

        {/* Gym days */}
        <div className="space-y-1">
          <label className="text-sm font-medium">Gym sessions per week</label>
          <select value={form.gym_days_week} onChange={e => set('gym_days_week', Number(e.target.value))}
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
          <SportPicker
            value={form.primary_sports}
            onChange={sports => set('primary_sports', sports)}
          />
        </div>

        {/* Garmin credentials */}
        <div className="space-y-3">
          <label className="text-sm font-medium">Garmin Connect</label>
          <div className="space-y-2">
            <input
              type="email" placeholder="Garmin email"
              value={form.garmin_email}
              onChange={e => set('garmin_email', e.target.value)}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
            <div className="relative">
              <input
                type={showGarminPw ? 'text' : 'password'}
                placeholder="Garmin password"
                value={form.garmin_password}
                onChange={e => set('garmin_password', e.target.value)}
                className="w-full bg-background border border-border rounded-md px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
              <button type="button" onClick={() => setShowGarminPw(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                {showGarminPw ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button type="submit" disabled={mut.isPending}
            className="px-5 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
            {mut.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </form>

      {/* Danger zone */}
      <div className="border border-red-500/30 rounded-xl p-5 space-y-3">
        <p className="text-sm font-medium text-red-400">Danger zone</p>
        <p className="text-xs text-muted-foreground">
          Permanently delete your account and all training data. This cannot be undone.
        </p>
        {!confirmDelete ? (
          <button onClick={() => setConfirmDelete(true)}
            className="px-4 py-2 border border-red-500/50 text-red-400 rounded-md text-sm hover:bg-red-500/10 transition-colors">
            Delete account
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <button onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}
              className="px-4 py-2 bg-red-500 text-white rounded-md text-sm font-medium hover:bg-red-600 disabled:opacity-50 transition-colors">
              {deleteMut.isPending ? 'Deleting…' : 'Yes, delete everything'}
            </button>
            <button onClick={() => setConfirmDelete(false)}
              className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
