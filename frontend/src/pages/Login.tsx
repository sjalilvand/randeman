import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { ErrorBox } from '../components/ui'

export default function Login() {
  const { user, loading, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username.trim().toLowerCase(), password)
    } catch (err: any) {
      setError(err.message ?? 'ورود ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">ر</div>
        <h1>راندمان</h1>
        <p className="login-sub">سامانه مدیریت عملکرد، وظایف، پروژه‌ها و مستندات سازمانی</p>
        <ErrorBox message={error} />
        <label className="field">
          <span className="field-label">نام کاربری</span>
          <input dir="ltr" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label className="field">
          <span className="field-label">رمز عبور</span>
          <input dir="ltr" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        <button className="btn btn-primary" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'در حال ورود…' : 'ورود'}
        </button>
        <p className="muted" style={{ textAlign: 'center', marginTop: 14 }}>
          حساب شما توسط مدیر سامانه ایجاد می‌شود.
        </p>
      </form>
    </div>
  )
}
