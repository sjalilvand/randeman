/** برچسب‌های فارسی وضعیت‌ها و مقادیر کنترل‌شده (مطابق سند ۵) */

export const TASK_STATUS: Record<string, { label: string; tone: string }> = {
  draft: { label: 'پیش‌نویس', tone: 'gray' },
  assigned: { label: 'تخصیص‌یافته', tone: 'blue' },
  in_progress: { label: 'در حال انجام', tone: 'amber' },
  ready_for_review: { label: 'آماده بررسی', tone: 'purple' },
  completed: { label: 'تکمیل و تأییدشده', tone: 'green' },
  needs_correction: { label: 'نیازمند اصلاح', tone: 'red' },
  blocked: { label: 'متوقف', tone: 'darkred' },
  cancelled: { label: 'لغوشده', tone: 'slate' },
}

export const REPORT_STATUS: Record<string, { label: string; tone: string }> = {
  draft: { label: 'پیش‌نویس', tone: 'gray' },
  submitted: { label: 'ارسال‌شده', tone: 'blue' },
  in_review: { label: 'در حال بررسی', tone: 'purple' },
  approved: { label: 'تأییدشده', tone: 'green' },
  needs_correction: { label: 'نیازمند اصلاح', tone: 'red' },
  none: { label: 'ساخته نشده', tone: 'slate' },
}

export const PROJECT_STATUS: Record<string, { label: string; tone: string }> = {
  draft: { label: 'پیش‌نویس', tone: 'gray' },
  active: { label: 'فعال', tone: 'green' },
  paused: { label: 'متوقف', tone: 'amber' },
  completed: { label: 'تکمیل‌شده', tone: 'blue' },
  cancelled: { label: 'لغوشده', tone: 'slate' },
}

export const PRIORITY: Record<string, { label: string; tone: string }> = {
  low: { label: 'کم', tone: 'gray' },
  medium: { label: 'متوسط', tone: 'blue' },
  high: { label: 'زیاد', tone: 'amber' },
  critical: { label: 'بحرانی', tone: 'red' },
}

export const DOC_STATUS: Record<string, { label: string; tone: string }> = {
  quarantined: { label: 'در قرنطینه', tone: 'amber' },
  ready: { label: 'آماده', tone: 'green' },
  rejected: { label: 'رد شده', tone: 'red' },
}

export const BLOCKER_STATUS: Record<string, { label: string; tone: string }> = {
  open: { label: 'باز', tone: 'red' },
  resolved: { label: 'رفع شده', tone: 'green' },
  cancelled: { label: 'لغوشده', tone: 'slate' },
}

export const BLOCKER_TYPE: Record<string, string> = {
  info_missing: 'کمبود اطلاعات',
  inter_unit_dependency: 'وابستگی بین‌واحدی',
  resource_shortage: 'کمبود منابع',
  awaiting_decision: 'انتظار تصمیم',
  technical_issue: 'مشکل فنی',
  priority_change: 'تغییر اولویت',
  external_factor: 'عامل بیرونی',
  other: 'سایر',
}

export const ACTIVITY_TYPE: Record<string, string> = {
  execution: 'اجرایی',
  analysis: 'تحلیلی',
  meeting: 'جلسه',
  coordination: 'هماهنگی',
  documentation: 'مستندسازی',
  fix: 'رفع اشکال',
  training: 'آموزش',
  support: 'پشتیبانی',
  other: 'سایر',
}

export const ITEM_KIND: Record<string, string> = {
  done: 'خروجی تکمیل‌شده',
  ongoing: 'کار جاری',
  delay: 'تأخیر',
  unplanned: 'خارج از برنامه',
}

export const CONFIDENTIALITY: Record<string, string> = {
  internal: 'داخلی',
  restricted: 'محدود',
  secret: 'محرمانه',
}

export const ROLES_FA: Record<string, string> = {
  senior_manager: 'مدیر ارشد',
  unit_manager: 'مدیر واحد',
  project_manager: 'مدیر پروژه',
  employee: 'کارمند / کارشناس',
  pmo: 'مسئول تعالی / PMO',
  observer: 'ناظر',
  auditor: 'ممیز',
  sys_admin: 'مدیر سامانه',
}

export const CHANGE_REQ_STATUS: Record<string, { label: string; tone: string }> = {
  pending: { label: 'در انتظار تصمیم', tone: 'amber' },
  approved: { label: 'موافقت شده', tone: 'green' },
  rejected: { label: 'رد شده', tone: 'red' },
}
