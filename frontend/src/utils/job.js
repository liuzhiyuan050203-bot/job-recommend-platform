export const EDUCATION = [
  { value: 0, label: '不限' },
  { value: 1, label: '专科' },
  { value: 2, label: '本科' },
  { value: 3, label: '硕士' },
  { value: 4, label: '博士' }
]

export const EXPERIENCE = [
  { value: 0, label: '不限' },
  { value: 1, label: '应届生' },
  { value: 2, label: '一年以内' },
  { value: 3, label: '一到三年' },
  { value: 4, label: '三到五年' },
  { value: 5, label: '五年以上' }
]

export const JOB_TYPE = [
  { value: 1, label: '全职' },
  { value: 2, label: '实习' },
  { value: 3, label: '校招' }
]

export const AUDIT_STATUS = [
  { value: 0, label: '待审核' },
  { value: 1, label: '已通过' },
  { value: 2, label: '已驳回' }
]

export const APP_STATUS = [
  { value: 0, label: '待初筛' },
  { value: 1, label: '笔试' },
  { value: 2, label: '面试中' },
  { value: 3, label: '已录用' },
  { value: 4, label: '未通过' }
]

export const INTERVIEW_STATUS = [
  { value: 0, label: '待进行' },
  { value: 1, label: '已完成' },
  { value: 2, label: '已取消' },
  { value: 3, label: '学生缺席' }
]

export function labelOf(options, value) {
  const hit = options.find((item) => item.value === Number(value))
  return hit ? hit.label : '-'
}

export function salaryText(min, max, months) {
  if (min == null || max == null) return '-'
  const k = (n) => {
    if (n >= 1000) {
      const num = n / 1000
      return `${Number.isInteger(num) ? num : num.toFixed(1)}k`
    }
    return String(n)
  }
  return `${k(min)}-${k(max)}${months ? ` · ${months}薪` : ''}`
}

export function auditTagType(status) {
  if (status === 1) return 'success'
  if (status === 2) return 'danger'
  return 'warning'
}

export function appTagType(status) {
  if (status === 3) return 'success'
  if (status === 4) return 'danger'
  if (status === 2) return 'warning'
  return 'info'
}

export function mapCategoryOptions(list) {
  return (list || []).map((node) => {
    const item = { value: node.id, label: node.name }
    if (node.children && node.children.length) {
      item.children = mapCategoryOptions(node.children)
    }
    return item
  })
}

/** 职位数据来源：platform 企业发布 / self_crawl 校招官网同步 / ext_ats 外部来源（飞书招聘公开门户） */
export const JOB_SOURCE = {
  platform: { label: '企业发布', short: '企业发布', type: 'success', estimated: false },
  self_crawl: { label: '校招官网同步', short: '校招官网', type: 'info', estimated: true },
  ext_ats: { label: '外部来源', short: '外部来源', type: 'warning', estimated: true }
}

export const JOB_SOURCE_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'platform', label: '企业发布' },
  { value: 'self_crawl', label: '校招官网同步' },
  { value: 'ext_ats', label: '外部来源（需官网投递）' }
]

export function sourceMeta(code) {
  return JOB_SOURCE[code] || null
}

export function isExternalJob(job) {
  return job?.sourceCode === 'ext_ats'
}

export function isEstimatedSalary(job) {
  if (!job) return false
  if (job.salaryEstimated === true) return true
  return !!sourceMeta(job.sourceCode)?.estimated
}

export const ESTIMATE_TIP = '官网未公布薪资，此处为平台按技术方向与城市估算，仅供参考'
