import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, Chip, DataTable, ErrorBox, Field, Modal, PageTitle, StatusChip } from '../components/ui'
import { ROLES_FA } from '../constants'
import { toJalaliStr } from '../jalali'

const ROLE_CODES = Object.keys(ROLES_FA)

export default function Users() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<any | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['users', q],
    queryFn: () => api<{ items: any[]; total: number }>('/users', { params: { q, size: 100 } }),
  })

  const save = useMutation({
    mutationFn: (payload: any) =>
      editing
        ? api(`/users/${editing.id}`, { method: 'PUT', body: payload })
        : api('/users', { body: payload }),
    onSuccess: () => { setOpen(false); setEditing(null); setError(null); qc.invalidateQueries({ queryKey: ['users'] }) },
    onError: (e: any) => setError(e.message),
  })
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api(`/users/${id}/${active ? 'deactivate' : 'activate'}`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
    onError: (e: any) => setError(e.message),
  })

  const openEdit = (u: any | null) => {
    setEditing(u)
    setError(null)
    setOpen(true)
  }

  return (
    <div>
      <PageTitle
        title="کاربران"
        subtitle="غیرفعال‌سازی سوابق تاریخی را حذف نمی‌کند؛ تغییر نقش ثبت ممیزی دارد (سند ۴.۳)"
        actions={<button className="btn btn-primary" onClick={() => openEdit(null)}>+ کاربر جدید</button>}
      />
      <ErrorBox message={error} />
      <div className="toolbar">
        <input placeholder="جست‌وجو…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card>
        <DataTable
          loading={isLoading}
          rows={data?.items}
          columns={[
            { key: 'full_name', label: 'نام' },
            { key: 'username', label: 'نام کاربری', render: (r) => <span dir="ltr">{r.username}</span> },
            { key: 'position', label: 'سمت', render: (r) => r.position ?? '—' },
            { key: 'primary_unit_name', label: 'واحد', render: (r) => r.primary_unit_name ?? '—' },
            { key: 'roles', label: 'نقش‌ها', render: (r) => r.roles.map((x: string) => <Chip key={x} label={ROLES_FA[x] ?? x} tone="blue" />) },
            { key: 'is_active', label: 'وضعیت', render: (r) => r.is_active ? <Chip label="فعال" tone="green" /> : <Chip label="غیرفعال" tone="red" /> },
            { key: 'last_login_at', label: 'آخرین ورود', render: (r) => toJalaliStr(r.last_login_at, true) },
            {
              key: 'actions', label: 'عملیات',
              render: (r) => (
                <span style={{ display: 'flex', gap: 4 }}>
                  <button className="btn btn-sm" onClick={() => openEdit(r)}>ویرایش</button>
                  <button className={`btn btn-sm ${r.is_active ? 'btn-danger' : ''}`} onClick={() => toggle.mutate({ id: r.id, active: r.is_active })}>
                    {r.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}
                  </button>
                </span>
              ),
            },
          ]}
        />
      </Card>

      <Modal open={open} title={editing ? `ویرایش کاربر ${editing.username}` : 'ایجاد کاربر جدید'} onClose={() => setOpen(false)} wide>
        <ErrorBox message={error} />
        <form onSubmit={(e) => {
          e.preventDefault()
          const fd = new FormData(e.currentTarget as HTMLFormElement)
          const roles = ROLE_CODES.filter((c) => fd.get(`role-${c}`) === 'on')
          save.mutate({
            username: editing ? editing.username : fd.get('username'),
            password: fd.get('password') || null,
            first_name: fd.get('first_name'),
            last_name: fd.get('last_name'),
            personnel_code: fd.get('personnel_code') || null,
            position: fd.get('position') || null,
            email: fd.get('email') || null,
            phone: fd.get('phone') || null,
            capacity_hours_per_week: fd.get('capacity') ? Number(fd.get('capacity')) : null,
            work_start_date: fd.get('work_start_date') || null,
            direct_manager_id: fd.get('direct_manager_id') || null,
            roles,
          })
        }}>
          {!editing && (
            <Field label="نام کاربری *" hint="فقط حروف کوچک انگلیسی، رقم، نقطه، خط تیره">
              <input name="username" dir="ltr" required pattern="[a-z0-9_.\-]+" />
            </Field>
          )}
          <div className="form-row">
            <Field label="نام *"><input name="first_name" required defaultValue={editing?.first_name} /></Field>
            <Field label="نام خانوادگی *"><input name="last_name" required defaultValue={editing?.last_name} /></Field>
          </div>
          <div className="form-row">
            <Field label="رمز عبور" hint={editing ? 'خالی = بدون تغییر' : 'برای کاربر جدید الزامی (حداقل ۸ کاراکتر)'}>
              <input name="password" type="password" dir="ltr" minLength={8} required={!editing} />
            </Field>
            <Field label="شماره پرسنلی"><input name="personnel_code" defaultValue={editing?.personnel_code} /></Field>
          </div>
          <div className="form-row">
            <Field label="سمت"><input name="position" defaultValue={editing?.position} /></Field>
            <Field label="ایمیل"><input name="email" type="email" dir="ltr" defaultValue={editing?.email} /></Field>
          </div>
          <div className="form-row">
            <Field label="شناسه مدیر مستقیم (UUID)"><input name="direct_manager_id" dir="ltr" defaultValue={editing?.direct_manager_id} /></Field>
            <Field label="ظرفیت هفتگی (ساعت)"><input name="capacity" type="number" min={1} max={80} step={0.5} defaultValue={editing?.capacity_hours_per_week} /></Field>
          </div>
          <Field label="تاریخ شروع همکاری"><input name="work_start_date" type="date" /></Field>
          <Field label="نقش‌ها *" hint="مدیر سامانه به‌صورت پیش‌فرض تأییدکننده عملکرد نیست">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {ROLE_CODES.map((c) => (
                <label key={c} style={{ display: 'flex', gap: 4, alignItems: 'center', fontSize: '0.84rem' }}>
                  <input type="checkbox" name={`role-${c}`} defaultChecked={editing?.roles?.includes(c)} style={{ width: 'auto' }} />
                  {ROLES_FA[c]}
                </label>
              ))}
            </div>
          </Field>
          <button className="btn btn-primary" disabled={save.isPending}>ذخیره</button>
        </form>
      </Modal>
    </div>
  )
}
