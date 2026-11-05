import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

export interface CurrentUser {
  id: string
  username: string
  first_name: string
  last_name: string
  full_name: string
  position: string | null
  primary_unit_id: string | null
  roles: string[]
  capacity_hours_per_week: number | null
}

interface AuthCtx {
  user: CurrentUser | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasRole: (...codes: string[]) => boolean
}

const Ctx = createContext<AuthCtx>({
  user: null, loading: true, login: async () => {}, logout: async () => {}, hasRole: () => false,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<{ user: CurrentUser }>('/auth/me')
      .then((d) => setUser(d.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string) => {
    const d = await api<{ user: CurrentUser }>('/auth/login', { body: { username, password } })
    setUser(d.user)
  }

  const logout = async () => {
    try { await api('/auth/logout', { method: 'POST' }) } catch { /* noop */ }
    setUser(null)
  }

  const hasRole = (...codes: string[]) =>
    !!user && (user.roles.includes('sys_admin') || codes.some((c) => user.roles.includes(c)))

  return <Ctx.Provider value={{ user, loading, login, logout, hasRole }}>{children}</Ctx.Provider>
}

export function useAuth() {
  return useContext(Ctx)
}
