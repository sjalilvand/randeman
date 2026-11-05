import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, DataTable, ErrorBox, Field, Modal, OkBox, PageTitle } from '../components/ui'
import { ACTIVITY_TYPE } from '../constants'
import { toJalaliStr, todayIso } from '../jalali'

export default function Activities() {
  const qc = useQueryClient()
  const [filters, setFilters] = useState<{ from?: string; to?: string; type?: string }>({})
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['activities', filters],
    queryFn: () => api<{ items: any[]; total: number }>('/activities', {
      params: { date_from: filters.from, date_to: filters.to, type_filter: filters.type, size: 50 },
    }),
  })

  const create = useMutation({
    mutationFn: (body: any) => api('/activities', { body }),
    onSuccess: () => { setOpen(false); setError(null); setOk('فعالیت ثبت شد'); qc.invalidateQueries({ queryKey: ['activities'] }) },
    onError: (e: any) => setError(e.message),
  })

  return (
    <div>
      <PageTitle
        title="فعالیت‌ها"
        subtitle="ثبت اقدامات واقعی — فعالیت از وظیفه مستقل است (سند ۵.۴)"
        actions={<button className="btn btn-primary" onClick={() => setOpen(true)}>+ ثبت فعالیت</button>}
      />
      <OkBox message={ok} />
      <div className="toolbar">
        <input type="date" value={filters.from ?? ''} onChange={(e) => setFilters((f) => ({ ...f, from: e.target.value }))} />
        <input type="date" value={filters.to ?? ''} onChange={(e) => setFilters((f) => ({ ...f, to: e.target.value }))} />
        <select value={filters.type ?? ''} onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value }))}>
          <option value="">همه انواع</option>
          {Object.entries(ACTIVITY_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <a className="btn btn-sm" href="/api/v1/reports/activities.xlsx">⬇ خروجی Excel</a>
      </div>
      <Card>
        <DataTable
          loading={isLoading}
          rows={data?.items}
          columns={[
            { key: 'activity_date', label: 'تاریخ', render: (r) => toJalaliStr(r.activity_date) },
            { key: 'title', label: 'عنوان' },
            { key: 'type', label: 'نوع', render: (r) => ACTIVITY_TYPE[r.type] ?? r.type },
            { key: 'duration_minutes', label: 'مدت (دقیقه)', render: (r) => r.duration_minutes ?? '—' },
            { key: 'task_code', label: 'وظیفه مرتبط', render: (r) => r.task_code ? <a href={`/tasks/${r.task_id}`}>{r.task_code}</a> : '—' },
            { key: 'blocker_note', label: 'مانع', render: (r) => r.blocker_note ?? '—' },
          ]}
        />
      </Card>

      <Modal open={open} title="ثبت فعالیت جدید" onClose={() => setOpen(false)} wide>
        <ErrorBox message={error} />
        <form onSubmit={(e) => {
          e.preventDefault()
          const fd = new FormData(e.currentTarget as HTMLFormElement)
          create.mutate({
            activity_date: fd.get('activity_date'),
            title: fd.get('title'),
            description: fd.get('description') || null,
            result: fd.get('result') || null,
            task_id: fd.get('task_id') || null,
            duration_minutes: fd.get('duration_minutes') ? Number(fd.get('duration_minutes')) : null,
            type: fd.get('type'),
            blocker_note: fd.get('blocker_note') || null,
          })
        }}>
          <div className="form-row">
            <Field label="تاریخ انجام *"><input name="activity_date" type="date" defaultValue={todayIso()} required /></Field>
            <Field label="نوع *">
              <select name="type" defaultValue="execution">
                {Object.entries(ACTIVITY_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
          </div>
          <Field label="عنوان *"><input name="title" required minLength={3} /></Field>
          <Field label="شرح"><textarea name="description" /></Field>
          <Field label="نتیجه"><textarea name="result" /></Field>
          <div className="form-row">
            <Field label="وظیفه مرتبط (اختیاری)" hint="شناسه وظیفه را از صفحه وظیفه کپی کنید">
              <input name="task_id" dir="ltr" />
            </Field>
            <Field label="مدت (دقیقه)" hint="زمان غیرعادی هشدار دارد، نه قضاوت خودکار">
              <input name="duration_minutes" type="number" min={1} max={10080} />
            </Field>
          </div>
          <Field label="مانع (در صورت وجود)"><textarea name="blocker_note" /></Field>
          <button className="btn btn-primary" disabled={create.isPending}>ثبت</button>
        </form>
      </Modal>
    </div>
  )
}
