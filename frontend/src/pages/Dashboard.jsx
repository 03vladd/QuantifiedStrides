import { useQuery } from '@tanstack/react-query'
import { fetchDashboard } from '@/api/dashboard'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  AlertTriangle, Info, XCircle, Moon, Wind, Thermometer,
  Heart, Zap, Activity, Dumbbell, CheckCircle2
} from 'lucide-react'

// ── helpers ─────────────────────────────────────────────────────────────────

function fmt(val, decimals = 1) {
  return val == null ? '—' : Number(val).toFixed(decimals)
}

function severityVariant(s) {
  if (s === 'critical') return 'destructive'
  if (s === 'warning')  return 'secondary'
  return 'outline'
}

function severityIcon(s) {
  if (s === 'critical') return <XCircle size={14} />
  if (s === 'warning')  return <AlertTriangle size={14} />
  return <Info size={14} />
}

function intensityColor(modifier) {
  if (modifier === 'push')     return 'text-green-400'
  if (modifier === 'back_off') return 'text-yellow-400'
  if (modifier === 'rest')     return 'text-red-400'
  return 'text-blue-400'
}

function freshnessBar(value) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const color = pct > 60 ? 'bg-green-500' : pct > 30 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground w-8 text-right">{pct}%</span>
    </div>
  )
}

// ── sub-components ───────────────────────────────────────────────────────────

function AlertsSection({ alerts }) {
  if (!alerts?.length) return null
  return (
    <div className="flex flex-col gap-2">
      {alerts.map((a, i) => (
        <div key={i} className="flex items-start gap-2 p-3 rounded-md bg-muted/50 border border-border">
          <span className={
            a.severity === 'critical' ? 'text-red-400' :
            a.severity === 'warning'  ? 'text-yellow-400' : 'text-blue-400'
          }>
            {severityIcon(a.severity)}
          </span>
          <span className="text-sm">{a.message}</span>
          <Badge variant={severityVariant(a.severity)} className="ml-auto text-xs shrink-0">
            {a.severity}
          </Badge>
        </div>
      ))}
    </div>
  )
}

