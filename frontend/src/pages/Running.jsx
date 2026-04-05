import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { fetchRunningTrends, fetchBiomechanics } from '@/api/running'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtPace(v) {
  if (!v || v <= 0) return '—'
  const m = Math.floor(v), s = Math.round((v - m) * 60)
  return `${m}:${String(s).padStart(2,'0')}`
}

function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-GB',{day:'2-digit',month:'short'})
}

const sel = 'text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground'

const chartProps = {
  margin: { top:4, right:8, left:0, bottom:4 },
}

const axisStyle = { fontSize:11, fill:'var(--muted-foreground)' }

function ChartCard({ title, children }) {
  return (
    <Card>
      <CardHeader className="pb-1"><CardTitle className="text-sm">{title}</CardTitle></CardHeader>
      <CardContent className="h-48">{children}</CardContent>
    </Card>
  )
}

const tooltipStyle = {
  contentStyle: { backgroundColor:'var(--card)', border:'1px solid var(--border)', borderRadius:6 },
  labelStyle:   { color:'var(--muted-foreground)', fontSize:11 },
}

// ── economy tab ───────────────────────────────────────────────────────────────

function EconomyTab({ data }) {
  if (!data?.length) return <p className="text-sm text-muted-foreground">No running data available.</p>

  const chartData = data.map(d => ({
    date:      d.workout_date,
    pace:      d.avg_pace,
    gap:       d.avg_gap,
    decoup:    d.decoupling_pct,
    rei:       d.rei,
    km:        d.distance_km,
  }))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ChartCard title="Avg Pace vs GAP (min/km)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} {...chartProps}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtDate} />
              <YAxis tick={axisStyle} tickFormatter={fmtPace} reversed width={44} />
              <Tooltip {...tooltipStyle} formatter={(v,n) => [fmtPace(v)+' /km', n]} labelFormatter={d=>new Date(d).toLocaleDateString('en-GB')} />
              <Legend />
              <Line type="monotone" dataKey="pace" name="Avg Pace" stroke="#4da6ff" strokeWidth={2} dot={{r:3}} />
              <Line type="monotone" dataKey="gap"  name="GAP"      stroke="#55efc4" strokeWidth={2} dot={{r:3}} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Aerobic Decoupling (%)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData.filter(d => d.decoup != null)} {...chartProps}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtDate} />
              <YAxis tick={axisStyle} tickFormatter={v=>`${v.toFixed(1)}%`} width={44} />
              <Tooltip {...tooltipStyle} formatter={v=>[`${v?.toFixed(1)}%`, 'Decoupling']} />
              {/* reference line at 5% */}
              <Line type="monotone" dataKey="decoup" name="Decoupling" stroke="#e17055" strokeWidth={2} dot={d => {
                const color = d.payload.decoup > 5 ? '#d63031' : '#00cc7a'
                return <circle key={d.index} cx={d.cx} cy={d.cy} r={4} fill={color} />
              }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Decoupling legend */}
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block"/>≤5% efficient aerobic base</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block"/>&gt;5% cardiac drift</span>
      </div>

      {/* Table summary */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="text-left py-1.5">Date</th>
              <th className="text-left py-1.5">Dist</th>
              <th className="text-left py-1.5">Pace</th>
              <th className="text-left py-1.5">GAP</th>
              <th className="text-left py-1.5">Decoupling</th>
              <th className="text-left py-1.5">HR</th>
            </tr>
          </thead>
          <tbody>
            {data.map(d => (
              <tr key={d.workout_id} className="border-b border-border/40">
                <td className="py-1">{new Date(d.workout_date).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'2-digit'})}</td>
                <td className="py-1">{d.distance_km.toFixed(1)} km</td>
                <td className="py-1">{fmtPace(d.avg_pace)}</td>
                <td className="py-1">{fmtPace(d.avg_gap)}</td>
                <td className="py-1">
                  {d.decoupling_pct != null ? (
                    <span className={d.decoupling_pct > 5 ? 'text-red-400' : 'text-green-400'}>
                      {d.decoupling_pct.toFixed(1)}%
                    </span>
                  ) : '—'}
                </td>
                <td className="py-1">{d.avg_hr ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── biomechanics tab ──────────────────────────────────────────────────────────

function BiomechanicsTab({ data }) {
  if (!data?.length) return <p className="text-sm text-muted-foreground">No biomechanics data available.</p>

  const chartData = data.map(d => ({
    date:    d.workout_date,
    cadence: d.avg_cadence,
    gct:     d.avg_gct,
    vo:      d.avg_vo,
    fatigue: d.fatigue_score,
  }))

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <ChartCard title="Cadence (spm)">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData.filter(d=>d.cadence)} {...chartProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtDate} />
            <YAxis tick={axisStyle} width={36} />
            <Tooltip {...tooltipStyle} formatter={v=>[`${v?.toFixed(0)} spm`,'Cadence']} />
            <Line type="monotone" dataKey="cadence" stroke="#a29bfe" strokeWidth={2} dot={{r:3}} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Ground Contact Time (ms)">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData.filter(d=>d.gct)} {...chartProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtDate} />
            <YAxis tick={axisStyle} width={40} />
            <Tooltip {...tooltipStyle} formatter={v=>[`${v?.toFixed(0)} ms`,'GCT']} />
            <Line type="monotone" dataKey="gct" stroke="#fd79a8" strokeWidth={2} dot={{r:3}} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Vertical Oscillation (mm)">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData.filter(d=>d.vo)} {...chartProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtDate} />
            <YAxis tick={axisStyle} width={36} />
            <Tooltip {...tooltipStyle} formatter={v=>[`${v?.toFixed(1)} mm`,'Vert Osc']} />
            <Line type="monotone" dataKey="vo" stroke="#00cec9" strokeWidth={2} dot={{r:3}} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Fatigue Score (0–100)">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData.filter(d=>d.fatigue != null)} {...chartProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtDate} />
            <YAxis domain={[0,100]} tick={axisStyle} width={28} />
            <Tooltip {...tooltipStyle} formatter={v=>[`${v?.toFixed(0)}`,'Fatigue']} />
            <Line type="monotone" dataKey="fatigue" stroke="#e17055" strokeWidth={2} dot={d=>{
              const color = d.payload.fatigue > 70 ? '#d63031' : d.payload.fatigue > 40 ? '#fdcb6e' : '#00cc7a'
              return <circle key={d.index} cx={d.cx} cy={d.cy} r={4} fill={color} />
            }} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Running() {
  const [days, setDays] = useState(365)

  const { data: trends   = [] } = useQuery({ queryKey:['running-trends', days],       queryFn: () => fetchRunningTrends(days) })
  const { data: biomech  = [] } = useQuery({ queryKey:['running-biomechanics', days], queryFn: () => fetchBiomechanics(days) })

  return (
    <div className="p-6 space-y-4 max-w-6xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Running Analytics</h2>
        <select value={days} onChange={e=>setDays(Number(e.target.value))} className={sel}>
          <option value={90}>Last 3 months</option>
          <option value={180}>Last 6 months</option>
          <option value={365}>Last year</option>
          <option value={548}>Last 18 months</option>
          <option value={730}>Last 2 years</option>
        </select>
      </div>

      <Tabs defaultValue="economy">
        <TabsList>
          <TabsTrigger value="economy">Economy & GAP</TabsTrigger>
          <TabsTrigger value="biomechanics">Biomechanics</TabsTrigger>
        </TabsList>
        <TabsContent value="economy"     className="mt-4"><EconomyTab     data={trends} /></TabsContent>
        <TabsContent value="biomechanics" className="mt-4"><BiomechanicsTab data={biomech} /></TabsContent>
      </Tabs>
    </div>
  )
}
