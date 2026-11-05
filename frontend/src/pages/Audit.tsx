import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Card, DataTable, PageTitle } from '../components/ui'
import { toJalaliStr } from '../jalali'

export default function Audit() {
  const [action, setAction] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['audit', action],
    queryFn: () => api<{ items: any[]; total: number }>('/audit-events', { params: { action: action || undefined, size: 100 } }),
  })
  return (
    <div>
      <PageTitle title="ممیزی" subtitle="تاریخچه رویدادهای حساس در محدوده مجاز (سند ۴.۳ و ۱۳.۲)" />
      <div className="toolbar">
        <select value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">همه رویدادها</option>
          {['login', 'login_failed', 'user_created', 'user_updated', 'user_deactivated', 'task_created', 'task_approved',
            'task_reopened', 'task_blocked', 'weekly_report_submitted', 'weekly_report_approved', 'document_uploaded',
            'document_downloaded', 'setting_changed', 'blocker_resolved'].map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      <Card>
        <DataTable
          loading={isLoading}
          rows={data?.items}
          columns={[
            { key: 'created_at', label: 'زمان', render: (r) => toJalaliStr(r.created_at, true) },
            { key: 'action', label: 'رویداد', render: (r) => <span dir="ltr">{r.action}</span> },
            { key: 'actor_name', label: 'عامل' },
            { key: 'entity_type', label: 'رکورد', render: (r) => r.entity_type ?? '—' },
            { key: 'summary', label: 'شرح' },
            { key: 'ip', label: 'IP', render: (r) => <span dir="ltr">{r.ip ?? '—'}</span> },
          ]}
        />
      </Card>
    </div>
  )
}
