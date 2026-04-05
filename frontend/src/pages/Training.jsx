import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { fetchSportOptions, fetchWorkouts, fetchWorkout } from '@/api/training'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ChevronRight } from 'lucide-react'

// ── helpers ──────────────────────────────────────────────────────────────────

const SPORT_ICONS = {
  running: '🏃', trail_running: '🏔️', cycling: '🚴', indoor_cycling: '🚴',
  mountain_biking: '🚵', strength_training: '🏋️', bouldering: '🧗',
  resort_skiing: '⛷️', indoor_cardio: '💪',
}
const sportIcon = s => SPORT_ICONS[s] ?? '🏅'
const sportLabel = s => s?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) ?? s

function fmtDuration(s) {
  if (!s) return '—'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60)
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
           : `${m}:${String(sec).padStart(2,'0')}`
}

function fmtPace(minKm) {
  if (!minKm || minKm <= 0) return '—'
  const m = Math.floor(minKm), s = Math.round((minKm - m) * 60)
  return `${m}:${String(s).padStart(2,'0')} /km`
}

function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' })
}

const sel = 'text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground'

// ── zone bar ─────────────────────────────────────────────────────────────────

const ZONE_COLORS = ['#74b9ff','#55efc4','#fdcb6e','#e17055','#d63031']
const ZONE_LABELS = ['Z1 Recovery','Z2 Aerobic','Z3 Tempo','Z4 Threshold','Z5 VO₂max']

