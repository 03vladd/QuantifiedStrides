import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { fetchJournal, saveJournal, fetchJournalHistory } from '@/api/checkin'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { BookOpen, ChevronDown, ChevronRight } from 'lucide-react'

const LOAD_FEEL_LABEL = {
  '-2': 'Much too easy',
  '-1': 'Slightly easy',
   '0': 'Just right',
   '1': 'Slightly hard',
   '2': 'Too hard',
}
const LOAD_FEEL_COLOR = {
  '-2': 'text-green-400',
  '-1': 'text-emerald-400',
   '0': 'text-yellow-400',
   '1': 'text-orange-400',
   '2': 'text-red-400',
}

// ── helpers ───────────────────────────────────────────────────────────────────

const today = new Date().toLocaleDateString('en-CA')

const sel = 'text-sm bg-background border border-border rounded-md px-3 py-1.5 text-foreground'

function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtShort(d) {
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

const axisStyle = { fontSize: 11, fill: 'var(--muted-foreground)' }
const tooltipStyle = {
  contentStyle: { backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: 6 },
  labelStyle: { color: 'var(--muted-foreground)', fontSize: 11 },
}

// ── Write Tab ─────────────────────────────────────────────────────────────────

function WriteTab() {
  const qc = useQueryClient()
  const [date, setDate] = useState(today)
  const [content, setContent] = useState('')
  const [saved, setSaved] = useState(false)

  const { data: existing } = useQuery({
    queryKey: ['journal', date],
    queryFn: () => fetchJournal(date).catch(() => null),
    staleTime: 30_000,
  })

  useEffect(() => {
    setContent(existing?.content ?? '')
  }, [existing])

  const { data: dayContext = [] } = useQuery({
    queryKey: ['journal-history', 1],
    queryFn: () => fetchJournalHistory(1),
  })

  const mut = useMutation({
    mutationFn: saveJournal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['journal', date] })
      qc.invalidateQueries({ queryKey: ['journal-history'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  function handleDateChange(v) { setDate(v); setSaved(false); setContent('') }

  function submit(e) {
    e.preventDefault()
    if (!content.trim()) return
    mut.mutate({ entry_date: date, content: content.trim() })
  }

  const todayRow = dayContext?.find(r => r.entry_date === date)

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <label className="text-sm text-muted-foreground">Entry date</label>
        <input type="date" value={date} onChange={e => handleDateChange(e.target.value)} className={sel} />
      </div>

      {existing?.content && (
        <p className="text-xs text-blue-400 bg-blue-950/30 border border-blue-800/40 rounded px-3 py-2">
          Entry for this date exists — editing it.
        </p>
      )}

      <form onSubmit={submit} className="space-y-3">
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="How did the day go? How's the body feeling? Anything notable about training, recovery, or life stress? …"
          rows={8}
          className={`${sel} w-full resize-none`}
        />
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={mut.isPending || !content.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50"
          >
            {mut.isPending ? 'Saving…' : 'Save Entry'}
          </button>
          {saved && <span className="text-xs text-green-400">Saved!</span>}
          {mut.isError && <span className="text-xs text-red-400">Save failed.</span>}
        </div>
      </form>

      {/* Today's context */}
      {todayRow && (todayRow.overall_feel || todayRow.session_rpe) && (
        <>
          <Separator />
          <div>
            <p className="text-xs text-muted-foreground mb-3 font-medium uppercase tracking-wide">Today's data context</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {todayRow.overall_feel && (
                <div className="text-sm space-y-1">
                  <p className="font-medium">Morning check-in</p>
                  <p className="text-muted-foreground">
                    Feel <span className="text-foreground font-medium">{todayRow.overall_feel}/10</span> · legs {todayRow.legs_feel}/10 · joints {todayRow.joint_feel}/10
                  </p>
                  {todayRow.injury_note && (
                    <p className="text-xs text-yellow-400">🩹 {todayRow.injury_note}</p>
                  )}
                </div>
              )}
              {todayRow.session_rpe && (
                <div className="text-sm space-y-1">
                  <p className="font-medium">Post-workout</p>
                  <p className="text-muted-foreground">
                    RPE <span className="text-foreground font-medium">{todayRow.session_rpe}/10</span> · quality {todayRow.session_quality}/10
                  </p>
                  {todayRow.reflection_notes && (
                    <p className="text-xs text-muted-foreground italic">{todayRow.reflection_notes}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── History Tab ───────────────────────────────────────────────────────────────

function HistoryRow({ row }) {
  const [open, setOpen] = useState(false)
  const hasReadiness  = row.overall_feel != null
  const hasReflection = row.session_rpe != null
  const hasJournal    = !!row.journal_note

  const badges = []
  if (hasReadiness)  badges.push(`feel ${row.overall_feel}/10`)
  if (hasReflection) badges.push(`RPE ${row.session_rpe}/10`)
  if (hasJournal)    badges.push('📓')
  if (row.injury_note) badges.push('🩹')

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted transition-colors"
      >
        <div>
          <span className="text-sm font-medium">{fmtDate(row.entry_date)}</span>
          <span className="ml-3 text-xs text-muted-foreground">{badges.join('  ·  ') || 'no data'}</span>
        </div>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>

      {open && (
        <div className="px-4 pb-4 pt-2 border-t border-border space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              {hasReadiness ? (
                <>
                  <p className="text-xs font-medium mb-1">Morning check-in</p>
                  <p className="text-sm text-muted-foreground">
                    Overall <span className="text-foreground font-medium">{row.overall_feel}/10</span> · legs {row.legs_feel}/10 · upper {row.upper_body_feel}/10 · joints {row.joint_feel}/10
                  </p>
                  {row.injury_note && <p className="text-xs text-yellow-400 mt-0.5">🩹 {row.injury_note}</p>}
                  {(row.time_available || row.going_out_tonight) && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {[row.time_available && `time: ${row.time_available}`, row.going_out_tonight && 'going out tonight'].filter(Boolean).join('  ·  ')}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-xs text-muted-foreground italic">No morning check-in</p>
              )}
            </div>

            <div>
              {hasReflection ? (
                <>
                  <p className="text-xs font-medium mb-1">Post-workout reflection</p>
                  <p className="text-sm text-muted-foreground">
                    RPE <span className="text-foreground font-medium">{row.session_rpe}/10</span> · quality {row.session_quality}/10
                  </p>
                  {row.load_feel != null && (
                    <p className={`text-xs mt-0.5 ${LOAD_FEEL_COLOR[String(row.load_feel)]}`}>
                      Load: {LOAD_FEEL_LABEL[String(row.load_feel)]}
                    </p>
                  )}
                  {row.reflection_notes && (
                    <p className="text-xs text-muted-foreground mt-0.5 border-l-2 border-muted pl-2 italic">{row.reflection_notes}</p>
                  )}
                </>
              ) : (
                <p className="text-xs text-muted-foreground italic">No post-workout reflection</p>
              )}
            </div>
          </div>

          {hasJournal && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium mb-1">Journal note</p>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">{row.journal_note}</p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function HistoryTab() {
  const [days, setDays] = useState(90)

  const { data: rows = [], isFetching } = useQuery({
    queryKey: ['journal-history', days],
    queryFn: () => fetchJournalHistory(days),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select value={days} onChange={e => setDays(Number(e.target.value))} className={sel}>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 3 months</option>
          <option value={180}>Last 6 months</option>
          <option value={365}>Last year</option>
        </select>
        {isFetching && <span className="text-xs text-muted-foreground animate-pulse">Loading…</span>}
      </div>

      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No entries yet in this period.</p>
      ) : (
        <div className="space-y-2">
          {rows.map(row => <HistoryRow key={row.entry_date} row={row} />)}
        </div>
      )}
    </div>
  )
}

// ── Trends Tab ────────────────────────────────────────────────────────────────

function TrendsTab() {
  const [days, setDays] = useState(60)

  const { data: rows = [] } = useQuery({
    queryKey: ['journal-history', days],
    queryFn: () => fetchJournalHistory(days),
  })

  const readinessData = rows
    .filter(r => r.overall_feel != null)
    .map(r => ({ date: r.entry_date, overall: r.overall_feel, legs: r.legs_feel, joints: r.joint_feel }))
    .reverse()

  const rpeData = rows
    .filter(r => r.session_rpe != null)
    .map(r => ({ date: r.entry_date, rpe: r.session_rpe, quality: r.session_quality }))
    .reverse()

  const injuryRows = rows.filter(r => r.injury_note)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <select value={days} onChange={e => setDays(Number(e.target.value))} className={sel}>
          <option value={30}>30 days</option>
          <option value={60}>60 days</option>
          <option value={90}>90 days</option>
          <option value={180}>180 days</option>
        </select>
      </div>

      {readinessData.length === 0 && rpeData.length === 0 ? (
        <p className="text-sm text-muted-foreground">No check-in or reflection data in this period.</p>
      ) : (
        <>
          {readinessData.length > 0 && (
            <Card>
              <CardHeader className="pb-1"><CardTitle className="text-sm">Readiness Scores</CardTitle></CardHeader>
              <CardContent className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={readinessData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtShort} />
                    <YAxis domain={[0, 10]} tick={axisStyle} width={24} />
                    <Tooltip
                      {...tooltipStyle}
                      formatter={(v, n) => [`${v}/10`, n]}
                      labelFormatter={d => new Date(d).toLocaleDateString('en-GB')}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="overall" name="Overall" stroke="#00cec9" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="legs"    name="Legs"    stroke="#6c5ce7" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
                    <Line type="monotone" dataKey="joints"  name="Joints"  stroke="#fd79a8" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {rpeData.length > 0 && (
            <Card>
              <CardHeader className="pb-1"><CardTitle className="text-sm">Session RPE & Quality</CardTitle></CardHeader>
              <CardContent className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rpeData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={axisStyle} tickFormatter={fmtShort} />
                    <YAxis domain={[0, 10]} tick={axisStyle} width={24} />
                    <Tooltip
                      {...tooltipStyle}
                      formatter={(v, n) => [`${v}/10`, n]}
                      labelFormatter={d => new Date(d).toLocaleDateString('en-GB')}
                    />
                    <Legend />
                    <Bar dataKey="rpe"     name="RPE"             fill="#e17055" opacity={0.7} radius={[2,2,0,0]} />
                    <Bar dataKey="quality" name="Session quality"  fill="#55efc4" opacity={0.8} radius={[2,2,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {injuryRows.length > 0 && (
            <Card>
              <CardHeader className="pb-1"><CardTitle className="text-sm">Injury / Discomfort Notes</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-1">
                  {injuryRows.map(r => (
                    <li key={r.entry_date} className="text-sm text-muted-foreground">
                      <span className="text-foreground font-medium">
                        {new Date(r.entry_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>: {r.injury_note}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Journal() {
  return (
    <div className="p-6 space-y-4 max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
        <BookOpen size={20} /> Journal
      </h2>

      <Tabs defaultValue="write">
        <TabsList>
          <TabsTrigger value="write">Write Entry</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
        </TabsList>
        <TabsContent value="write"   className="mt-4"><WriteTab /></TabsContent>
        <TabsContent value="history" className="mt-4"><HistoryTab /></TabsContent>
        <TabsContent value="trends"  className="mt-4"><TrendsTab /></TabsContent>
      </Tabs>
    </div>
  )
}
