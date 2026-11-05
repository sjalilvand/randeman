import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, DataTable, ErrorBox, Field, Modal, PageTitle, StatusChip } from '../components/ui'
import { BLOCKER_STATUS, BLOCKER_TYPE } from '../constants'
import { toJalaliStr } from '../jalali'

export default function Blockers() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('open')
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['blockers', statusFilter],
    queryFn: () => api<{ items: any[]; total: number }>('/blockers', { params: { status_filter: statusFilter || undefined, size: 50 } }),
  })
  const { data: projects } = useQuery({
    queryKey: ['projects-lite'],
    queryFn: () => api<{ items: any[] }>('/projects', { params: { size: 100 } }),
  })
  const { data: risks } = useQuery<any[]>({ queryKey: ['risks'], queryFn: () => api('/blockers/risks') })

  const create = useMutation({
    mutationFn: (body: any) => api('/blockers', { body }),
    onSuccess: () => { setOpen(false); setError(null); qc.invalidateQueries({ queryKey: ['blockers'] }) },
    onError: (e: any) => setError(e.message),
  })
  const resolve = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => api(`/blockers/${id}/resolve`, { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['blockers'] }),
    onError: (e: any) => setError(e.message),
  })

  return (
    <div>
      <PageTitle
        title="موانع، ریسک‌ها و درخواست تصمیم"
        subtitle="ثبت مانع سررسید را خودکار تغییر نمی‌دهد؛ تصمیم لازم با مهلت پاسخ پیگیری می‌شود (سند ۸)"
        actions={<button className="btn btn-primary" onClick={() => setOpen(true)}>+ ثبت مانع</button>}
      />
      <ErrorBox message={error} />
      <div className="toolbar">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">همه وضعیت‌ها</option>
          {Object.entries(BLOCKER_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <Card title="موانع">
        <DataTable
          loading={isLoading}
          rows={data?.items}
          columns={[
            { key: 'title', label: 'عنوان' },
            { key: 'type', label: 'نوع', render: (r) => BLOCKER_TYPE[r.type] ?? r.type },
            { key: 'project_title', label: 'پروژه' },
            { key: 'owner_name', label: 'مسئول پیگیری' },
            { key: 'decision_needed', label: 'درخواست تصمیم', render: (r) => r.decision_needed ? '⏳ نیازمند تصمیم' : '—' },
            { key: 'response_deadline', label: 'مهلت پاسخ', render: (r) => toJalaliStr(r.response_deadline) },
            { key: 'status', label: 'وضعیت', render: (r) => <StatusChip map={BLOCKER_STATUS} value={r.status} /> },
            {
              key: 'actions', label: '',
              render: (r) => r.status === 'open' ? (
                <button className="btn btn-sm" onClick={() => {
                  const note = (prompt('توضیح رفع مانع:') || '').trim()
                  if (note !== null) resolve.mutate({ id: r.id, body: { resolution_note: note } })
                }}>رفع شد</button>
              ) : null,
            },
          ]}
        />
      </Card>

      <Card title="ریسک‌های پروژه‌ای">
        <DataTable
          rows={risks}
          columns={[
            { key: 'title', label: 'عنوان' },
            { key: 'probability', label: 'احتمال', render: (r: any) => ({ low: 'کم', medium: 'متوسط', high: 'زیاد' } as Record<string, string>)[r.probability] ?? r.probability },
            { key: 'impact', label: 'اثر', render: (r: any) => ({ low: 'کم', medium: 'متوسط', high: 'زیاد' } as Record<string, string>)[r.impact] ?? r.impact },
            { key: 'owner', label: 'مالک' },
            { key: 'mitigation', label: 'اقدام پیشگیرانه' },
          ]}
        />
      </Card>

      <Modal open={open} title="ثبت مانع جدید" onClose={() => setOpen(false)} wide>
        <ErrorBox message={error} />
        <form onSubmit={(e) => {
          e.preventDefault()
          const fd = new FormData(e.currentTarget as HTMLFormElement)
          create.mutate({
            title: fd.get('title'),
            description: fd.get('description') || null,
            project_id: fd.get('project_id') || null,
            type: fd.get('type'),
            impact: fd.get('impact') || null,
            owner_id: fd.get('owner_id') || null,
            decision_needed: fd.get('decision_needed') || null,
            response_deadline: fd.get('response_deadline') || null,
          })
        }}>
          <Field label="عنوان *"><input name="title" required minLength={3} /></Field>
          <Field label="شرح"><textarea name="description" /></Field>
          <div className="form-row">
            <Field label="نوع مانع">
              <select name="type" defaultValue="other">
                {Object.entries(BLOCKER_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="پروژه مرتبط">
              <select name="project_id" defaultValue="">
                <option value="">— بدون پروژه —</option>
                {(projects?.items ?? []).map((p: any) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </Field>
          </div>
          <div className="form-row">
            <Field label="اثر"><input name="impact" /></Field>
            <Field label="شناسه مسئول پیگیری (UUID)"><input name="owner_id" dir="ltr" /></Field>
          </div>
          <Field label="تصمیم لازم از مدیریت" hint="این مانع در داشبورد «در انتظار تصمیم» نمایش داده می‌شود"><textarea name="decision_needed" /></Field>
          <Field label="مهلت پاسخ"><input name="response_deadline" type="date" /></Field>
          <button className="btn btn-primary" disabled={create.isPending}>ثبت مانع</button>
        </form>
      </Modal>
    </div>
  )
}
