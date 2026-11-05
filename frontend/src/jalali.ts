/** تبدیل تاریخ میلادی به شمسی و قالب‌بندی فارسی (سند ۱۰.۵) */
import jalaali from 'jalaali-js'

const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']

export function toFa(input: string | number): string {
  return String(input).replace(/\d/g, (d) => FA_DIGITS[Number(d)])
}

export function toJalaliStr(iso: string | null | undefined, withTime = false): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const j = jalaali.toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate())
  const base = toFa(`${j.jy}/${String(j.jm).padStart(2, '0')}/${String(j.jd).padStart(2, '0')}`)
  if (!withTime) return base
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${base} ${toFa(`${hh}:${mm}`)}`
}

const MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

export function jalaliLongDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const j = jalaali.toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate())
  return toFa(`${j.jd} ${MONTHS[j.jm - 1]} ${j.jy}`)
}

export function todayIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** شنبه هفته جاری به وقت مرورگر */
export function currentWeekStart(): string {
  const d = new Date()
  const offset = (d.getDay() + 1) % 7 // یکشنبه=0 → ۱ روز تا شنبه؛ شنبه=6 → 0
  d.setDate(d.getDate() - offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function shiftWeek(weekStartIso: string, weeks: number): string {
  const d = new Date(weekStartIso)
  d.setDate(d.getDate() + weeks * 7)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function dueInfo(iso: string | null | undefined): { text: string; late: boolean; soon: boolean } {
  if (!iso) return { text: '—', late: false, soon: false }
  const due = new Date(iso)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.round((due.getTime() - today.getTime()) / 86400000)
  if (days < 0) return { text: `${toFa(Math.abs(days))} روز تأخیر`, late: true, soon: false }
  if (days === 0) return { text: 'سررسید امروز', late: false, soon: true }
  if (days <= 3) return { text: `${toFa(days)} روز مانده`, late: false, soon: true }
  return { text: toJalaliStr(iso), late: false, soon: false }
}
