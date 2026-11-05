import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Card, Chip, ErrorBox, Field, Modal, PageTitle, Progress, StatusChip } from '../components/ui'
import { CHANGE_REQ_STATUS, PRIORITY, TASK_STATUS } from '../constants'
import { dueInfo, toJalaliStr } from '../jalali'

export default function TaskDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { user } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState<string | null>(null)

  const { data: t, isLoading } = useQuery({ queryKey: ['task', id], queryFn: () => api(`/tasks/${id}`) })

  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: any }) => api(`/tasks/${id}${path}`, { method: 'POST', body }),
    onSuccess: () => { setError(null); setAction(null); qc.invalidateQueries({ queryKey: ['task', id] }); qc.invalidateQueries({ queryKey: ['tasks'] }) },
    onError: (e: any) => setError(e.message),
  })

  if (isLoading) return <div className="page-loading">…</div>
  if (!t) return <div className="empty-state">وظیفه یافت نشد یا دسترسی ندارید</div>

  const isAssignee = user?.id === t.assignee_id
  const due = dueInfo(t.current_due_date)
  const run = (path: string, body?: any) => act.mutate({ path, body })

  const actionButtons = (
    <div className="page-actions">
      {t.status === 'assigned' && isAssignee && <button className="btn btn-primary" onClick={() => run('/start')}>▶ شروع انجام</button>}
      {t.status === 'in_progress' && isAssignee && <button className="btn btn-primary" onClick={() => setAction('submit')}>ارسال برای بررسی</button>}
      {t.status === 'in_progress' && isAssignee && <button className="btn btn-danger" onClick={() => setAction('block')}>⛔ ثبت مانع و توقف</button>}
      {t.status === 'blocked' && isAssignee && <button className="btn" onClick={() => run('/unblock', {})}>رفع مانع و ادامه</button>}
      {t.status === 'ready_for_review' && (
        <>
          <button className="btn btn-primary" onClick={() => setAction('approve')}>✔ تأیید خروجی</button>
          <button className="btn btn-danger" onClick={() => setAction('correction')}>درخواست اصلاح</button>
        </>
      )}
      {t.status === 'needs_correction' && isAssignee && <button className="btn btn-primary" onClick={() => run('/start')}>شروع اصلاح</button>}
      {isAssignee && ['assigned', 'in_progress', 'needs_correction'].includes(t.status) && (
        <button className="btn" onClick={() => setAction('due')}>درخواست تغییر سررسید</button>
      )}
      {['draft', 'assigned'].includes(t.status) && <button className="btn" onClick={() => setAction('cancel')}>لغو وظیفه</button>}
      {t.status === 'completed' && <button className="btn" onClick={() => setAction('reopen')}>بازگشایی</button>}
    </div>
  )

  return (
    <div>
      <PageTitle
        title={`${t.code} — ${t.title}`}
        subtitle={<><StatusChip map={TASK_STATUS} value={t.status} /> <StatusChip map={PRIORITY} value={t.priority} /> {due.late && <Chip label={due.text} tone="red" />}</>}
        actions={actionButtons}
      />
      <ErrorBox message={error} />

      <div className="grid-2">
        <div>
          <Card title="اطلاعات وظیفه">
            <div className="info-grid">
              <div className="info-item"><span className="k">مسئول اصلی</span><span className="v">{t.assignee_name}</span></div>
              <div className="info-item"><span className="k">تأییدکننده</span><span className="v">{t.approver_name ?? 'تعیین نشده'}</span></div>
              <div className="info-item"><span className="k">پروژه</span><span className="v">{t.project_title ? <Link to={`/projects/${t.project_id}`}>{t.project_title}</Link> : 'خارج از پروژه'}</span></div>
              <div className="info-item"><span className="k">واحد</span><span className="v">{t.unit_name ?? '—'}</span></div>
              <div className="info-item"><span className="k">سررسید مبنا</span><span className="v">{toJalaliStr(t.base_due_date)}</span></div>
              <div className="info-item"><span className="k">سررسید جاری</span><span className="v">{toJalaliStr(t.current_due_date)}</span></div>
              <div className="info-item"><span className="k">ساعت تخمینی</span><span className="v">{t.estimated_hours ?? '—'}</span></div>
              <div className="info-item"><span className="k">وزن</span><span className="v">{t.weight}</span></div>
            </div>
            {t.description && <p style={{ marginTop: 12 }}>{t.description}</p>}
            {t.acceptance_criteria && <p className="muted">✅ معیار پذیرش: {t.acceptance_criteria}</p>}
            {t.delivery_note && <p className="muted">📦 خروجی ثبت‌شده: {t.delivery_note}</p>}
            {t.blocked_reason && <p><Chip label="مانع" tone="darkred" /> {t.blocked_reason}</p>}
            <div style={{ marginTop: 12 }}><span className="k muted">پیشرفت:</span> <Progress value={t.progress} /></div>
          </Card>

          <Card title="تاریخچه وضعیت">
            <ul className="timeline">
              {(t.history ?? []).map((h: any, i: number) => (
                <li key={i}>
                  <strong>{TASK_STATUS[h.to]?.label ?? h.to}</strong>
                  {h.from && <> (از: {TASK_STATUS[h.from]?.label ?? h.from})</>}
                  {' — '}{h.actor} — <span className="muted">{toJalaliStr(h.at, true)}</span>
                  {h.reason && <div className="muted">دلیل: {h.reason}</div>}
                </li>
              ))}
              {(t.history ?? []).length === 0 && <li className="muted">تاریخچه‌ای ثبت نشده</li>}
            </ul>
          </Card>

          <Card title="درخواست‌های تغییر سررسید">
            <table>
              <thead><tr><th>از</th><th>به</th><th>دلیل</th><th>وضعیت</th></tr></thead>
              <tbody>
                {(t.change_requests ?? []).map((cr: any) => (
                  <tr key={cr.id}>
                    <td>{toJalaliStr(cr.old_value)}</td>
                    <td>{toJalaliStr(cr.new_value)}</td>
                    <td>{cr.reason ?? '—'}</td>
                    <td>
                      <StatusChip map={CHANGE_REQ_STATUS} value={cr.status} />
                      {cr.status === 'pending' && (
                        <span style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                          <button className="btn btn-sm btn-primary" onClick={() => run(`/due-change-requests/${cr.id}/decide`, { approve: true })}>موافقت</button>
                          <button className="btn btn-sm btn-danger" onClick={() => run(`/due-change-requests/${cr.id}/decide`, { approve: false, comment: 'رد درخواست' })}>رد</button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {(t.change_requests ?? []).length === 0 && <tr><td colSpan={4} className="muted" style={{ textAlign: 'center' }}>درخواستی نیست</td></tr>}
              </tbody>
            </table>
          </Card>
        </div>

        <div>
          <Card title="ثبت پیشرفت">
            <form onSubmit={(e) => {
              e.preventDefault()
              const v = Number(new FormData(e.currentTarget as HTMLFormElement).get('progress'))
              run('/progress', { progress: v })
            }}>
              <Field label="درصد پیشرفت"><input name="progress" type="number" min={0} max={100} defaultValue={t.progress} /></Field>
              <button className="btn btn-sm">ذخیره پیشرفت</button>
            </form>
          </Card>

          <Card title="همکاران">
            <ul className="kv-list">
              {(t.collaborators ?? []).map((c: any) => <li key={c.user_id}><span>{c.full_name}</span></li>)}
              {(t.collaborators ?? []).length === 0 && <li className="muted">همکاری ثبت نشده</li>}
            </ul>
          </Card>

          <Card title="وابستگی‌ها">
            <ul className="kv-list">
              {(t.dependencies ?? []).map((d: any) => (
                <li key={d.task_id}>
                  <span>{d.code} — {d.title}</span>
                  <StatusChip map={TASK_STATUS} value={d.status} />
                </li>
              ))}
              {(t.dependencies ?? []).length === 0 && <li className="muted">وابستگی ثبت نشده</li>}
            </ul>
          </Card>

          <Card title="مستندات پیوسته">
            <ul className="kv-list">
              {(t.documents ?? []).map((d: any) => (
                <li key={d.id}>
                  <span>{d.title} <Chip label={`نسخه ${d.version}`} tone="gray" /></span>
                  <StatusChip map={{ quarantined: { label: 'قرنطینه', tone: 'amber' }, ready: { label: 'آماده', tone: 'green' }, rejected: { label: 'رد شده', tone: 'red' } }} value={d.status} />
                </li>
              ))}
              {(t.documents ?? []).length === 0 && <li className="muted">مستندی پیوست نشده — از بخش مستندات بارگذاری کنید</li>}
            </ul>
          </Card>
        </div>
      </div>

      {/* مودال‌های عملیات */}
      <Modal open={action === 'submit'} title="ارسال خروجی برای بررسی" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); run('/submit-for-review', { delivery_note: new FormData(e.currentTarget as HTMLFormElement).get('note') }) }}>
          <Field label="شرح خروجی و شواهد *" hint="ثبت خروجی و شواهد لازم برای ورود به گردش بررسی الزامی است"><textarea name="note" required minLength={5} /></Field>
          <button className="btn btn-primary">ارسال</button>
        </form>
      </Modal>
      <Modal open={action === 'approve'} title="تأیید خروجی" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); run('/approve', { comment: new FormData(e.currentTarget as HTMLFormElement).get('comment') || null }) }}>
          <Field label="یادداشت تأیید (اختیاری)"><textarea name="comment" /></Field>
          <button className="btn btn-primary">تأیید نهایی</button>
        </form>
      </Modal>
      <Modal open={action === 'correction'} title="درخواست اصلاح" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); run('/request-correction', { reason: new FormData(e.currentTarget as HTMLFormElement).get('reason') }) }}>
          <Field label="دلیل اصلاح *"><textarea name="reason" required /></Field>
          <button className="btn btn-danger">ثبت درخواست اصلاح</button>
        </form>
      </Modal>
      <Modal open={action === 'block'} title="ثبت مانع و توقف وظیفه" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); run('/block', { reason: new FormData(e.currentTarget as HTMLFormElement).get('reason') }) }}>
          <Field label="شرح مانع *" hint="مانع در بخش موانع نیز ثبت می‌شود"><textarea name="reason" required /></Field>
          <button className="btn btn-danger">توقف وظیفه</button>
        </form>
      </Modal>
      <Modal open={action === 'due'} title="درخواست تغییر سررسید" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget as HTMLFormElement); run('/request-due-date-change', { new_due_date: fd.get('due'), reason: fd.get('reason') }) }}>
          <Field label="سررسید جدید *" hint="سررسید مبنا حفظ می‌شود؛ فقط سررسید جاری با تصویب تغییر می‌کند"><input name="due" type="date" required /></Field>
          <Field label="دلیل *"><textarea name="reason" required /></Field>
          <button className="btn btn-primary">ثبت درخواست</button>
        </form>
      </Modal>
      <Modal open={action === 'cancel'} title="لغو وظیفه" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); run('/cancel', { reason: new FormData(e.currentTarget as HTMLFormElement).get('reason') }) }}>
          <Field label="دلیل لغو *"><textarea name="reason" required /></Field>
          <button className="btn btn-danger">لغو وظیفه</button>
        </form>
      </Modal>
      <Modal open={action === 'reopen'} title="بازگشایی وظیفه" onClose={() => setAction(null)}>
        <form onSubmit={(e) => { e.preventDefault(); run('/reopen', { reason: new FormData(e.currentTarget as HTMLFormElement).get('reason') }) }}>
          <Field label="دلیل بازگشایی *" hint="بازگشایی عملیات ثبت‌شده است؛ عامل و دلیل در ممیزی ثبت می‌شود"><textarea name="reason" required minLength={5} /></Field>
          <button className="btn btn-primary">بازگشایی</button>
        </form>
      </Modal>
    </div>
  )
}
