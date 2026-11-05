/** چیدمان اصلی: نوار کنار، سربرگ، اعلان‌ها (سند ۱۲.۱) */
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useAuth } from '../auth'
import { ROLES_FA } from '../constants'
import { toJalaliStr } from '../jalali'

interface Notif { id: string; title: string; body: string | null; is_read: boolean; created_at: string; entity_type?: string | null }

function NotificationsBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<{ items: Notif[]; unread: number }>('/notifications', { params: { size: 15 } }),
    refetchInterval: 30000,
  })
  useEffect(() => {
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])
  const markAll = async () => {
    await api('/notifications/read-all', { method: 'POST' })
    qc.invalidateQueries({ queryKey: ['notifications'] })
  }
  const markOne = async (id: string) => {
    await api('/notifications/read', { method: 'POST', body: { ids: [id] } })
    qc.invalidateQueries({ queryKey: ['notifications'] })
  }
  return (
    <div className="bell-wrap" ref={ref}>
      <button className="icon-btn" onClick={() => setOpen((o) => !o)} aria-label="اعلان‌ها">
        🔔
        {!!data?.unread && <span className="badge">{data.unread}</span>}
      </button>
      {open && (
        <div className="dropdown notif-drop">
          <div className="drop-head">
            <strong>اعلان‌ها</strong>
            <button className="btn btn-ghost btn-sm" onClick={markAll}>خواندن همه</button>
          </div>
          {(data?.items ?? []).length === 0 && <p className="muted pad">اعلانی نیست</p>}
          {(data?.items ?? []).map((n) => (
            <button key={n.id} className={`notif-item ${n.is_read ? '' : 'unread'}`} onClick={() => markOne(n.id)}>
              <strong>{n.title}</strong>
              {n.body && <span>{n.body}</span>}
              <time>{toJalaliStr(n.created_at, true)}</time>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const NAV = [
  { to: '/', label: 'داشبورد', icon: '🏠', roles: null },
  { to: '/projects', label: 'پروژه‌ها', icon: '📁', roles: null },
  { to: '/tasks', label: 'وظایف', icon: '✅', roles: null },
  { to: '/activities', label: 'فعالیت‌ها', icon: '📝', roles: null },
  { to: '/weekly-report', label: 'گزارش هفتگی', icon: '📅', roles: null },
  { to: '/review-queue', label: 'بررسی گزارش‌ها', icon: '🗂', roles: ['unit_manager', 'project_manager', 'senior_manager', 'pmo'] },
  { to: '/documents', label: 'مستندات', icon: '📎', roles: null },
  { to: '/blockers', label: 'موانع و ریسک‌ها', icon: '🚧', roles: null },
  { to: '/users', label: 'کاربران', icon: '👥', roles: ['sys_admin'] },
  { to: '/org-units', label: 'ساختار سازمانی', icon: '🏢', roles: ['sys_admin', 'unit_manager', 'senior_manager', 'pmo'] },
  { to: '/audit', label: 'ممیزی', icon: '🔍', roles: ['auditor', 'senior_manager', 'pmo', 'sys_admin'] },
  { to: '/settings', label: 'تنظیمات', icon: '⚙️', roles: ['sys_admin'] },
]

export default function Layout() {
  const { user, logout, hasRole } = useAuth()
  const nav = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  if (!user) return null
  const items = NAV.filter((n) => !n.roles || hasRole(...n.roles))

  return (
    <div className="layout">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-logo">ر</span>
          <div>
            <strong>راندمان</strong>
            <small>دیدبان عملکرد سازمان</small>
          </div>
        </div>
        <nav>
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} onClick={() => setMenuOpen(false)}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <span aria-hidden>{n.icon}</span> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot muted">نسخه ۱.۰ — استقرار داخلی</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setMenuOpen((o) => !o)} aria-label="منو">☰</button>
          <div className="spacer" />
          <NotificationsBell />
          <div className="user-chip">
            <div className="avatar">{user.first_name?.[0] ?? '؟'}</div>
            <div>
              <strong>{user.full_name}</strong>
              <small>{user.roles.map((r) => ROLES_FA[r] ?? r).join('، ') || '—'}</small>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={async () => { await logout(); nav('/login') }}>خروج</button>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
