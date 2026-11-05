import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Login from './pages/Login'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Projects = lazy(() => import('./pages/Projects'))
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'))
const Tasks = lazy(() => import('./pages/Tasks'))
const TaskDetail = lazy(() => import('./pages/TaskDetail'))
const Activities = lazy(() => import('./pages/Activities'))
const WeeklyReport = lazy(() => import('./pages/WeeklyReport'))
const ReviewQueue = lazy(() => import('./pages/ReviewQueue'))
const Documents = lazy(() => import('./pages/Documents'))
const Blockers = lazy(() => import('./pages/Blockers'))
const Users = lazy(() => import('./pages/Users'))
const OrgUnits = lazy(() => import('./pages/OrgUnits'))
const Audit = lazy(() => import('./pages/Audit'))
const Settings = lazy(() => import('./pages/Settings'))

function Guard({ children, roles }: { children: JSX.Element; roles?: string[] | null }) {
  const { user, loading, hasRole } = useAuth()
  if (loading) return <div className="page-loading">در حال بارگذاری…</div>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !hasRole(...roles)) return <div className="empty-state"><span>🔒</span><p>دسترسی مجاز نیست</p></div>
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Suspense fallback={<div className="page-loading">…</div>}><Dashboard /></Suspense>} />
        <Route path="/projects" element={<Suspense fallback={<div className="page-loading">…</div>}><Projects /></Suspense>} />
        <Route path="/projects/:id" element={<Suspense fallback={<div className="page-loading">…</div>}><ProjectDetail /></Suspense>} />
        <Route path="/tasks" element={<Suspense fallback={<div className="page-loading">…</div>}><Tasks /></Suspense>} />
        <Route path="/tasks/:id" element={<Suspense fallback={<div className="page-loading">…</div>}><TaskDetail /></Suspense>} />
        <Route path="/activities" element={<Suspense fallback={<div className="page-loading">…</div>}><Activities /></Suspense>} />
        <Route path="/weekly-report" element={<Suspense fallback={<div className="page-loading">…</div>}><WeeklyReport /></Suspense>} />
        <Route path="/review-queue" element={<Suspense fallback={<div className="page-loading">…</div>}><ReviewQueue /></Suspense>} />
        <Route path="/documents" element={<Suspense fallback={<div className="page-loading">…</div>}><Documents /></Suspense>} />
        <Route path="/blockers" element={<Suspense fallback={<div className="page-loading">…</div>}><Blockers /></Suspense>} />
        <Route path="/users" element={<Suspense fallback={<div className="page-loading">…</div>}><Users /></Suspense>} />
        <Route path="/org-units" element={<Suspense fallback={<div className="page-loading">…</div>}><OrgUnits /></Suspense>} />
        <Route path="/audit" element={<Suspense fallback={<div className="page-loading">…</div>}><Audit /></Suspense>} />
        <Route path="/settings" element={<Suspense fallback={<div className="page-loading">…</div>}><Settings /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
