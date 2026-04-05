import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  fetchGarminWorkouts, fetchSession, fetch1RMHistory,
  fetchTrackedExercises, fetchExerciseNames, createSession,
} from '@/api/strength'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dumbbell, ChevronRight, Plus, Trash2, ClipboardList } from 'lucide-react'

const BAR_WEIGHT_KG = 20.0

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function sessionBadge(type) {
  if (!type) return null
  return (
    <Badge variant={type === 'upper' ? 'secondary' : 'outline'} className="capitalize text-xs">
      {type}
    </Badge>
  )
}

function fmtWeight(set) {
  if (set.is_bodyweight) return 'BW'
  if (set.total_weight_kg) return `${set.total_weight_kg} kg`
  if (set.band_color) return `band (${set.band_color})`
  return '—'
}

function fmtReps(set) {
  if (set.duration_seconds) return `${set.duration_seconds}s`
  if (set.reps_min && set.reps_max) return `${set.reps_min}–${set.reps_max}`
  if (set.reps) return set.reps
  return '—'
}

function computeTotal(weightKg, plusBar, inclBar, perHand) {
  if (weightKg == null) return null
  if (plusBar) return weightKg + BAR_WEIGHT_KG
  if (inclBar) return weightKg               // already includes bar
  if (perHand) return weightKg * 2
  return weightKg
}

// ── session detail panel ─────────────────────────────────────────────────────

