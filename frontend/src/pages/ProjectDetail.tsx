import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Card, Chip, DataTable, ErrorBox, Field, Modal, PageTitle, Progress, StatusChip } from '../components/ui'
import { BLOCKER_STATUS, PROJECT_STATUS } from '../constants'
import { toJalaliStr } from '../jalali'

export default function ProjectDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { hasRole } = useAuth()
  const [tab, setTab] = useState('overview')
  const [error, setError] = useState<string | null>(null)

  const { data: p, isLoading } = useQuery({ queryKey: ['project', id], queryFn: () => api(`/projects/${id}`) })
  const { data: metrics } = useQuery({ queryKey: ['project-metrics', id], queryFn: () => api(`/projects/${id}/metrics`) })
  const { data: blockers } = useQuery({
    queryKey: ['project-blockers', id],
    queryFn: () => api<{ items: any[] }>('/blockers', { params: { project_id: id, size: 50 } }),
    enabled: tab === 'blockers',
  })

  const addMember = useMutation({
    mutationFn: (body: any) => api(`/projects/${id}/members`, { body }),
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: ['project', id] }) },
    onError: (e: any) => setError(e.message),
  })
  const addMilestone = useMutation({
    mutationFn: (body: any) => api(`/projects/${id}/milestones`, { body }),
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: ['project', id] }) },
    onError: (e: any) => setError(e.message),
  })

  if (isLoading) return <div className="page-loading">…</div>
  if (!p) return <div className="empty-state">پروژه یافت نشد</div>
  const canManage = hasRole('senior_manager', 'pmo') || p.members?.some((m: any) => m.role_in_project === 'manager')

  return (
    <div>
      <PageTitle
        title={`${p.code} — ${p.title}`}
        subtitle={<><StatusChip map={PROJECT_STATUS} value={p.status} /> <span className="muted">واحد راهبر: {p.lead_unit_name ?? '—'}</span></>}
      />

      <div className="stats-grid">
        <div className="stat-card"><div className="stat-label">پیشرفت گزارش‌شده</div><Progress value={p.progress_reported} /></div>
        <div className="stat-card"><div className="stat-label">پیشرفت تأییدشده</div><Progress value={p.progress_approved} /></div>
        <div className="stat-card"><div className="stat-label">وظایف معتبر</div><div className="stat-value">{p.task_count}</div></div>
        <div className="stat-card"><div className="stat-label">موانع باز</div><div className="stat-value">{p.open_blockers}</div></div>
      </div>

      <div className="tabs">
        {[
          ['overview', 'نمای کلی'],
          ['members', 'اعضا'],
          ['milestones', 'نقاط عطف'],
          ['blockers', 'موانع'],
          ['metrics', 'شاخص‌ها'],
        ].map(([k, label]) => (
          <button key={k} className={`tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>

      <ErrorBox message={error} />

      {tab === 'overview' && (
        <Card title="اطلاعات پروژه">
          <div className="info-grid">
            <div className="info-item"><span className="k">مدیر پروژه</span><span className="v">{p.manager_name ?? '—'}</span></div>
            <div className="info-item"><span className="k">دسته</span><span className="v">{p.category ?? '—'}</span></div>
            <div className="info-item"><span className="k">حامی</span><span className="v">{p.sponsor ?? '—'}</span></div>
            <div className="info-item"><span className="k">شروع</span><span className="v">{toJalaliStr(p.start_date)}</span></div>
            <div className="info-item"><span className="k">پایان</span><span className="v">{toJalaliStr(p.end_date)}</span></div>
          </div>
          <p style={{ marginTop: 12 }}>{p.description || <span className="muted">بدون شرح</span>}</p>
          {p.goal && <p className="muted">🎯 هدف: {p.goal}</p>}
          {p.acceptance_criteria && <p className="muted">✅ معیار پذیرش: {p.acceptance_criteria}</p>}
          <div style={{ marginTop: 12 }}>
            <Link className="btn btn-sm" to={`/tasks?project=${id}`}>مشاهده وظایف پروژه ←</Link>
          </div>
        </Card>
      )}

      {tab === 'members' && (
        <Card title="اعضای پروژه">
          <table>
            <thead><tr><th>نام</th><th>نقش در پروژه</th></tr></thead>
            <tbody>
              {(p.members ?? []).map((m: any) => (
                <tr key={m.user_id}><td>{m.full_name}</td><td>{m.role_in_project === 'manager' ? 'مدیر پروژه' : 'عضو'}</td></tr>
              ))}
            </tbody>
          </table>
          {canManage && (
            <form style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}
              onSubmit={(e) => {
                e.preventDefault()
                const fd = new FormData(e.currentTarget as HTMLFormElement)
                addMember.mutate({ user_id: fd.get('user_id'), role_in_project: 'member' })
                ;(e.currentTarget as HTMLFormElement).reset()
              }}>
              <input name="user_id" dir="ltr" placeholder="شناسه کاربر (UUID)" required style={{ minWidth: 260 }} />
              <button className="btn btn-sm btn-primary">افزودن عضو</button>
            </form>
          )}
        </Card>
      )}

      {tab === 'milestones' && (
        <Card title="نقاط عطف">
          <table>
            <thead><tr><th>عنوان</th><th>سررسید</th><th>وضعیت</th></tr></thead>
            <tbody>
              {(p.milestones ?? []).map((m: any) => (
                <tr key={m.id}>
                  <td>{m.title}</td>
                  <td>{toJalaliStr(m.due_date)}</td>
                  <td>{m.is_done ? <Chip label="تحقق یافته" tone="green" /> : <Chip label="در جریان" tone="blue" />}</td>
                </tr>
              ))}
              {(p.milestones ?? []).length === 0 && <tr><td colSpan={3} className="muted" style={{ textAlign: 'center' }}>نقطه عطفی ثبت نشده</td></tr>}
            </tbody>
          </table>
          {canManage && (
            <form style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}
              onSubmit={(e) => {
                e.preventDefault()
                const fd = new FormData(e.currentTarget as HTMLFormElement)
                addMilestone.mutate({ title: fd.get('title'), due_date: fd.get('due_date') || null })
                ;(e.currentTarget as HTMLFormElement).reset()
              }}>
              <input name="title" placeholder="عنوان نقطه عطف" required />
              <input name="due_date" type="date" />
              <button className="btn btn-sm btn-primary">افزودن</button>
            </form>
          )}
        </Card>
      )}

      {tab === 'blockers' && (
        <Card title="موانع پروژه">
          <DataTable
            rows={blockers?.items}
            columns={[
              { key: 'title', label: 'عنوان' },
              { key: 'type', label: 'نوع' },
              { key: 'owner_name', label: 'مسئول پیگیری' },
              { key: 'status', label: 'وضعیت', render: (r: any) => <StatusChip map={BLOCKER_STATUS} value={r.status} /> },
            ]}
          />
        </Card>
      )}

      {tab === 'metrics' && metrics && (
        <Card title="شاخص‌های پروژه (سند ۷)">
          <ul className="kv-list">
            <li><span>پیشرفت گزارش‌شده</span><Progress value={metrics.progress?.reported} /></li>
            <li><span>پیشرفت تأییدشده</span><Progress value={metrics.progress?.approved} /></li>
            <li><span>درصد تعهدات معوق (سال جاری)</span><strong>{metrics.overdue_pct ?? 'قابل محاسبه نیست'}</strong></li>
            <li><span>تکمیل به‌موقع (سررسید جاری)</span><strong>{metrics.on_time_current ?? 'قابل محاسبه نیست'}</strong></li>
            <li><span>تکمیل به‌موقع (سررسید مبنا)</span><strong>{metrics.on_time_base ?? 'قابل محاسبه نیست'}</strong></li>
            <li><span>میانگین تأخیر تا ارسال (روز)</span><strong>{metrics.delays?.submit_delay_avg ?? '—'}</strong></li>
            <li><span>میانگین انتظار بررسی (روز)</span><strong>{metrics.delays?.review_wait_avg ?? '—'}</strong></li>
            <li><span>میانگین تأخیر تا تأیید نهایی (روز)</span><strong>{metrics.delays?.approve_delay_avg ?? '—'}</strong></li>
          </ul>
        </Card>
      )}
    </div>
  )
}
