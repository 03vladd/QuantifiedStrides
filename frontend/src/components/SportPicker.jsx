const SPORTS = [
  { key: 'trail_run',  label: 'Trail Running' },
  { key: 'xc_mtb',    label: 'XC MTB' },
  { key: 'climbing',  label: 'Climbing' },
  { key: 'ski',       label: 'Skiing' },
  { key: 'snowboard', label: 'Snowboarding' },
  { key: 'road_run',  label: 'Road Running' },
  { key: 'bike',      label: 'Road Cycling' },
]

/**
 * value    — { trail_run: 3, climbing: 5, ... }  (absent key = not active)
 * onChange — (newValue: object) => void
 */
export default function SportPicker({ value = {}, onChange }) {
  function toggle(key, checked) {
    const updated = { ...value }
    if (!checked) {
      delete updated[key]
    } else {
      updated[key] = 3   // default priority when first enabling
    }
    onChange(updated)
  }

  function setPriority(key, priority) {
    onChange({ ...value, [key]: priority })
  }

  return (
    <div className="rounded-lg border border-border overflow-hidden divide-y divide-border">
      {SPORTS.map(s => {
        const priority = value[s.key] ?? 0
        const active   = priority > 0
        return (
          <div
            key={s.key}
            className={`flex items-center gap-3 px-4 py-3 transition-colors ${active ? 'bg-primary/5' : 'bg-background'}`}
          >
            <input
              type="checkbox"
              id={`sp-${s.key}`}
              checked={active}
              onChange={e => toggle(s.key, e.target.checked)}
              className="w-4 h-4 accent-primary shrink-0 cursor-pointer"
            />
            <label
              htmlFor={`sp-${s.key}`}
              className="flex-1 text-sm cursor-pointer select-none"
            >
              {s.label}
            </label>
            {active && (
              <select
                value={priority}
                onChange={e => setPriority(s.key, Number(e.target.value))}
                className="bg-background border border-border rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
              >
                <option value={1}>1 – light</option>
                <option value={2}>2</option>
                <option value={3}>3 – moderate</option>
                <option value={4}>4</option>
                <option value={5}>5 – primary</option>
              </select>
            )}
          </div>
        )
      })}
    </div>
  )
}
