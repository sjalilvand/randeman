import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Card, Chip, Progress, StatCard, StatusChip } from '../components/ui'
import { PRIORITY, REPORT_STATUS, TASK_STATUS } from '../constants'
import { dueInfo, toJalaliStr } from '../jalali'

interface MyDash {
  computed_at: string
  cards: { open_tasks: number; overdue: number; pending_corrections: number; review_waiting: number; unread_notifications: number }
  my_tasks: { id: string; code: string; title: string; status: string; priority: string; progress: number; current_due_date: string | null }[]
  week_report: { week_start: string; status: string }
  workload: { ratio_pct: number | null; estimated_hours: number; capacity_hours: number; coverage_pct: number | null }
}

interface OrgDash {
  projects_by_status: Record<string, number>
  tasks_by_status: Record<string, number>
  open_blockers: number
  decisions_waiting: number
  overdue_top: { code: string; title: string; due: string | null; assignee: string }[]
  weekly_submission: { week_start: string; total: number; submitted: number }[]
}

export default function Dashboard() {
  const { user, hasRole } = useAuth()
  const mine = useQuery<MyDash>({ queryKey: ['dash-me'], queryFn: () => api('/dashboards/me') })
  const orgVisible = hasRole('senior_manager', 'pmo')
  const org = useQuery<OrgDash>({
    queryKey: ['dash-org'],
    queryFn: () => api('/dashboards/org'),
    enabled: orgVisible,
  })

  const c = mine.data?.cards
  return (
    <div>
      <div className="page-title">
        <div>
          <h2>سلام {user?.full_name} 👋</h2>
          <p className="muted">نمای کلی کارهای شما — به‌روزرسانی: {toJalaliStr(mine.data?.computed_at, true)}</p>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="کارهای باز من" value={c?.open_tasks ?? '…'} to="/tasks" />
        <StatCard label="معوق" value={c?.overdue ?? '…'} to="/tasks?overdue=1" />
        <StatCard label="نیازمند اصلاح" value={c?.pending_corrections ?? '…'} to="/tasks?status=needs_correction" />
        <StatCard label="در انتظار بررسی من" value={c?.review_waiting ?? '…'} to="/tasks?status=ready_for_review" />
        <StatCard label="اعلان‌های نخوانده" value={c?.unread_notifications ?? '…'} />
      </div>

      <div className="grid-2">
        <Card title="کارهای من (۱۰ مورد اخیر)" extra={<Link to="/tasks">همه وظایف ←</Link>}>
          <table>
            <thead><tr><th>کد</th><th>عنوان</th><th>وضعیت</th><th>پیشرفت</th><th>سررسید</th></tr></thead>
            <tbody>
              {(mine.data?.my_tasks ?? []).map((t) => {
                const due = dueInfo(t.current_due_date)
                return (
                  <tr key={t.id}>
                    <td><Link to={`/tasks/${t.id}`}>{t.code}</Link></td>
                    <td>{t.title}</td>
                    <td><StatusChip map={TASK_STATUS} value={t.status} /></td>
                    <td style={{ minWidth: 90 }}><Progress value={t.progress} /></td>
                    <td>{due.late ? <Chip label={due.text} tone="red" /> : due.soon ? <Chip label={due.text} tone="amber" /> : due.text}</td>
                  </tr>
                )
              })}
              {mine.data && mine.data.my_tasks.length === 0 && (
                <tr><td colSpan={5} className="muted" style={{ textAlign: 'center' }}>وظیفه بازی ندارید</td></tr>
              )}
            </tbody>
          </table>
        </Card>

        <div>
          <Card title="گزارش هفتگی این هفته">
            <p>
              وضعیت: <StatusChip map={REPORT_STATUS} value={mine.data?.week_report.status ?? 'none'} />
            </p>
            <Link className="btn btn-primary btn-sm" to="/weekly-report">مشاهده / ثبت گزارش</Link>
          </Card>
          <Card title="بار کاری این هفته">
            <p style={{ margin: '4px 0' }}>
              <Progress value={mine.data?.workload.ratio_pct ?? null} />
            </p>
            <p className="muted">
              ساعات تخمینی: {mine.data?.workload.estimated_hours ?? '—'} از ظرفیت {mine.data?.workload.capacity_hours ?? '—'} ساعت
              {mine.data?.workload.coverage_pct != null && <> — پوشش داده: {mine.data.workload.coverage_pct}٪</>}
            </p>
          </Card>
        </div>
      </div>

      {orgVisible && org.data && (
        <>
          <div className="stats-grid">
            <StatCard label="موانع باز سازمان" value={org.data.open_blockers} to="/blockers" />
            <StatCard label="در انتظار تصمیم مدیریت" value={org.data.decisions_waiting} to="/blockers" />
            <StatCard
              label="پروژه‌های فعال"
              value={org.data.projects_by_status['active'] ?? 0}
              to="/projects"
            />
          </div>
          <div className="grid-2">
            <Card title="تأخیرهای برجسته سازمان" extra={<Link to="/tasks?overdue=1">همه ←</Link>}>
              <table>
                <thead><tr><th>کد</th><th>عنوان</th><th>مسئول</th><th>سررسید</th></tr></thead>
                <tbody>
                  {org.data.overdue_top.map((t) => (
                    <tr key={t.code}>
                      <td>{t.code}</td>
                      <td>{t.title}</td>
                      <td>{t.assignee}</td>
                      <td><Chip label={dueInfo(t.due).text} tone="red" /></td>
                    </tr>
                  ))}
                  {org.data.overdue_top.length === 0 && (
                    <tr><td colSpan={4} className="muted" style={{ textAlign: 'center' }}>تأخیری ثبت نشده</td></tr>
                  )}
                </tbody>
              </table>
            </Card>
            <Card title="نرخ ارسال گزارش هفتگی (۴ هفته اخیر)">
              <table>
                <thead><tr><th>هفته</th><th>ارسال‌شده</th><th>کل</th></tr></thead>
                <tbody>
                  {org.data.weekly_submission.map((w) => (
                    <tr key={w.week_start}>
                      <td>{toJalaliStr(w.week_start)}</td>
                      <td>{w.submitted}</td>
                      <td>{w.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
          <Card title="وضعیت وظایف سازمان">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {Object.entries(org.data.tasks_by_status).map(([k, v]) => (
                <Chip key={k} label={`${TASK_STATUS[k]?.label ?? k}: ${v}`} tone={TASK_STATUS[k]?.tone ?? 'gray'} />
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
