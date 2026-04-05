import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { LayoutDashboard, Dumbbell, Moon, Activity, Mountain, ClipboardList, BookOpen, RefreshCw, User, LogOut } from 'lucide-react'
import { triggerSync } from '@/api/sync'
import { clearToken } from '@/api/client'

const links = [
  { to: '/',         label: 'Dashboard', icon: LayoutDashboard },
  { to: '/checkin',  label: 'Check-In',  icon: ClipboardList },
  { to: '/training', label: 'Training',  icon: Activity },
  { to: '/strength', label: 'Strength',  icon: Dumbbell },
  { to: '/running',  label: 'Running',   icon: Mountain },
  { to: '/sleep',    label: 'Sleep',     icon: Moon },
  { to: '/journal',  label: 'Journal',   icon: BookOpen },
]

export default function Sidebar() {
  const queryClient = useQueryClient()
  const navigate    = useNavigate()
  const [syncing, setSyncing] = useState(false)

  const user = (() => {
    try { return JSON.parse(localStorage.getItem('qs_user') || '{}') }
    catch { return {} }
  })()

  async function handleSync() {
    if (syncing) return
    setSyncing(true)
    try {
      await triggerSync()
      await queryClient.invalidateQueries({ predicate: q => q.queryKey[0] !== 'me' })
    } catch {
      // non-fatal
    } finally {
      setSyncing(false)
    }
  }

  function handleLogout() {
    clearToken()
    queryClient.clear()
    navigate('/login')
  }

  return (
    <aside className="w-56 shrink-0 border-r border-border h-screen sticky top-0 flex flex-col p-4 gap-1">
      <div className="mb-6 px-2">
        <h1 className="text-sm font-semibold tracking-widest text-muted-foreground uppercase">Quantified</h1>
        <p className="text-xs text-muted-foreground">Strides</p>
      </div>

      {links.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`
          }>
          <Icon size={16} />
          {label}
        </NavLink>
      ))}

      <div className="mt-auto space-y-1">
        <button onClick={handleSync} disabled={syncing}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50">
          <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Syncing…' : 'Sync Garmin'}
        </button>

        <NavLink to="/profile"
          className={({ isActive }) =>
            `w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`
          }>
          <User size={16} />
          {user.name || 'Profile'}
        </NavLink>

        <button onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors text-muted-foreground hover:bg-muted hover:text-foreground">
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
