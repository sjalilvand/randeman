import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { Card, ErrorBox, OkBox, PageTitle } from '../components/ui'

export default function Settings() {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const { data: settings } = useQuery<Record<string, any>>({ queryKey: ['settings'], queryFn: () => api('/settings') })
  const { data: metrics } = useQuery<any[]>({ queryKey: ['metric-defs'], queryFn: () => api('/settings/metrics') })

  const update = useMutation({
    mutationFn: ({ key, value }: { key: string; value: any }) => api(`/settings/${key}`, { method: 'PUT', body: { value } }),
    onSuccess: () => { setError(null); setOk('تنظیم ذخیره شد'); qc.invalidateQueries({ queryKey: ['settings'] }) },
    onError: (e: any) => setError(e.message),
  })

  return (
    <div>
      <PageTitle title="تنظیمات سامانه" subtitle="تنظیمات عمومی و تعریف نسخه‌بندی‌شده شاخص‌ها (سند ۷ و ۱۰.۲)" />
      <ErrorBox message={error} />
      <OkBox message={ok} />

      <Card title="تنظیمات عمومی">
        <form onSubmit={(e) => {
          e.preventDefault()
          const fd = new FormData(e.currentTarget as HTMLFormElement)
          update.mutate({ key: 'report_deadline_hour', value: Number(fd.get('report_deadline_hour')) })
          update.mutate({ key: 'default_weekly_capacity_hours', value: Number(fd.get('default_weekly_capacity_hours')) })
          update.mutate({ key: 'brand_title', value: String(fd.get('brand_title')) })
        }}>
          <div className="form-row-3">
            <label className="field">
              <span className="field-label">ساعت مهلت گزارش هفتگی</span>
              <input name="report_deadline_hour" type="number" min={0} max={23} defaultValue={settings?.report_deadline_hour?.value} />
              <span className="field-hint">{settings?.report_deadline_hour?.description}</span>
            </label>
            <label className="field">
              <span className="field-label">ظرفیت هفتگی پیش‌فرض (ساعت)</span>
              <input name="default_weekly_capacity_hours" type="number" min={1} max={80} step={0.5} defaultValue={settings?.default_weekly_capacity_hours?.value} />
            </label>
            <label className="field">
              <span className="field-label">عنوان نمایشی سامانه</span>
              <input name="brand_title" defaultValue={settings?.brand_title?.value} />
            </label>
          </div>
          <button className="btn btn-primary">ذخیره تنظیمات</button>
        </form>
      </Card>

      <Card title="تعریف شاخص‌ها (metric_definitions)">
        <table>
          <thead><tr><th>شاخص</th><th>نسخه</th><th>فرمول</th><th>توضیح</th></tr></thead>
          <tbody>
            {(metrics ?? []).map((m) => (
              <tr key={m.key}>
                <td><strong>{m.title_fa}</strong><div className="muted" dir="ltr">{m.key}</div></td>
                <td>v{m.version}</td>
                <td>{m.formula}</td>
                <td className="muted">{m.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