function HRZones({ detail }) {
  const zones = [detail.z1, detail.z2, detail.z3, detail.z4, detail.z5].map(Number)
  const total = zones.reduce((a,b) => a+b, 0)
  if (!total) return null

  const data = zones.map((s,i) => ({ name: ZONE_LABELS[i], min: Math.round(s/60), color: ZONE_COLORS[i] }))

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-2">Heart Rate Zones</p>
      <div className="h-8">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={[Object.fromEntries(data.map(d => [d.name, d.min]))]}
            layout="vertical" margin={{ top:0, right:0, left:0, bottom:0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" hide />
            <Tooltip formatter={(v,n) => [`${v} min`, n]} />
            {data.map(d => (
              <Bar key={d.name} dataKey={d.name} stackId="a" fill={d.color} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-3 flex-wrap mt-1">
        {data.map(d => (
          <span key={d.name} className="text-xs text-muted-foreground flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm" style={{background:d.color}} />
            {d.name} {d.min}m
          </span>
        ))}
      </div>
    </div>
  )
}

// ── workout detail ────────────────────────────────────────────────────────────

function Metric({ label, value }) {
  if (!value) return null
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  )
}

function WorkoutDetail({ workoutId }) {
  const { data: d, isLoading } = useQuery({
    queryKey: ['workout', workoutId],
    queryFn: () => fetchWorkout(workoutId),
    enabled: !!workoutId,
  })

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse">Loading…</p>
  if (!d) return null

  const distKm   = d.distance_m ? d.distance_m / 1000 : null
  const avgPace  = distKm && d.duration_s ? (d.duration_s / 60) / distKm : null
  const isRun    = ['running','trail_running'].includes(d.sport)
  const isStrength = d.sport === 'strength_training'

  return (
    <div className="space-y-4">
      <div>
        <p className="text-lg font-bold">
          {sportIcon(d.sport)} {d.workout_type || sportLabel(d.sport)}
        </p>
        <p className="text-xs text-muted-foreground">
          {fmtDate(d.workout_date)}
          {d.start_time && ` · ${new Date(d.start_time).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})}`}
          {d.location && ` · ${d.location}`}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {distKm && <Metric label="Distance" value={`${distKm.toFixed(2)} km`} />}
        <Metric label="Duration"  value={fmtDuration(d.duration_s)} />
        <Metric label="Avg HR"    value={d.avg_hr   ? `${d.avg_hr} bpm` : null} />
        {avgPace && <Metric label="Avg Pace" value={fmtPace(avgPace)} />}
        <Metric label="Calories"  value={d.calories ? `${d.calories} kcal` : null} />
        <Metric label="TSS"       value={d.tss      ? d.tss.toFixed(0) : null} />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Metric label="Elev Gain"    value={d.elev_gain   ? `${d.elev_gain.toFixed(0)} m` : null} />
        <Metric label="Elev Loss"    value={d.elev_loss   ? `${d.elev_loss.toFixed(0)} m` : null} />
        <Metric label="Aerobic TE"   value={d.aerobic_te  ? d.aerobic_te.toFixed(1) : null} />
        <Metric label="Anaerobic TE" value={d.anaerobic_te ? d.anaerobic_te.toFixed(1) : null} />
        <Metric label="VO₂max Est"   value={d.vo2max      ? d.vo2max.toFixed(1) : null} />
      </div>

      {d.avg_power && (
        <div className="grid grid-cols-3 gap-3">
          <Metric label="Avg Power"  value={`${d.avg_power.toFixed(0)} W`} />
          <Metric label="Max Power"  value={d.max_power  ? `${d.max_power.toFixed(0)} W` : null} />
          <Metric label="Norm Power" value={d.norm_power ? `${d.norm_power.toFixed(0)} W` : null} />
        </div>
      )}

      {isRun && (d.avg_cadence || d.avg_gct || d.avg_stride || d.avg_vo) && (
        <div className="grid grid-cols-3 gap-3">
          <Metric label="Avg Cadence" value={d.avg_cadence ? `${d.avg_cadence.toFixed(0)} spm` : null} />
          <Metric label="Avg GCT"     value={d.avg_gct     ? `${d.avg_gct.toFixed(0)} ms` : null} />
          <Metric label="Avg Stride"  value={d.avg_stride  ? `${d.avg_stride.toFixed(2)} m` : null} />
          <Metric label="Vert Osc"    value={d.avg_vo      ? `${d.avg_vo.toFixed(1)} cm` : null} />
          <Metric label="Total Steps" value={d.total_steps ? d.total_steps.toLocaleString() : null} />
        </div>
      )}

      <HRZones detail={d} />

      {isStrength && (
        <p className="text-xs text-muted-foreground border-l-2 border-muted pl-2">
          Strength session — view exercises in the Strength tab
        </p>
      )}
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Training() {
  const [sport,      setSport]      = useState('all')
  const [days,       setDays]       = useState(365)
  const [selectedId, setSelectedId] = useState(null)

  const { data: sports = [] } = useQuery({
    queryKey: ['sport-options'],
    queryFn: fetchSportOptions,
  })

  const { data: workouts = [], isLoading } = useQuery({
    queryKey: ['workouts', days, sport],
    queryFn: () => fetchWorkouts(days, sport),
  })

  return (
    <div className="p-6 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-baseline justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold tracking-tight">Workout History</h2>
        <div className="flex gap-2">
          <select value={sport} onChange={e => { setSport(e.target.value); setSelectedId(null) }} className={sel}>
            <option value="all">All sports</option>
            {sports.map(s => <option key={s} value={s}>{sportIcon(s)} {sportLabel(s)}</option>)}
          </select>
          <select value={days} onChange={e => { setDays(Number(e.target.value)); setSelectedId(null) }} className={sel}>
            <option value={90}>Last 3 months</option>
            <option value={180}>Last 6 months</option>
            <option value={365}>Last year</option>
            <option value={730}>Last 2 years</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground animate-pulse">Loading workouts…</p>
      ) : workouts.length === 0 ? (
        <p className="text-sm text-muted-foreground">No workouts found.</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
          {/* List */}
          <div className="space-y-1 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
            <p className="text-xs text-muted-foreground px-1 mb-2">{workouts.length} workouts</p>
            {workouts.map(w => {
              const distKm = w.distance_m ? (w.distance_m / 1000).toFixed(1) : null
              return (
                <button key={w.workout_id}
                  onClick={() => setSelectedId(w.workout_id === selectedId ? null : w.workout_id)}
                  className={`w-full text-left px-3 py-2.5 rounded-md border transition-colors ${
                    w.workout_id === selectedId
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-border hover:bg-muted'
                  }`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">
                      {sportIcon(w.sport)} {fmtDate(w.workout_date)}
                    </span>
                    <ChevronRight size={14} className="shrink-0 opacity-50" />
                  </div>
                  <div className="text-xs opacity-60 mt-0.5 flex gap-2 flex-wrap">
                    <span>{sportLabel(w.sport)}</span>
                    {distKm && <span>{distKm} km</span>}
                    {w.duration_s && <span>{fmtDuration(w.duration_s)}</span>}
                    {w.avg_hr && <span>{w.avg_hr} bpm</span>}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Detail */}
          <Card>
            <CardContent className="pt-4">
              {selectedId
                ? <WorkoutDetail workoutId={selectedId} />
                : <p className="text-sm text-muted-foreground">Select a workout to see details.</p>
              }
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
