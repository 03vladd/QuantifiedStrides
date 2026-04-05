import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { fetchSleepList, fetchSleepDetail, fetchSleepTrends } from '@/api/sleep'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Moon, ChevronRight } from 'lucide-react'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDur(min) {
  if (!min) return '—'
  return `${Math.floor(min/60)}h ${String(min%60).padStart(2,'0')}m`
}

function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})
}

function scoreColor(s) {
  if (s == null) return '#666'
  if (s >= 80) return '#00cc7a'
  if (s >= 60) return '#fdcb6e'
  return '#ff6b6b'
}

const FEEDBACK_LABELS = {
  POSITIVE_RECOVERING:'Recovering well', POSITIVE_TRAINING_ADAPTED:'Training adapted',
  POSITIVE_RESTORATIVE:'Restorative',    NEGATIVE_POOR_SLEEP:'Poor sleep',
  NEGATIVE_HIGH_ACTIVITY:'High activity stress', NEUTRAL_BALANCED:'Balanced',
  NEGATIVE_UNUSUAL_HR:'Unusual HR',      POSITIVE_LATE_BED_TIME:'Good sleep (late bedtime)',
}

const STAGE_COLORS = { Deep:'#4a6fa5', Light:'#74b9ff', REM:'#a29bfe', Awake:'#636e72' }

const sel = 'text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground'

// ── trend charts ──────────────────────────────────────────────────────────────

