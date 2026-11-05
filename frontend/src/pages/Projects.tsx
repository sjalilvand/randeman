import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Card, DataTable, ErrorBox, Field, Modal, PageTitle, Progress, StatusChip } from '../components/ui'
import { PROJECT_STATUS } from '../constants'
import { toJalaliStr } from '../jalali'

export default function Projects() {
  const { hasRole } = useAuth()
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState(params.get('status') ?? '')
  const [modalOpen, setModalOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['projects', q, statusFilter],
    queryFn: () => api<{ items: any[]; total: number }>('/projects', { params: { q, status_filter: statusFilter || undefined, size: 50 } }),
  })

  const create = useMutation({
    mutationFn: (body: any) => api('/projects', { body }),
    onSuccess: () => {
      setModalOpen(false)
      setError(null)
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
    onError: (e: any) => setError(e.message),
  })

  return (
    <div>
      <PageTitle
        title="پروژه‌ها"
        subtitle="پروژه، اعضا، مراحل و خروجی‌ها (سند ۵.۲)"
        actions={hasRole('unit_manager', 'project_manager', 'senior_manager', 'pmo') && (
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>+ پروژه جدید</button>
        )}
      />
      <div className="toolbar">
        <input placeholder="جست‌وجوی عنوان…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">همه وضعیت‌ها</option>
          {Object.entries(PROJECT_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <Card>
        <DataTable
          loading={isLoading}
          rows={data?.items}
          columns={[
            { key: 'code', label: 'کد', render: (r) => <Link to={`/projects/${r.id}`}>{r.code}</Link> },
            { key: 'title', label: 'عنوان' },
            { key: 'status', label: 'وضعیت', render: (r) => <StatusChip map={PROJECT_STATUS} value={r.status} /> },
            { key: 'manager_name', label: 'مدیر پروژه' },
            { key: 'lead_unit_name', label: 'واحد راهبر' },
            { key: 'task_count', label: 'وظایف' },
            { key: 'progress', label: 'پیشرفت', render: (r) => <Progress value={r.progress_reported} /> },
            { key: 'end_date', label: 'پایان', render: (r) => toJalaliStr(r.end_date) },
          ]}
        />
      </Card>

      <Modal open={modalOpen} title="ایجاد پروژه جدید" onClose={() => setModalOpen(false)} wide>
        <ErrorBox message={error} />
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const fd = new FormData(e.currentTarget as HTMLFormElement)
            create.mutate({
              title: fd.get('title'),
              description: fd.get('description') || null,
              goal: fd.get('goal') || null,
              category: fd.get('category') || null,
              sponsor: fd.get('sponsor') || null,
              start_date: fd.get('start_date') || null,
              end_date: fd.get('end_date') || null,
              status: 'active',
            })
          }}
        >
          <Field label="عنوان پروژه *"><input name="title" required minLength={3} /></Field>
          <Field label="شرح"><textarea name="description" /></Field>
          <Field label="هدف"><textarea name="goal" /></Field>
          <div className="form-row">
            <Field label="دسته"><input name="category" /></Field>
            <Field label="حامی"><input name="sponsor" /></Field>
          </div>
          <div className="form-row">
            <Field label="تاریخ شروع"><input name="start_date" type="date" /></Field>
            <Field label="تاریخ پایان"><input name="end_date" type="date" /></Field>
          </div>
          <button className="btn btn-primary" disabled={create.isPending}>ایجاد</button>
        </form>
      </Modal>
    </div>
  )
}
