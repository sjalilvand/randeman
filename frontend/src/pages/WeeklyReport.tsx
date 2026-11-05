import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, Chip, ErrorBox, Field, OkBox, PageTitle, StatusChip } from '../components/ui'
import { ITEM_KIND, REPORT_STATUS } from '../constants'
import { currentWeekStart, shiftWeek, toJalaliStr } from '../jalali'

interface Report {
  id: string
  status: string
  version: number
  summary: string | null
  blockers: string | null
  next_plan: string | null
  decision_requests: string | null
  approver_name: string | null
  submitted_at: string | null
  approved_at: string | null
  submitted_late: boolean
  items: { id: string; title: string; description: string | null; hours: number | null; kind: string | null; task_id: string | null }[]
  versions: { version: number; created_at: string; note: string | null }[]
  review_actions: { action: string; comment: string | null; at: string; actor: string }[]
}

export default function WeeklyReport() {
  const qc = useQueryClient()
  const [week, setWeek] = useState(currentWeekStart())
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const { data: report, isLoading } = useQuery<Report | null>({
    queryKey: ['my-report', week],
    queryFn: () => api('/weekly-reports/my', { params: { week_start: week } }),
  })

  const generate = useMutation({
    mutationFn: () => api('/weekly-reports/my/generate', { body: { week_start: week } }),
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: ['my-report', week] }) },
    onError: (e: any) => setError(e.message),
  })

  const save = useMutation({
    mutationFn: (body: any) => api('/weekly-reports/my', { method: 'PUT', body }),
    onSuccess: () => { setError(null); setOk('پیش‌نویس ذخیره شد'); qc.invalidateQueries({ queryKey: ['my-report', week] }) },
    onError: (e: any) => setError(e.message),
  })

  const submit = useMutation({
    mutationFn: () => api('/weekly-reports/my/submit', { body: { week_start: week } }),
    onSuccess: () => { setError(null); setOk('گزارش ارسال شد و برای بررسی درآمد'); qc.invalidateQueries({ queryKey: ['my-report', week] }) },
    onError: (e: any) => setError(e.message),
  })

  const editable = !report || report.status === 'draft' || report.status === 'needs_correction'
  const items = report?.items ?? []

  const addItem = () => {
    save.mutate({
      week_start: week,
      summary: report?.summary ?? '',
      blockers: report?.blockers ?? '',
      next_plan: report?.next_plan ?? '',
      decision_requests: report?.decision_requests ?? '',
      items: [...items.map((i) => ({ title: i.title, description: i.description, hours: i.hours, kind: i.kind ?? 'done', task_id: i.task_id })),
              { title: '', description: '', hours: null, kind: 'done', task_id: null }],
    })
  }

  const updateItem = (idx: number, patch: any) => {
    const next = items.map((i, j) => {
      if (j !== idx) return { title: i.title, description: i.description, hours: i.hours, kind: i.kind ?? 'done', task_id: i.task_id }
      return { title: i.title, description: i.description, hours: i.hours, kind: i.kind ?? 'done', task_id: i.task_id, ...patch }
    })
    save.mutate({ week_start: week, summary: report?.summary, blockers: report?.blockers, next_plan: report?.next_plan, decision_requests: report?.decision_requests, items: next })
  }

  return (
    <div>
      <PageTitle
        title="گزارش هفتگی"
        subtitle={`هفته ${toJalaliStr(week)} — هفته کاری شنبه تا جمعه (سند ۵.۵)`}
        actions={
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-sm" onClick={() => setWeek(shiftWeek(week, -1))}>→ هفته قبل</button>
            <button className="btn btn-sm" onClick={() => setWeek(currentWeekStart())}>هفته جاری</button>
            <button className="btn btn-sm" onClick={() => setWeek(shiftWeek(week, 1))}>هفته بعد ←</button>
          </div>
        }
      />
      <ErrorBox message={error} />
      <OkBox message={ok} />

      {report && (
        <Card>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <StatusChip map={REPORT_STATUS} value={report.status} />
            <Chip label={`نسخه ${report.version}`} tone="gray" />
            {report.submitted_late && <Chip label="ارسال با تأخیر" tone="amber" />}
            {report.approver_name && <span className="muted">بررسی‌کننده: {report.approver_name}</span>}
            {report.submitted_at && <span className="muted">ارسال: {toJalaliStr(report.submitted_at, true)}</span>}
            {report.approved_at && <span className="muted">تأیید: {toJalaliStr(report.approved_at, true)}</span>}
          </div>
          {(report.versions ?? []).length > 0 && (
            <p className="muted" style={{ marginTop: 8 }}>
              نسخه‌ها: {report.versions.map((v) => `${v.version}`).join(' ← ')} — هر ارسال/تأیید اسنپ‌شات تغییرناپذیر ایجاد می‌کند
            </p>
          )}
          {(report.review_actions ?? []).length > 0 && (
            <ul className="kv-list" style={{ marginTop: 8 }}>
              {report.review_actions.map((a, i) => (
                <li key={i}>
                  <span>{a.actor} — {a.action === 'approve' ? 'تأیید' : a.action === 'request_correction' ? 'درخواست اصلاح' : 'یادداشت'}</span>
                  <span className="muted">{a.comment ?? ''} · {toJalaliStr(a.at, true)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {isLoading ? <div className="page-loading">…</div> : !report ? (
        <Card>
          <p>برای این هفته گزارشی ساخته نشده است.</p>
          <button className="btn btn-primary" onClick={() => generate.mutate()} disabled={generate.isPending}>
            ایجاد پیش‌نویس خودکار از فعالیت‌ها و وظایف
          </button>
        </Card>
      ) : (
        <Card title={editable ? 'ویرایش گزارش' : 'گزارش (قفل — قابل ویرایش نیست)'}>
          <form onSubmit={(e) => {
            e.preventDefault()
            if (!editable) return
            const form = e.currentTarget as HTMLFormElement
            const fd = new FormData(form)
            const rows: any[] = []
            items.forEach((_, idx) => {
              rows.push({
                title: fd.get(`title-${idx}`),
                description: fd.get(`desc-${idx}`) || null,
                hours: fd.get(`hours-${idx}`) ? Number(fd.get(`hours-${idx}`)) : null,
                kind: fd.get(`kind-${idx}`),
                task_id: null,
              })
            })
            save.mutate({
              week_start: week,
              summary: fd.get('summary'),
              blockers: fd.get('blockers'),
              next_plan: fd.get('next_plan'),
              decision_requests: fd.get('decision_requests'),
              items: rows,
            })
          }}>
            <fieldset disabled={!editable} style={{ border: 'none', padding: 0, margin: 0 }}>
              <Field label="خلاصه اقدامات"><textarea name="summary" defaultValue={report.summary ?? ''} /></Field>

              <h3 style={{ margin: '12px 0 8px' }}>اقلام گزارش</h3>
              {items.map((it, idx) => (
                <div className="report-item-row" key={it.id ?? idx}>
                  <input name={`title-${idx}`} defaultValue={it.title} placeholder="عنوان قلم" required={!!it.title || undefined} />
                  <select name={`kind-${idx}`} defaultValue={it.kind ?? 'done'}>
                    {Object.entries(ITEM_KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <input name={`hours-${idx}`} type="number" step="0.5" min="0" defaultValue={it.hours ?? ''} placeholder="ساعت" style={{ width: 90 }} />
                  <button type="button" className="btn btn-sm btn-danger" onClick={() => updateItem(idx, { _remove: true })}>✕</button>
                </div>
              ))}
              {editable && <button type="button" className="btn btn-sm" onClick={addItem}>+ افزودن قلم</button>}

              <Field label="موانع"><textarea name="blockers" defaultValue={report.blockers ?? ''} /></Field>
              <Field label="برنامه هفته بعد"><textarea name="next_plan" defaultValue={report.next_plan ?? ''} /></Field>
              <Field label="درخواست تصمیم از مدیریت"><textarea name="decision_requests" defaultValue={report.decision_requests ?? ''} /></Field>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn" disabled={save.isPending}>ذخیره پیش‌نویس</button>
                {editable && report.status === 'draft' && (
                  <button type="button" className="btn btn-primary" onClick={() => { if (confirm('گزارش پس از ارسال قابل ویرایش مستقیم نیست. ارسال شود؟')) submit.mutate() }}>
                    ارسال برای بررسی
                  </button>
                )}
              </div>
            </fieldset>
          </form>
        </Card>
      )}
    </div>
  )
}
