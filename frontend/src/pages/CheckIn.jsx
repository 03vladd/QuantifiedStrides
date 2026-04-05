import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchReadiness, saveReadiness, fetchReflection, saveReflection } from '@/api/checkin'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ClipboardList } from 'lucide-react'

// ── helpers ───────────────────────────────────────────────────────────────────

const today = new Date().toLocaleDateString('en-CA')

const sel = 'text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground'

function SliderRow({ label, name, value, onChange }) {
  const pct = ((value - 1) / 9) * 100
  const color = value >= 8 ? '#00cc7a' : value >= 5 ? '#fdcb6e' : '#ff6b6b'
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold" style={{ color }}>{value}/10</span>
      </div>
      <input
        type="range" min={1} max={10} value={value}
        onChange={e => onChange(name, Number(e.target.value))}
        className="w-full accent-primary"
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Terrible</span><span>Perfect</span>
      </div>
    </div>
  )
}

// ── Morning Check-In ─────────────────────────────────────────────────────────

function MorningTab() {
  const qc = useQueryClient()
  const [date, setDate]   = useState(today)
  const [vals, setVals]   = useState({ overall: 7, legs: 7, upper: 7, joints: 8 })
  const [injuryNote, setInjuryNote] = useState('')
  const [timeAvail, setTimeAvail]   = useState('medium')
  const [goingOut, setGoingOut]     = useState(false)
  const [saved, setSaved] = useState(false)

  const { data: existing } = useQuery({
    queryKey: ['readiness', date],
    queryFn: () => fetchReadiness(date).catch(() => null),
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!existing) return
    setVals({ overall: existing.overall_feel, legs: existing.legs_feel, upper: existing.upper_body_feel, joints: existing.joint_feel })
    setInjuryNote(existing.injury_note ?? '')
    setTimeAvail(existing.time_available ?? 'medium')
    setGoingOut(!!existing.going_out_tonight)
  }, [existing])

  const mut = useMutation({
    mutationFn: saveReadiness,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['readiness', date] })
      qc.invalidateQueries({ queryKey: ['journal-history'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  function set(name, v) { setVals(p => ({ ...p, [name]: v })) }

  function handleDateChange(v) {
    setDate(v)
    setSaved(false)
  }

  function submit(e) {
    e.preventDefault()
    mut.mutate({
      entry_date:       date,
      overall_feel:     vals.overall,
      legs_feel:        vals.legs,
      upper_body_feel:  vals.upper,
      joint_feel:       vals.joints,
      injury_note:      vals.joints <= 6 ? injuryNote || null : null,
      time_available:   timeAvail,
      going_out_tonight: goingOut,
    })
  }

  const isUpdate = !!existing

  return (
    <form onSubmit={submit} className="space-y-6 max-w-xl">
      <div className="flex items-center gap-3">
        <label className="text-sm text-muted-foreground">Date</label>
        <input type="date" value={date} onChange={e => handleDateChange(e.target.value)} className={sel} />
      </div>

      {isUpdate && (
        <p className="text-xs text-blue-400 bg-blue-950/30 border border-blue-800/40 rounded px-3 py-2">
          Check-in for this date already logged — update below.
        </p>
      )}

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm">How are you feeling today?</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          <SliderRow label="Overall feel"    name="overall" value={vals.overall} onChange={set} />
          <SliderRow label="Legs"            name="legs"    value={vals.legs}    onChange={set} />
          <SliderRow label="Upper body"      name="upper"   value={vals.upper}   onChange={set} />
          <SliderRow label="Joints / injury" name="joints"  value={vals.joints}  onChange={set} />

          {vals.joints <= 6 && (
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground">What's bothering you?</label>
              <input
                type="text" value={injuryNote}
                onChange={e => setInjuryNote(e.target.value)}
                placeholder="e.g. left knee slight ache"
                className={`${sel} w-full`}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4 space-y-4">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Time available today</p>
            <div className="flex gap-4">
              {['short', 'medium', 'long'].map(opt => (
                <label key={opt} className="flex items-center gap-2 cursor-pointer text-sm">
                  <input
                    type="radio" name="time" value={opt} checked={timeAvail === opt}
                    onChange={() => setTimeAvail(opt)}
                    className="accent-primary"
                  />
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </label>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox" checked={goingOut}
              onChange={e => setGoingOut(e.target.checked)}
              className="accent-primary w-4 h-4"
            />
            <span className="text-sm">Going out tonight?</span>
          </label>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={mut.isPending}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {mut.isPending ? 'Saving…' : isUpdate ? 'Update Check-In' : 'Save Check-In'}
        </button>
        {saved && <span className="text-xs text-green-400">Saved!</span>}
        {mut.isError && <span className="text-xs text-red-400">Save failed.</span>}
      </div>
    </form>
  )
}

// ── Post-Workout Reflection ───────────────────────────────────────────────────

const LOAD_FEEL_OPTIONS = [
  { value: -2, label: 'Much too easy', color: '#00cc7a' },
  { value: -1, label: 'Slightly easy', color: '#55efc4' },
  { value:  0, label: 'Just right',    color: '#fdcb6e' },
  { value:  1, label: 'Slightly hard', color: '#e17055' },
  { value:  2, label: 'Too hard',      color: '#d63031' },
]

function PostWorkoutTab({ initialDate }) {
  const qc = useQueryClient()
  const [date, setDate]       = useState(initialDate ?? today)
  const [rpe, setRpe]         = useState(6)
  const [quality, setQuality] = useState(7)
  const [loadFeel, setLoadFeel] = useState(null)
  const [notes, setNotes]     = useState('')
  const [saved, setSaved]     = useState(false)

  const { data: existing } = useQuery({
    queryKey: ['reflection', date],
    queryFn: () => fetchReflection(date).catch(() => null),
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!existing) return
    setRpe(existing.session_rpe ?? 6)
    setQuality(existing.session_quality ?? 7)
    setLoadFeel(existing.load_feel ?? null)
    setNotes(existing.notes ?? '')
  }, [existing])

  const mut = useMutation({
    mutationFn: saveReflection,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reflection', date] })
      qc.invalidateQueries({ queryKey: ['journal-history'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  function handleDateChange(v) { setDate(v); setSaved(false) }

  function submit(e) {
    e.preventDefault()
    mut.mutate({ entry_date: date, session_rpe: rpe, session_quality: quality, notes: notes || null, load_feel: loadFeel })
  }

  const isUpdate = !!existing

  return (
    <form onSubmit={submit} className="space-y-6 max-w-xl">
      <div className="flex items-center gap-3">
        <label className="text-sm text-muted-foreground">Date</label>
        <input type="date" value={date} onChange={e => handleDateChange(e.target.value)} className={sel} />
      </div>

      {isUpdate && (
        <p className="text-xs text-blue-400 bg-blue-950/30 border border-blue-800/40 rounded px-3 py-2">
          Reflection for this date already logged — updating.
        </p>
      )}

      <Card>
        <CardContent className="pt-4 space-y-5">
          <SliderRow label="Session RPE — how hard was it?"       name="rpe"     value={rpe}     onChange={(_, v) => setRpe(v)} />
          <SliderRow label="Session quality — how well did it go?" name="quality" value={quality} onChange={(_, v) => setQuality(v)} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4 space-y-2">
          <p className="text-sm text-muted-foreground">How was the load vs what you expected?</p>
          <p className="text-xs text-muted-foreground">This feeds directly into tomorrow's recommendation — if you felt sandbagged, the engine will push harder.</p>
          <div className="flex flex-wrap gap-2 pt-1">
            {LOAD_FEEL_OPTIONS.map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setLoadFeel(loadFeel === opt.value ? null : opt.value)}
                className="px-3 py-1.5 rounded-full text-xs font-medium border transition-all"
                style={loadFeel === opt.value
                  ? { background: opt.color, borderColor: opt.color, color: '#0a0a0a' }
                  : { borderColor: 'var(--border)', color: 'var(--muted-foreground)' }
                }
              >
                {opt.label}
              </button>
            ))}
          </div>
          {loadFeel === null && (
            <p className="text-xs text-muted-foreground italic">Optional — skip if not applicable.</p>
          )}
        </CardContent>
      </Card>

      <div className="space-y-1">
        <label className="text-sm text-muted-foreground">Notes</label>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Anything notable about this session…"
          rows={4}
          className={`${sel} w-full resize-none`}
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={mut.isPending}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {mut.isPending ? 'Saving…' : 'Save Reflection'}
        </button>
        {saved && <span className="text-xs text-green-400">Saved!</span>}
        {mut.isError && <span className="text-xs text-red-400">Save failed.</span>}
      </div>
    </form>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function CheckIn() {
  const location = useLocation()
  const state    = location.state ?? {}
  const initialTab  = state.tab  ?? 'morning'
  const initialDate = state.date ?? undefined

  return (
    <div className="p-6 space-y-4 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
        <ClipboardList size={20} /> Check-In
      </h2>

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="morning">Morning Check-In</TabsTrigger>
          <TabsTrigger value="post">Post-Workout Reflection</TabsTrigger>
        </TabsList>
        <TabsContent value="morning" className="mt-4"><MorningTab /></TabsContent>
        <TabsContent value="post"    className="mt-4"><PostWorkoutTab initialDate={initialDate} /></TabsContent>
      </Tabs>
    </div>
  )
}
