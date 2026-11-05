/** کامپوننت‌های پایه رابط — وضعیت با متن و آیکون، حالت بارگذاری/خطا/بدون داده (سند ۱۲.۱) */
import type { ReactNode } from 'react'

export function Chip({ label, tone = 'gray' }: { label: string; tone?: string }) {
  return <span className={`chip chip-${tone}`}>{label}</span>
}

export function StatusChip({ map, value }: { map: Record<string, { label: string; tone: string }>; value: string | null | undefined }) {
  if (!value) return <span className="muted">—</span>
  const meta = map[value] ?? { label: value, tone: 'gray' }
  return <Chip label={meta.label} tone={meta.tone} />
}

export function Card({ title, extra, children, className = '' }: { title?: ReactNode; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || extra) && (
        <header className="card-head">
          <h3>{title}</h3>
          {extra}
        </header>
      )}
      {children}
    </section>
  )
}

export function StatCard({ label, value, hint, to }: { label: string; value: ReactNode; hint?: string; to?: string }) {
  const inner = (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
  return to ? <a className="stat-link" href={to}>{inner}</a> : inner
}

export function Progress({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="muted">—</span>
  return (
    <div className="progress" title={`${value}%`}>
      <div className={`progress-bar ${value >= 100 ? 'done' : ''}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      <span className="progress-text">{value}٪</span>
    </div>
  )
}

export interface Column {
  key: string
  label: string
  render?: (row: any) => ReactNode
  width?: string
}

export function DataTable({ columns, rows, loading, empty = 'داده‌ای یافت نشد', footer }: {
  columns: Column[]
  rows: any[] | undefined
  loading?: boolean
  empty?: string
  footer?: ReactNode
}) {
  if (loading) return <div className="table-loading">در حال بارگذاری…</div>
  if (!rows || rows.length === 0) return <div className="empty-state"><span aria-hidden>📭</span><p>{empty}</p></div>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c.key} style={c.width ? { width: c.width } : undefined}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? i}>
              {columns.map((c) => (
                <td key={c.key}>{c.render ? c.render(row) : (row[c.key] ?? '—')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {footer}
    </div>
  )
}

export function Modal({ open, title, onClose, children, wide }: { open: boolean; title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal>
        <header className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="بستن">✕</button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function ErrorBox({ message }: { message?: string | null }) {
  if (!message) return null
  return <div className="error-box">⚠ {message}</div>
}

export function OkBox({ message }: { message?: string | null }) {
  if (!message) return null
  return <div className="ok-box">✓ {message}</div>
}

export function PageTitle({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-title">
      <div>
        <h2>{title}</h2>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      <div className="page-actions">{actions}</div>
    </div>
  )
}

export function Spinner() {
  return <span className="spinner" aria-label="بارگذاری" />
}
