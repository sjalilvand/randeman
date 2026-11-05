/** کلاینت API — نشست مبتنی بر Cookie هم‌مبدأ + سربرگ CSRF (سند ۱۳.۱ و ۱۱.۳) */

export class ApiError extends Error {
  status: number
  code: string
  constructor(status: number, message: string, code = 'error') {
    super(message)
    this.status = status
    this.code = code
  }
}

export type Params = Record<string, string | number | boolean | undefined | null>

function buildQuery(params?: Params): string {
  if (!params) return ''
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  })
  const s = q.toString()
  return s ? `?${s}` : ''
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: unknown; form?: FormData; params?: Params } = {},
): Promise<T> {
  const method = opts.method ?? (opts.body || opts.form ? 'POST' : 'GET')
  const headers: Record<string, string> = { 'X-Requested-With': 'XMLHttpRequest' }
  let body: BodyInit | undefined
  if (opts.form) {
    body = opts.form
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  const resp = await fetch(`/api/v1${path}${buildQuery(opts.params)}`, {
    method,
    headers,
    body,
    credentials: 'include',
  })
  if (resp.status === 204) return undefined as T
  let data: any = null
  try {
    data = await resp.json()
  } catch {
    data = null
  }
  if (!resp.ok) {
    const msg = data?.error?.message ?? data?.detail ?? `خطا (${resp.status})`
    throw new ApiError(resp.status, msg, data?.error?.code ?? 'error')
  }
  return data as T
}

export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const resp = await fetch(`/api/v1${path}`, { credentials: 'include' })
  if (!resp.ok) {
    let msg = `خطا (${resp.status})`
    try {
      const j = await resp.json()
      msg = j?.detail ?? msg
    } catch { /* noop */ }
    throw new ApiError(resp.status, msg)
  }
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fallbackName
  a.click()
  URL.revokeObjectURL(url)
}
