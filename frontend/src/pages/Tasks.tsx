import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Card, ErrorBox, Field, Modal, PageTitle, StatusChip } from '../components/ui'
import { PRIORITY, TASK_STATUS } from '../constants'
import { dueInfo, toJalaliStr } from '../jalali'

export default function Tasks() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { hasRole } = useAuth()
  const [view, setView] = useState<'list' | 'board'>('list')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState(params.get('status') ?? '')
  const [overdue, setOverdue] = useState(params.get('overdue') === '1')
  const [projectId, setProjectId] = useState(params.get('project') ?? '')
  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', q, status, overdue, projectId],
    queryFn: () => api<{ items: any[]; total: number }>('/tasks', {
      params: { q, status_filter: status || undefined, overdue_only: overdue || undefined, project_id: projectId || undefined, size: 100 },
    }),
  })
  const { data: projects } = useQuery({
    queryKey: ['projects-lite'],
    queryFn: () => api<{ items: any[] }>('/projects', { params: { size: 100 } }),
  })
  const { data: users } = useQuery({
    queryKey: ['users-lite'],
    queryFn: () => api<{ items: any[] }>('/users', { params: { active: true, size: 200 } }),
    enabled: hasRole('unit_manager', 'project_manager', 'senior_manager', 'pmo'),
  })

  const create = useMutation({
    mutationFn: (body: any) => api('/tasks', { body }),
    onSuccess: () => {
      setCreateOpen(false)
      setCreateError(null)
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (e: any) => setCreateError(e.message),
  })

  const rows = data?.items ?? []
  const columns = ['draft', 'assigned', 'in_progress', 'ready_for_review', 'needs_correction', 'blocked', 'completed']

  return (
    <div>
      <PageTitle
        title="وظایف"
        subtitle="تخصیص، سررسید، وابستگی و گردش بررسی (سند ۵.۳)"
        actions={hasRole('unit_manager', 'project_manager', 'senior_manager', 'pmo') && (
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>+ وظیفه جدید</button>
        )}
      />
      <div className="toolbar">
        <input placeholder="جست‌وجو (کد یا عنوان)…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">همه وضعیت‌ها</option>
          {Object.entries(TASK_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          <option value="">همه پروژه‌ها</option>
          {(projects?.items ?? []).map((p: any) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <label style={{ fontSize: '0.84rem', display: 'flex', gap: 4, alignItems: 'center' }}>
          <input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} style={{ width: 'auto' }} />
          فقط معوق‌ها
        </label>
        <div className="spacer" />
        <button className={`btn btn-sm ${view === 'list' ? 'btn-primary' : ''}`} onClick={() => setView('list')}>فهرست</button>
        <button className={`btn btn-sm ${view === 'board' ? 'btn-primary' : ''}`} onClick={() => setView('board')}>تابلو</button>
      </div>

      {view === 'list' ? (
        <Card>
          <table>
            <thead><tr><th>کد</th><th>عنوان</th><th>مسئول</th><th>وضعیت</th><th>اولویت</th><th>پیشرفت</th><th>سررسید</th></tr></thead>
            <tbody>
              {isLoading && <tr><td colSpan={7} className="muted">در حال بارگذاری…</td></tr>}
              {rows.map((t) => {
                const due = dueInfo(t.current_due_date)
                return (
                  <tr key={t.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/tasks/${t.id}`)}>
                    <td>{t.code}</td>
                    <td>{t.title}</td>
                    <td>{t.assignee_name}</td>
                    <td><StatusChip map={TASK_STATUS} value={t.status} /></td>
                    <td><StatusChip map={PRIORITY} value={t.priority} /></td>
                    <td>{t.progress}٪</td>
                    <td>{due.late ? <span className="chip chip-red">{due.text}</span> : due.soon ? <span className="chip chip-amber">{due.text}</span> : toJalaliStr(t.current_due_date)}</td>
                  </tr>
                )
              })}
              {!isLoading && rows.length === 0 && <tr><td colSpan={7} className="muted" style={{ textAlign: 'center' }}>وظیفه‌ای یافت نشد</td></tr>}
            </tbody>
          </table>
          <p className="muted" style={{ padding: '8px 4px' }}>مجموع: {data?.total ?? 0} — هر عدد داشبورد به همین فهرست متصل است (سند ۶)</p>
        </Card>
      ) : (
        <div className="board">
          {columns.map((st) => {
            const items = rows.filter((t) => t.status === st)
            return (
              <div className="board-col" key={st}>
                <div className="board-col-head">
                  <StatusChip map={TASK_STATUS} value={st} />
                  <span>{items.length}</span>
                </div>
                {items.map((t) => {
                  const due = dueInfo(t.current_due_date)
                  return (
                    <div className="board-card" key={t.id} onClick={() => nav(`/tasks/${t.id}`)}>
                      <strong>{t.title}</strong>
                      <div className="board-meta">
                        <span>{t.code}</span>
                        <span>{t.assignee_name}</span>
                      </div>
                      <div className="board-meta">
                        {due.late ? <span className="chip chip-red">{due.text}</span> : due.soon ? <span className="chip chip-amber">{due.text}</span> : <span>{toJalaliStr(t.current_due_date)}</span>}
                        <span>{t.progress}٪</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>
      )}
      <Modal open={createOpen} title="ایجاد وظیفه جدید" onClose={() => setCreateOpen(false)} wide>
        <ErrorBox message={createError} />
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const fd = new FormData(e.currentTarget as HTMLFormElement)
            create.mutate({
              title: fd.get('title'),
              description: fd.get('description') || null,
              assignee_id: fd.get('assignee_id'),
              project_id: fd.get('project_id') || null,
              base_due_date: fd.get('base_due_date') || null,
              current_due_date: fd.get('base_due_date') || null,
              estimated_hours: fd.get('estimated_hours') ? Number(fd.get('estimated_hours')) : null,
              weight: Number(fd.get('weight') || 1),
              priority: fd.get('priority'),
              acceptance_criteria: fd.get('acceptance_criteria') || null,
            })
          }}
        >
          <Field label="عنوان *"><input name="title" required minLength={3} /></Field>
          <Field label="شرح"><textarea name="description" /></Field>
          <div className="form-row">
            <Field label="مسئول اصلی *">
              <select name="assignee_id" required>
                <option value="">— انتخاب کنید —</option>
                {(users?.items ?? []).map((u: any) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
              </select>
            </Field>
            <Field label="پروژه">
              <select name="project_id">
                <option value="">— خارج از پروژه —</option>
                {(projects?.items ?? []).map((p: any) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </Field>
          </div>
          <div className="form-row-3">
            <Field label="سررسید مبنا"><input name="base_due_date" type="date" /></Field>
            <Field label="ساعت تخمینی"><input name="estimated_hours" type="number" min="0" step="0.5" /></Field>
            <Field label="وزن (سهم در پروژه)" hint="مثلاً ۱ تا ۵"><input name="weight" type="number" min="0.1" step="0.1" defaultValue={1} /></Field>
          </div>
          <div className="form-row">
            <Field label="اولویت">
              <select name="priority" defaultValue="medium">
                {Object.entries(PRIORITY).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </Field>
            <Field label="معیار پذیرش"><input name="acceptance_criteria" /></Field>
          </div>
          <button className="btn btn-primary" disabled={create.isPending}>ایجاد و تخصیص</button>
        </form>
      </Modal>
    </div>
  )
}
