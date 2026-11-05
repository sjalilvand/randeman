import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, downloadFile } from '../api'
import { Card, DataTable, ErrorBox, Field, Modal, PageTitle, StatusChip } from '../components/ui'
import { CONFIDENTIALITY, DOC_STATUS } from '../constants'
import { toJalaliStr } from '../jalali'

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} بایت`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} کیلوبایت`
  return `${(bytes / 1024 / 1024).toFixed(1)} مگابایت`
}

export default function Documents() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['documents', q],
    queryFn: () => api<{ items: any[]; total: number }>('/documents', { params: { q, size: 50 } }),
  })

  const upload = useMutation({
    mutationFn: async (form: HTMLFormElement) => {
      const fd = new FormData(form)
      return api('/documents', { form: fd })
    },
    onSuccess: () => { setOpen(false); setError(null); qc.invalidateQueries({ queryKey: ['documents'] }) },
    onError: (e: any) => setError(e.message),
  })

  return (
    <div>
      <PageTitle
        title="مستندات"
        subtitle="بارگذاری امن با قرنطینه و اسکن ClamAV — فایل پس از اسکن سالم آماده می‌شود (سند ۵.۶)"
        actions={<button className="btn btn-primary" onClick={() => setOpen(true)}>+ بارگذاری مستند</button>}
      />
      <div className="toolbar">
        <input placeholder="جست‌وجوی عنوان…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card>
        <DataTable
          loading={isLoading}
          rows={data?.items}
          columns={[
            { key: 'title', label: 'عنوان' },
            { key: 'version', label: 'نسخه', render: (r) => `نسخه ${r.version}` },
            { key: 'extension', label: 'نوع', render: (r) => r.extension.toUpperCase() },
            { key: 'size_bytes', label: 'حجم', render: (r) => humanSize(r.size_bytes) },
            { key: 'status', label: 'وضعیت اسکن', render: (r) => <StatusChip map={DOC_STATUS} value={r.status} /> },
            { key: 'confidentiality', label: 'محرمانگی', render: (r) => CONFIDENTIALITY[r.confidentiality] ?? r.confidentiality },
            { key: 'uploader_name', label: 'بارگذارنده' },
            { key: 'created_at', label: 'تاریخ', render: (r) => toJalaliStr(r.created_at, true) },
            {
              key: 'actions', label: 'عملیات',
              render: (r) => (
                <button className="btn btn-sm" disabled={r.status !== 'ready'}
                  onClick={() => downloadFile(`/documents/${r.id}/download`, r.original_name)}>
                  ⬇ دانلود
                </button>
              ),
            },
          ]}
        />
        <p className="muted" style={{ padding: '8px 4px' }}>
          فایل‌های «در قرنطینه» تا اتمام اسکن قابل دانلود نیستند؛ در صورت عدم دسترسی سرویس اسکن، فایل در قرنطینه می‌ماند (AC-16).
        </p>
      </Card>

      <Modal open={open} title="بارگذاری مستند جدید" onClose={() => setOpen(false)}>
        <ErrorBox message={error} />
        <form onSubmit={(e) => { e.preventDefault(); upload.mutate(e.currentTarget as HTMLFormElement) }}>
          <Field label="فایل *" hint="حداکثر ۲۰ مگابایت — PDF، DOCX، XLSX، PPTX، JPG، PNG، TXT">
            <input type="file" name="file" required accept=".pdf,.docx,.xlsx,.pptx,.jpg,.jpeg,.png,.txt" />
          </Field>
          <Field label="عنوان"><input name="title" /></Field>
          <Field label="توضیح"><textarea name="description" /></Field>
          <div className="form-row">
            <Field label="دسته"><input name="category" /></Field>
            <Field label="محرمانگی">
              <select name="confidentiality" defaultValue="internal">
                {Object.entries(CONFIDENTIALITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
          </div>
          <div className="form-row">
            <Field label="پیوند به (نوع رکورد)" hint="اختیاری — برای اتصال به وظیفه/پروژه">
              <select name="entity_type" defaultValue="">
                <option value="">— بدون پیوند —</option>
                <option value="task">وظیفه</option>
                <option value="project">پروژه</option>
                <option value="blocker">مانع</option>
              </select>
            </Field>
            <Field label="شناسه رکورد"><input name="entity_id" dir="ltr" /></Field>
          </div>
          <button className="btn btn-primary" disabled={upload.isPending}>بارگذاری</button>
        </form>
      </Modal>
    </div>
  )
}