function SessionDetail({ sessionId }) {
  const { data, isLoading } = useQuery({
    queryKey: ['strength-session', sessionId],
    queryFn: () => fetchSession(sessionId),
    enabled: !!sessionId,
  })

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse p-2">Loading…</p>
  if (!data)     return null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className="font-semibold">{fmtDate(data.session_date)}</h3>
        {sessionBadge(data.session_type)}
      </div>
      {data.raw_notes && (
        <p className="text-sm text-muted-foreground border-l-2 border-muted pl-3">{data.raw_notes}</p>
      )}
      {data.exercises.map((ex) => (
        <div key={ex.exercise_id} className="space-y-2">
          <div className="flex items-center gap-2">
            <Dumbbell size={13} className="text-muted-foreground" />
            <span className="text-sm font-medium">{ex.name}</span>
            {ex.notes && <span className="text-xs text-muted-foreground">· {ex.notes}</span>}
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground border-b border-border">
                <th className="text-left pb-1 w-8">Set</th>
                <th className="text-left pb-1">Reps</th>
                <th className="text-left pb-1">Weight</th>
                <th className="text-left pb-1">Notes</th>
              </tr>
            </thead>
            <tbody>
              {ex.sets.map((s) => (
                <tr key={s.set_id} className="border-b border-border/40">
                  <td className="py-1 text-muted-foreground">{s.set_number}</td>
                  <td className="py-1">{fmtReps(s)}</td>
                  <td className="py-1">{fmtWeight(s)}</td>
                  <td className="py-1 text-muted-foreground">
                    {[s.per_hand && 'per hand', s.per_side && 'per side', s.plus_bar && '+bar']
                      .filter(Boolean).join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

// ── 1RM chart ─────────────────────────────────────────────────────────────────

function OneRMChart() {
  const [exercise, setExercise] = useState('')
  const [days, setDays] = useState(365)

  const { data: exercises = [] } = useQuery({
    queryKey: ['strength-tracked-exercises'],
    queryFn: fetchTrackedExercises,
  })

  const { data: history = [], isLoading } = useQuery({
    queryKey: ['strength-1rm', exercise, days],
    queryFn: () => fetch1RMHistory(exercise, days),
    enabled: !!exercise,
  })

  const chartData = history.map(p => ({
    date: p.session_date,
    '1RM': Math.round(p.epley_1rm * 10) / 10,
  }))

  return (
    <div className="space-y-4">
      <div className="flex gap-3 flex-wrap items-center">
        <select value={exercise} onChange={e => setExercise(e.target.value)}
          className="text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground">
          <option value="">Select exercise…</option>
          {exercises.map(ex => <option key={ex} value={ex}>{ex}</option>)}
        </select>
        <select value={days} onChange={e => setDays(Number(e.target.value))}
          className="text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground">
          <option value={90}>Last 90 days</option>
          <option value={180}>Last 6 months</option>
          <option value={365}>Last year</option>
          <option value={730}>Last 2 years</option>
        </select>
      </div>

      {!exercise && <p className="text-sm text-muted-foreground">Pick an exercise to see estimated 1RM progression.</p>}
      {exercise && isLoading && <p className="text-sm text-muted-foreground animate-pulse">Loading…</p>}
      {exercise && !isLoading && chartData.length === 0 && (
        <p className="text-sm text-muted-foreground">No data for {exercise} in this period.</p>
      )}
      {chartData.length > 0 && (
        <>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickFormatter={d => new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickFormatter={v => `${v} kg`} width={56} />
                <Tooltip
                  contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: 6 }}
                  labelStyle={{ color: 'var(--muted-foreground)', fontSize: 11 }}
                  formatter={v => [`${v} kg`, 'Est. 1RM']} />
                <Line type="monotone" dataKey="1RM" stroke="var(--primary)" strokeWidth={2}
                  dot={{ r: 3, fill: 'var(--primary)' }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-muted-foreground">Estimated via Epley formula: weight × (1 + reps ÷ 30)</p>
        </>
      )}
    </div>
  )
}

// ── log session form ──────────────────────────────────────────────────────────

const BAND_COLORS = ['yellow', 'blue', 'green', 'red', 'black']

function AddExerciseForm({ exerciseNames, onAdd }) {
  const [name, setName]           = useState('')
  const [notes, setNotes]         = useState('')
  const [perHand, setPerHand]     = useState(false)
  const [perSide, setPerSide]     = useState(false)
  const [weightType, setWeightType] = useState('kg')
  const [weightKg, setWeightKg]   = useState(0)
  const [barOption, setBarOption] = useState('none')   // 'none' | 'plus' | 'incl'
  const [bandColor, setBandColor] = useState('yellow')
  const [nSets, setNSets]         = useState(3)
  const [isTimed, setIsTimed]     = useState(false)
  const [reps, setReps]           = useState(8)
  const [duration, setDuration]   = useState(30)

  function handleAdd() {
    if (!name) return
    const plusBar = barOption === 'plus'
    const inclBar = barOption === 'incl'
    const storedWeight = weightType === 'kg'
      ? (inclBar ? weightKg - BAR_WEIGHT_KG : weightKg)
      : null
    const total = weightType === 'kg'
      ? computeTotal(storedWeight, plusBar, inclBar, perHand)
      : null

    const sets = Array.from({ length: nSets }, (_, i) => ({
      set_number:          i + 1,
      reps:                isTimed ? null : reps,
      duration_seconds:    isTimed ? duration : null,
      weight_kg:           storedWeight,
      is_bodyweight:       weightType === 'bodyweight',
      band_color:          weightType === 'band' ? bandColor : null,
      per_hand:            perHand,
      per_side:            perSide,
      plus_bar:            plusBar,
      weight_includes_bar: inclBar,
      total_weight_kg:     total,
    }))

    onAdd({ name, notes: notes || null, sets })

    // reset
    setName(''); setNotes(''); setPerHand(false); setPerSide(false)
    setWeightType('kg'); setWeightKg(0); setBarOption('none')
    setNSets(3); setIsTimed(false); setReps(8); setDuration(30)
  }

  const inputCls = 'text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground w-full'
  const checkCls = 'flex items-center gap-2 text-sm cursor-pointer'

  return (
    <div className="border border-border rounded-lg p-4 space-y-4 bg-muted/20">
      <p className="text-sm font-semibold">Add Exercise</p>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Exercise</label>
          <input list="exercise-list" value={name} onChange={e => setName(e.target.value)}
            placeholder="Type or pick…" className={inputCls} />
          <datalist id="exercise-list">
            {exerciseNames.map(n => <option key={n} value={n} />)}
          </datalist>
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Notes (optional)</label>
          <input value={notes} onChange={e => setNotes(e.target.value)} className={inputCls} />
        </div>
      </div>

      <div className="flex gap-6">
        <label className={checkCls}>
          <input type="checkbox" checked={perHand} onChange={e => setPerHand(e.target.checked)} />
          Per hand
        </label>
        <label className={checkCls}>
          <input type="checkbox" checked={perSide} onChange={e => setPerSide(e.target.checked)} />
          Per side
        </label>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-muted-foreground block">Weight</label>
        <div className="flex gap-3">
          {['kg', 'bodyweight', 'band'].map(t => (
            <label key={t} className={checkCls}>
              <input type="radio" name="weight-type" value={t}
                checked={weightType === t} onChange={() => setWeightType(t)} />
              <span className="capitalize">{t}</span>
            </label>
          ))}
        </div>

        {weightType === 'kg' && (
          <div className="flex gap-3 flex-wrap">
            <div className="w-32">
              <input type="number" min={0} step={0.5} value={weightKg}
                onChange={e => setWeightKg(parseFloat(e.target.value) || 0)}
                className={inputCls} />
            </div>
            <div className="flex gap-3">
              {[['none', 'No bar'], ['plus', '+20 kg bar'], ['incl', 'Includes bar']].map(([val, lbl]) => (
                <label key={val} className={checkCls}>
                  <input type="radio" name="bar-opt" value={val}
                    checked={barOption === val} onChange={() => setBarOption(val)} />
                  {lbl}
                </label>
              ))}
            </div>
          </div>
        )}

        {weightType === 'band' && (
          <select value={bandColor} onChange={e => setBandColor(e.target.value)}
            className="text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground">
            {BAND_COLORS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 items-end">
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Sets</label>
          <input type="number" min={1} max={20} value={nSets}
            onChange={e => setNSets(parseInt(e.target.value) || 1)} className={inputCls} />
        </div>
        <div className="flex items-center gap-2">
          <label className={checkCls}>
            <input type="checkbox" checked={isTimed} onChange={e => setIsTimed(e.target.checked)} />
            Time-based
          </label>
        </div>
        <div>
          {isTimed ? (
            <>
              <label className="text-xs text-muted-foreground mb-1 block">Duration (s)</label>
              <input type="number" min={1} value={duration}
                onChange={e => setDuration(parseInt(e.target.value) || 1)} className={inputCls} />
            </>
          ) : (
            <>
              <label className="text-xs text-muted-foreground mb-1 block">Reps</label>
              <input type="number" min={1} value={reps}
                onChange={e => setReps(parseInt(e.target.value) || 1)} className={inputCls} />
            </>
          )}
        </div>
      </div>

      <button onClick={handleAdd} disabled={!name}
        className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-40 hover:opacity-90 transition-opacity">
        <Plus size={15} /> Add to session
      </button>
    </div>
  )
}

function ReflectionPrompt({ sessionDate, onYes, onNo }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4">
        <div className="flex items-center gap-3">
          <ClipboardList size={20} className="text-primary shrink-0" />
          <div>
            <p className="font-semibold">Session saved!</p>
            <p className="text-sm text-muted-foreground">Want to add a post-workout reflection?</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {new Date(sessionDate).toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: 'long' })}
        </p>
        <div className="flex gap-3 pt-1">
          <button
            onClick={onYes}
            className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Add Reflection
          </button>
          <button
            onClick={onNo}
            className="flex-1 px-4 py-2 border border-border rounded-md text-sm hover:bg-muted transition-colors"
          >
            Skip
          </button>
        </div>
      </div>
    </div>
  )
}

function LogSession({ exerciseNames, initialDate, onSaved }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const today = new Date().toLocaleDateString('en-CA')

  const [sessionDate, setSessionDate] = useState(initialDate ?? today)
  const [sessionType, setSessionType] = useState('upper')
  const [exercises, setExercises]     = useState([])
  const [savedDate, setSavedDate]     = useState(null)

  const mutation = useMutation({
    mutationFn: createSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strength-workouts'] })
      queryClient.invalidateQueries({ queryKey: ['strength-tracked-exercises'] })
      setExercises([])
      setSavedDate(sessionDate) // show reflection prompt
    },
  })

  function addExercise(ex) {
    setExercises(prev => [...prev, { ...ex, exercise_order: prev.length + 1 }])
  }

  function removeExercise(idx) {
    setExercises(prev => {
      const next = prev.filter((_, i) => i !== idx)
      return next.map((e, i) => ({ ...e, exercise_order: i + 1 }))
    })
  }

  function save() {
    mutation.mutate({ session_date: sessionDate, session_type: sessionType, exercises })
  }

  function summarise(ex) {
    const s0 = ex.sets[0]
    const repsStr = s0.duration_seconds ? `${s0.duration_seconds}s` : s0.reps
    const wtStr = s0.is_bodyweight ? 'BW'
      : s0.band_color ? `band(${s0.band_color})`
      : s0.total_weight_kg ? `${s0.total_weight_kg} kg` : '—'
    return `${ex.sets.length}×${repsStr} @ ${wtStr}`
  }

  return (
    <>
    {savedDate && (
      <ReflectionPrompt
        sessionDate={savedDate}
        onYes={() => {
          setSavedDate(null)
          onSaved()
          navigate('/checkin', { state: { tab: 'post', date: savedDate } })
        }}
        onNo={() => {
          setSavedDate(null)
          onSaved()
        }}
      />
    )}
    <div className="space-y-6">
      {/* Date + type */}
      <div className="flex gap-4 flex-wrap items-end">
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Date</label>
          <input type="date" value={sessionDate} onChange={e => setSessionDate(e.target.value)}
            className="text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground" />
        </div>
        <div className="flex gap-4">
          {['upper', 'lower'].map(t => (
            <label key={t} className="flex items-center gap-2 text-sm cursor-pointer capitalize">
              <input type="radio" name="session-type" value={t}
                checked={sessionType === t} onChange={() => setSessionType(t)} />
              {t}
            </label>
          ))}
        </div>
      </div>

      {/* Add exercise form */}
      <AddExerciseForm exerciseNames={exerciseNames} onAdd={addExercise} />

      {/* Session preview */}
      {exercises.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold">
            Session — {sessionType.charAt(0).toUpperCase() + sessionType.slice(1)} — {fmtDate(sessionDate)}
          </p>
          {exercises.map((ex, idx) => (
            <div key={idx} className="flex items-start justify-between gap-3 p-3 rounded-md border border-border bg-muted/30">
              <div>
                <p className="text-sm font-medium">{ex.name}</p>
                <p className="text-xs text-muted-foreground">{summarise(ex)}{ex.notes ? ` · ${ex.notes}` : ''}</p>
              </div>
              <button onClick={() => removeExercise(idx)}
                className="text-muted-foreground hover:text-destructive transition-colors mt-0.5">
                <Trash2 size={14} />
              </button>
            </div>
          ))}

          <Separator />

          <div className="flex gap-3">
            <button onClick={save} disabled={mutation.isPending || exercises.length === 0}
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-40 hover:opacity-90 transition-opacity">
              {mutation.isPending ? 'Saving…' : 'Save Session'}
            </button>
            <button onClick={() => setExercises([])}
              className="px-4 py-2 rounded-md border border-border text-sm hover:bg-muted transition-colors">
              Clear All
            </button>
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">{mutation.error?.message}</p>
          )}
        </div>
      )}
    </div>
    </>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Strength() {
  const [selectedId, setSelectedId]     = useState(null)
  const [prefillDate, setPrefillDate]   = useState(null)
  const [days, setDays]                 = useState(90)
  const [activeTab, setActiveTab]       = useState('sessions')

  const { data: workouts = [], isLoading } = useQuery({
    queryKey: ['strength-workouts', days],
    queryFn: () => fetchGarminWorkouts(days),
  })

  function openLog(date) {
    setPrefillDate(date)
    setActiveTab('log')
  }

  const { data: exerciseNames = [] } = useQuery({
    queryKey: ['exercise-names'],
    queryFn: fetchExerciseNames,
  })

  return (
    <div className="p-6 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Strength</h2>
        {activeTab === 'sessions' && (
          <select value={days} onChange={e => { setDays(Number(e.target.value)); setSelectedId(null) }}
            className="text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground">
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 6 months</option>
            <option value={365}>Last year</option>
          </select>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="log">Log Session</TabsTrigger>
          <TabsTrigger value="1rm">1RM Progression</TabsTrigger>
        </TabsList>

        {/* ── Sessions ── */}
        <TabsContent value="sessions" className="mt-4">
          {isLoading ? (
            <p className="text-sm text-muted-foreground animate-pulse">Loading sessions…</p>
          ) : workouts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No strength workouts from Garmin in this period.</p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4">
              <div className="space-y-1">
                {workouts.map(w => {
                  const logged = w.session_id != null
                  const isSelected = logged && w.session_id === selectedId
                  return (
                    <button key={w.workout_id}
                      onClick={() => logged
                        ? setSelectedId(w.session_id === selectedId ? null : w.session_id)
                        : openLog(w.workout_date)
                      }
                      className={`w-full text-left px-3 py-2.5 rounded-md border transition-colors ${
                        isSelected
                          ? 'bg-primary text-primary-foreground border-primary'
                          : logged
                            ? 'border-border hover:bg-muted'
                            : 'border-dashed border-border hover:bg-muted/60'
                      }`}>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-sm font-medium shrink-0">{fmtDate(w.workout_date)}</span>
                          {logged ? sessionBadge(w.session_type) : (
                            <span className="text-xs text-muted-foreground italic">not logged</span>
                          )}
                        </div>
                        <ChevronRight size={14} className="shrink-0 opacity-50" />
                      </div>
                      <div className="text-xs opacity-60 mt-0.5 flex gap-2">
                        {w.duration_min && <span>{w.duration_min} min</span>}
                        {w.calories && <span>{w.calories} kcal</span>}
                        {logged && <span>{w.total_exercises} exercises · {w.total_sets} sets</span>}
                      </div>
                    </button>
                  )
                })}
              </div>

              <Card>
                <CardContent className="pt-4">
                  {selectedId ? (
                    <SessionDetail sessionId={selectedId} />
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Select a logged session to see details, or click a dashed entry to log its exercises.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* ── Log Session ── */}
        <TabsContent value="log" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">
                {prefillDate ? `Log exercises for ${fmtDate(prefillDate)}` : 'Log a Strength Session'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <LogSession
                key={prefillDate}
                exerciseNames={exerciseNames}
                initialDate={prefillDate}
                onSaved={() => { setPrefillDate(null); setActiveTab('sessions') }}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── 1RM ── */}
        <TabsContent value="1rm" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Estimated 1RM over time</CardTitle>
            </CardHeader>
            <CardContent>
              <OneRMChart />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
