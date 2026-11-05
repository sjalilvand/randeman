import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, Chip, ErrorBox, Modal, PageTitle, StatusChip } from '../components/ui'
import { ITEM_KIND, REPORT_STATUS } from '../constants'
import { toJalaliStr } from '../jalali'

export default function ReviewQueue() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: inbox, isLoading } = useQuery<any[]>({
    queryKey: ['review-inbox'],
    queryFn: () => api('/weekly-reports/inbox'),
  })

  const { data: detail } = useQuery({
    queryKey: ['report-detail', selected],
    queryFn: () => api(`/weekly-reports/${selected}`),
    enabled: !!selected,
  })

  const act = useMutation({
    mutationFn: ({ id, path, body }: { id: string; path: string; body?: any }) =>
      api(`/weekly-reports/${id}${path}`, { method: 'POST', body }),
    onSuccess: () => {
      setError(null)
      qc.invalidateQueries({ queryKey: ['review-inbox'] })
      qc.invalidateQueries({ queryKey: ['report-detail', selected] })
    },
    onError: (e: any) => setError(e.message),
  })

  return (
    <div>
      <PageTitle title="بررسی گزارش‌های هفتگی" subtitle="صف بررسی‌کننده — تأیید گزارش توسط صاحب گزارش ممنوع است (AC-22)" />
      <ErrorBox message={error} />
      <Card>
        <table>
          <thead><tr><th>کارمند</th><th>هفته</th><th>وضعیت</th><th>ارسال</th><th>تأخیر</th><th></th></tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="muted">در حال بارگذاری…</td></tr>}
            {(inbox ?? []).map((r: any) => (
              <tr key={r.id}>
                <td>{r.user_name}</td>
                <td>{toJalaliStr(r.week_start)}</td>
                <td><StatusChip map={REPORT_STATUS} value={r.status} /></td>
                <td>{toJalaliStr(r.submitted_at, true)}</td>
                <td>{r.submitted_late ? <Chip label="با تأخیر" tone="amber" /> : '—'}</td>
                <td><button className="btn btn-sm" onClick={() => setSelected(r.id)}>بررسی</button></td>
              </tr>
            ))}
            {!isLoading && (inbox ?? []).length === 0 && <tr><td colSpan={6} className="muted" style={{ textAlign: 'center' }}>صف بررسی خالی است</td></tr>}
          </tbody>
        </table>
      </Card>

      <Modal open={!!selected} title="جزئیات گزارش هفتگی" onClose={() => setSelected(null)} wide>
        {detail && (
          <>
            <p>
              <strong>{detail.user_name}</strong> — هفته {toJalaliStr(detail.week_start)} <StatusChip map={REPORT_STATUS} value={detail.status} />
            </p>
            {detail.summary && <p>{detail.summary}</p>}
            <table>
              <thead><tr><th>عنوان</th><th>نوع</th><th>ساعت</th></tr></thead>
              <tbody>
                {(detail.items ?? []).map((i: any) => (
                  <tr key={i.id}>
                    <td>{i.title}{i.description && <div className="muted">{i.description}</div>}</td>
                    <td>{ITEM_KIND[i.kind] ?? i.kind ?? '—'}</td>
                    <td>{i.hours ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {detail.blockers && <p className="muted">🚧 موانع: {detail.blockers}</p>}
            {detail.next_plan && <p className="muted">برنامه هفته بعد: {detail.next_plan}</p>}
            {detail.decision_requests && <p className="muted">درخواست تصمیم: {detail.decision_requests}</p>}
            {['submitted', 'in_review'].includes(detail.status) && (
              <form onSubmit={(e) => {
                e.preventDefault()
                const comment = new FormData(e.currentTarget as HTMLFormElement).get('comment')
                act.mutate({ id: detail.id, path: '/approve', body: { comment } })
              }} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                <input name="comment" placeholder="یادداشت تأیید (اختیاری)" style={{ flex: 1, minWidth: 200 }} />
                <button className="btn btn-primary">تأیید گزارش</button>
                <button type="button" className="btn btn-danger" onClick={() => {
                  const comment = (prompt('دلیل درخواست اصلاح:') || '').trim()
                  if (comment) act.mutate({ id: detail.id, path: '/request-correction', body: { comment } })
                }}>درخواست اصلاح</button>
              </form>
            )}
          </>
        )}
      </Modal>
    </div>
  )
}