function TrendCharts({ trends }) {
  if (!trends?.length) return null

  const data = trends.map(t => ({
    date: t.sleep_date,
    score: t.sleep_score,
    hrv: t.overnight_hrv,
    rhr: t.rhr,
    dur: t.duration_minutes ? +(t.duration_minutes/60).toFixed(1) : null,
  }))

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-1"><CardTitle className="text-xs">Sleep Score</CardTitle></CardHeader>
        <CardContent className="h-36 pt-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{top:4,right:4,left:0,bottom:0}}>
              <XAxis dataKey="date" hide />
              <YAxis domain={[0,100]} tick={{fontSize:10,fill:'var(--muted-foreground)'}} width={28} />
              <Tooltip formatter={v=>[v,'Score']} labelFormatter={fmtDate}
                contentStyle={{backgroundColor:'var(--card)',border:'1px solid var(--border)',borderRadius:6}}
                labelStyle={{color:'var(--muted-foreground)',fontSize:11}} />
              <Bar dataKey="score" radius={[2,2,0,0]}>
                {data.map((d,i) => <Cell key={i} fill={scoreColor(d.score)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1"><CardTitle className="text-xs">HRV & Resting HR</CardTitle></CardHeader>
        <CardContent className="h-36 pt-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{top:4,right:4,left:0,bottom:0}}>
              <XAxis dataKey="date" hide />
              <YAxis yAxisId="hrv" tick={{fontSize:10,fill:'var(--muted-foreground)'}} width={28} />
              <YAxis yAxisId="rhr" orientation="right" tick={{fontSize:10,fill:'var(--muted-foreground)'}} width={28} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <Tooltip contentStyle={{backgroundColor:'var(--card)',border:'1px solid var(--border)',borderRadius:6}}
                labelFormatter={fmtDate} labelStyle={{color:'var(--muted-foreground)',fontSize:11}} />
              <Line yAxisId="hrv" type="monotone" dataKey="hrv" name="HRV (ms)"
                stroke="#00cc7a" strokeWidth={2} dot={false} />
              <Line yAxisId="rhr" type="monotone" dataKey="rhr" name="RHR (bpm)"
                stroke="#ff6b6b" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}

// ── sleep detail ──────────────────────────────────────────────────────────────

function SleepDetail({ sleepId }) {
  const { data: d, isLoading } = useQuery({
    queryKey: ['sleep', sleepId],
    queryFn: () => fetchSleepDetail(sleepId),
    enabled: !!sleepId,
  })

  if (isLoading) return <p className="text-sm text-muted-foreground animate-pulse">Loading…</p>
  if (!d) return null

  const feedback = FEEDBACK_LABELS[d.sleep_score_feedback] ?? d.sleep_score_feedback
  const stages = [
    { name:'Deep',  min: d.time_in_deep  || 0, color: STAGE_COLORS.Deep },
    { name:'REM',   min: d.time_in_rem   || 0, color: STAGE_COLORS.REM },
    { name:'Light', min: d.time_in_light || 0, color: STAGE_COLORS.Light },
    { name:'Awake', min: d.time_in_awake || 0, color: STAGE_COLORS.Awake },
  ]
  const totalStage = stages.reduce((a,b) => a+b.min, 0)
  const deepPct  = totalStage ? stages[0].min / totalStage * 100 : 0
  const remPct   = totalStage ? stages[1].min / totalStage * 100 : 0
  const awakePct = totalStage ? stages[3].min / totalStage * 100 : 0

  const delta = (a, b) => a != null && b != null ? (a - b) : null
  const fmtDelta = (v, invert) => {
    if (v == null) return null
    const sign = v > 0 ? '+' : ''
    const color = invert ? (v > 0 ? 'text-red-400' : 'text-green-400') : (v > 0 ? 'text-green-400' : 'text-red-400')
    return <span className={`text-xs ${color}`}>{sign}{v.toFixed(1)} vs 7d</span>
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="font-semibold">{new Date(d.sleep_date).toLocaleDateString('en-GB',{weekday:'long',day:'2-digit',month:'long',year:'numeric'})}</p>
        {feedback && <p className="text-xs text-muted-foreground">{feedback}</p>}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {[
          { label:'Sleep Score', val: d.sleep_score?.toFixed(0), delta: delta(d.sleep_score, d.baseline_score) },
          { label:'Duration',    val: fmtDur(d.duration_minutes), delta: delta(d.duration_minutes, d.baseline_duration) },
          { label:'HRV',         val: d.overnight_hrv ? `${d.overnight_hrv.toFixed(0)} ms` : '—', delta: delta(d.overnight_hrv, d.baseline_hrv) },
          { label:'Resting HR',  val: d.rhr ? `${d.rhr} bpm` : '—', delta: delta(d.rhr, d.baseline_rhr), invert: true },
          { label:'Body Battery',val: d.body_battery_change != null ? (d.body_battery_change > 0 ? `+${d.body_battery_change}` : `${d.body_battery_change}`) : '—' },
          { label:'Sleep Stress',val: d.avg_sleep_stress?.toFixed(0) ?? '—' },
        ].map(({label, val, delta: dv, invert}) => (
          <div key={label}>
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="text-sm font-medium">{val}</p>
            {fmtDelta(dv, invert)}
          </div>
        ))}
      </div>

      {totalStage > 0 && (
        <>
          <Separator />
          <div>
            <p className="text-xs text-muted-foreground mb-2">Sleep Stages</p>
            <div className="h-5 rounded overflow-hidden flex">
              {stages.filter(s => s.min > 0).map(s => (
                <div key={s.name} style={{width:`${s.min/totalStage*100}%`, background:s.color}}
                  title={`${s.name}: ${fmtDur(s.min)}`} />
              ))}
            </div>
            <div className="flex gap-3 flex-wrap mt-2">
              {stages.filter(s => s.min > 0).map(s => (
                <span key={s.name} className="text-xs text-muted-foreground flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-sm" style={{background:s.color}} />
                  {s.name} {fmtDur(s.min)} ({(s.min/totalStage*100).toFixed(0)}%)
                </span>
              ))}
            </div>
            <div className="mt-2 space-y-0.5">
              {deepPct  >= 20 && <p className="text-xs text-green-500">✓ Good deep sleep (≥20%)</p>}
              {deepPct  >  0 && deepPct < 20 && <p className="text-xs text-yellow-500">⚠ Low deep sleep ({deepPct.toFixed(0)}% — target ≥20%)</p>}
              {remPct   >= 20 && <p className="text-xs text-green-500">✓ Good REM (≥20%)</p>}
              {remPct   >  0 && remPct  < 20 && <p className="text-xs text-yellow-500">⚠ Low REM ({remPct.toFixed(0)}% — target ≥20%)</p>}
              {awakePct > 10 && <p className="text-xs text-yellow-500">⚠ Fragmented — {awakePct.toFixed(0)}% awake time</p>}
            </div>
          </div>
        </>
      )}

      {d.overnight_hrv && d.baseline_hrv && (
        <>
          <Separator />
          <div>
            <p className="text-xs text-muted-foreground mb-2">HRV vs Baseline</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-muted-foreground">Tonight</p>
                <p className="text-sm font-medium">{d.overnight_hrv.toFixed(0)} ms</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">7-day Baseline</p>
                <p className="text-sm font-medium">{d.baseline_hrv.toFixed(1)} ms</p>
              </div>
            </div>
            {(() => {
              const diff = d.overnight_hrv - d.baseline_hrv
              if (diff > 3)        return <p className="text-xs text-green-500 mt-1">HRV elevated — good recovery signal.</p>
              if (diff < -5)       return <p className="text-xs text-red-400 mt-1">HRV suppressed — consider reducing training load.</p>
              if (diff < -1)       return <p className="text-xs text-yellow-500 mt-1">HRV slightly below baseline — monitor.</p>
              return <p className="text-xs text-muted-foreground mt-1">HRV tracking baseline closely — stable recovery.</p>
            })()}
          </div>
        </>
      )}
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Sleep() {
  const [days,       setDays]       = useState(90)
  const [selectedId, setSelectedId] = useState(null)

  const { data: list     = [] } = useQuery({ queryKey:['sleep-list', days],   queryFn: () => fetchSleepList(days) })
  const { data: trends   = [] } = useQuery({ queryKey:['sleep-trends', days], queryFn: () => fetchSleepTrends(days) })

  return (
    <div className="p-6 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2"><Moon size={20} /> Sleep</h2>
        <select value={days} onChange={e=>{setDays(Number(e.target.value));setSelectedId(null)}} className={sel}>
          <option value={30}>Last 30 days</option>
          <option value={60}>Last 60 days</option>
          <option value={90}>Last 3 months</option>
          <option value={180}>Last 6 months</option>
        </select>
      </div>

      <TrendCharts trends={trends} />

      {list.length === 0 ? (
        <p className="text-sm text-muted-foreground">No sleep data in this period.</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4">
          <div className="space-y-1 max-h-[calc(100vh-400px)] overflow-y-auto pr-1">
            <p className="text-xs text-muted-foreground px-1 mb-2">{list.length} nights</p>
            {list.map(s => {
              const dot = s.sleep_score >= 80 ? '🟢' : s.sleep_score >= 60 ? '🟡' : s.sleep_score ? '🔴' : '⚪'
              return (
                <button key={s.sleep_id}
                  onClick={() => setSelectedId(s.sleep_id === selectedId ? null : s.sleep_id)}
                  className={`w-full text-left px-3 py-2.5 rounded-md border transition-colors ${
                    s.sleep_id === selectedId ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'
                  }`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{dot} {fmtDate(s.sleep_date)}</span>
                    <ChevronRight size={14} className="opacity-50" />
                  </div>
                  <div className="text-xs opacity-60 mt-0.5 flex gap-2">
                    {s.sleep_score && <span>Score {s.sleep_score.toFixed(0)}</span>}
                    {s.duration_minutes && <span>{fmtDur(s.duration_minutes)}</span>}
                    {s.overnight_hrv && <span>HRV {s.overnight_hrv.toFixed(0)}</span>}
                    {s.body_battery_change != null && <span>⚡{s.body_battery_change > 0 ? '+' : ''}{s.body_battery_change}</span>}
                  </div>
                </button>
              )
            })}
          </div>

          <Card>
            <CardContent className="pt-4">
              {selectedId
                ? <SleepDetail sleepId={selectedId} />
                : <p className="text-sm text-muted-foreground">Select a night to see details.</p>
              }
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