function TrainingLoadCard({ tl }) {
  if (!tl) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Activity size={15} /> Training Load
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-3 text-center">
          <div>
            <p className="text-xs text-muted-foreground">CTL</p>
            <p className="text-2xl font-bold">{fmt(tl.ctl, 0)}</p>
            <p className="text-xs text-muted-foreground">fitness</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">ATL</p>
            <p className="text-2xl font-bold">{fmt(tl.atl, 0)}</p>
            <p className="text-xs text-muted-foreground">fatigue</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">TSB</p>
            <p className={`text-2xl font-bold ${tl.tsb >= 0 ? 'text-green-400' : 'text-yellow-400'}`}>
              {tl.tsb >= 0 ? '+' : ''}{fmt(tl.tsb, 0)}
            </p>
            <p className="text-xs text-muted-foreground">form</p>
          </div>
        </div>
        <Separator />
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Today's load</span>
          <span className="font-medium">{fmt(tl.today_load, 0)} TSS</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Ramp rate</span>
          <span className="font-medium">{fmt(tl.ramp_rate, 1)} TSS/wk</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">State</span>
          <span className={`font-semibold capitalize ${intensityColor(tl.intensity_modifier)}`}>
            {tl.freshness_label}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function HRVCard({ hrv }) {
  if (!hrv) return null
  const statusColor = {
    elevated: 'text-green-400',
    normal: 'text-blue-400',
    suppressed: 'text-red-400',
    no_data: 'text-muted-foreground',
  }[hrv.status] ?? 'text-muted-foreground'

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Heart size={15} /> HRV Status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-2">
          <span className={`text-3xl font-bold ${statusColor}`}>
            {fmt(hrv.last_hrv, 0)}
          </span>
          <span className="text-muted-foreground text-sm">ms</span>
          <Badge variant="outline" className={`ml-auto capitalize ${statusColor}`}>
            {hrv.status.replace('_', ' ')}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground text-xs">Baseline</p>
            <p>{fmt(hrv.baseline, 0)} ms</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Deviation</p>
            <p>{hrv.deviation != null ? `${hrv.deviation > 0 ? '+' : ''}${fmt(hrv.deviation, 1)}` : '—'} ms</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Trend</p>
            <p className="capitalize">{hrv.trend ?? '—'}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Baseline SD</p>
            <p>{fmt(hrv.baseline_sd, 1)} ms</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function SleepCard({ sleep }) {
  if (!sleep) return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2"><Moon size={15} /> Sleep</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">No sleep data for today.</p>
      </CardContent>
    </Card>
  )
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2"><Moon size={15} /> Sleep</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold">{fmt(sleep.duration, 1)}</span>
          <span className="text-muted-foreground text-sm">hrs</span>
          {sleep.score != null && (
            <Badge variant="outline" className="ml-auto">Score {fmt(sleep.score, 0)}</Badge>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <p className="text-muted-foreground text-xs">HRV</p>
            <p>{fmt(sleep.hrv, 0)} ms</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">RHR</p>
            <p>{sleep.rhr ?? '—'} bpm</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Body Battery</p>
            <p>{sleep.body_battery != null ? `${sleep.body_battery > 0 ? '+' : ''}${sleep.body_battery}` : '—'}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">HRV Status</p>
            <p className="capitalize">{sleep.hrv_status ?? '—'}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function WeatherCard({ weather }) {
  if (!weather) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Thermometer size={15} /> Weather
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-around text-sm">
          <div className="text-center">
            <Thermometer size={16} className="mx-auto mb-1 text-muted-foreground" />
            <p className="font-medium">{fmt(weather.temp, 1)}°C</p>
          </div>
          <div className="text-center">
            <Wind size={16} className="mx-auto mb-1 text-muted-foreground" />
            <p className="font-medium">{fmt(weather.wind, 1)} m/s</p>
          </div>
          <div className="text-center">
            <Activity size={16} className="mx-auto mb-1 text-muted-foreground" />
            <p className="font-medium">{weather.rain ? `${fmt(weather.rain, 1)} mm` : 'Dry'}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function MuscleFreshnessCard({ mf }) {
  if (!mf?.muscles) return null
  const entries = Object.entries(mf.muscles).sort((a, b) => a[1] - b[1])
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Zap size={15} /> Muscle Freshness
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {entries.map(([muscle, val]) => (
          <div key={muscle}>
            <div className="flex justify-between text-xs mb-1">
              <span className="capitalize">{muscle.replace(/_/g, ' ')}</span>
            </div>
            {freshnessBar(val)}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function RecommendationCard({ rec }) {
  if (!rec) return null
  return (
    <Card className="col-span-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <CheckCircle2 size={15} /> Today's Recommendation
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-xl font-bold">{rec.primary}</p>
            <div className="flex gap-2 mt-1 flex-wrap">
              {rec.intensity && <Badge variant="outline">{rec.intensity}</Badge>}
              {rec.duration  && <Badge variant="outline">{rec.duration}</Badge>}
              {rec.gym_rec?.session_type && (
                <Badge variant="secondary" className="capitalize">
                  {rec.gym_rec.session_type} day
                </Badge>
              )}
            </div>
          </div>
          {rec.why && (
            <p className="text-sm text-muted-foreground max-w-sm">{rec.why}</p>
          )}
          {rec.narrative && (
            <p className="text-sm text-foreground/80 max-w-sm border-l-2 border-primary/40 pl-3 italic">
              {rec.narrative}
            </p>
          )}
        </div>

        {rec.gym_rec?.focus?.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Movement focus</p>
            <div className="flex gap-1 flex-wrap">
              {rec.gym_rec.focus.map(f => (
                <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
              ))}
            </div>
          </div>
        )}

        {rec.exercises?.length > 0 && (
          <>
            <Separator />
            <div>
              <p className="text-xs text-muted-foreground mb-2">Exercise suggestions</p>
              <div className="grid gap-2">
                {rec.exercises.map((ex, i) => (
                  <div key={i} className="flex items-start gap-3 p-2 rounded bg-muted/40 text-sm">
                    <div className="flex-1">
                      <p className="font-medium">{ex.name}</p>
                      {ex.note && <p className="text-xs text-muted-foreground">{ex.note}</p>}
                    </div>
                    <div className="text-right text-xs text-muted-foreground shrink-0">
                      {ex.sets && ex.reps && <p>{ex.sets}×{ex.reps}</p>}
                      {ex.weight_str && <p>{ex.weight_str}</p>}
                      {ex.last_done  && <p>Last: {String(ex.last_done)}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {rec.avoid?.length > 0 && (
          <div className="flex gap-1 flex-wrap items-center">
            <span className="text-xs text-muted-foreground">Avoid:</span>
            {rec.avoid.map(a => (
              <Badge key={a} variant="destructive" className="text-xs">{a}</Badge>
            ))}
          </div>
        )}

        {rec.notes?.length > 0 && (
          <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
            {rec.notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function ReadinessCard({ readiness }) {
  if (!readiness) return null
  const scores = [
    { label: 'Overall',  val: readiness.overall },
    { label: 'Legs',     val: readiness.legs },
    { label: 'Upper',    val: readiness.upper },
    { label: 'Joints',   val: readiness.joints },
  ]
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Dumbbell size={15} /> Readiness Check-in
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-4 gap-2 text-center">
          {scores.map(({ label, val }) => (
            <div key={label}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className={`text-xl font-bold ${val >= 7 ? 'text-green-400' : val >= 4 ? 'text-yellow-400' : 'text-red-400'}`}>
                {val ?? '—'}
              </p>
            </div>
          ))}
        </div>
        {readiness.injury_note && (
          <p className="text-xs text-muted-foreground border-l-2 border-yellow-500 pl-2">
            {readiness.injury_note}
          </p>
        )}
        <div className="flex gap-3 text-xs text-muted-foreground">
          {readiness.time     && <span>Time: <span className="text-foreground capitalize">{readiness.time}</span></span>}
          {readiness.going_out != null && (
            <span>Going out: <span className="text-foreground">{readiness.going_out ? 'yes' : 'no'}</span></span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ── main page ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const today = new Date().toLocaleDateString('en-CA')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['dashboard', today],
    queryFn: () => fetchDashboard(today),
  })

  if (isLoading) {
    return (
      <div className="p-8 text-muted-foreground animate-pulse">Loading dashboard…</div>
    )
  }

  if (isError) {
    return (
      <div className="p-8">
        <p className="text-red-400 font-medium">Failed to load dashboard</p>
        <p className="text-sm text-muted-foreground mt-1">{error?.message}</p>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <span className="text-sm text-muted-foreground">{data.date}</span>
      </div>

      {/* Alerts */}
      <AlertsSection alerts={data.alerts} />

      {/* Main recommendation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RecommendationCard rec={data.recommendation} />
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <TrainingLoadCard tl={data.training_load} />
        <HRVCard          hrv={data.hrv_status} />
        <SleepCard        sleep={data.sleep} />
      </div>

      {/* Lower row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <MuscleFreshnessCard mf={data.muscle_freshness} />
        <ReadinessCard readiness={data.readiness} />
        <WeatherCard weather={data.weather} />
      </div>

      {/* Recent load summary */}
      {data.recent_load?.by_sport?.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Recent Load (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6 flex-wrap text-sm">
              {data.recent_load.by_sport.map(s => (
                <div key={s.key}>
                  <p className="text-muted-foreground text-xs">{s.label}</p>
                  {s.km > 0
                    ? <p className="font-medium">{s.km.toFixed(1)} km</p>
                    : <p className="font-medium">{s.sessions} session{s.sessions !== 1 ? 's' : ''}</p>
                  }
                  {s.minutes > 0 && <p className="text-xs text-muted-foreground">{s.minutes} min</p>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
