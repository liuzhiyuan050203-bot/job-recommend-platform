/** 投递弹窗：过滤测试/污染简历，并按「校招默认 > 校招 > 默认 > 最近」排序。 */
export const TEST_RESUME_TITLE = /UX-IDOR|越权|测试简历|_勿用|流程测试|匹配测试|详情整理|推荐测试|隔离职位|夹具/i

export function isTestResumeTitle(title) {
  return TEST_RESUME_TITLE.test(String(title || ''))
}

export function pickApplyResumes(list) {
  return (list || [])
    .filter((item) => !isTestResumeTitle(item.title))
    .slice()
    .sort((a, b) => {
      const score = (r) => (r.isDefault === 1 ? 2 : 0) + ((r.title || '').includes('校招') ? 1 : 0)
      const d = score(b) - score(a)
      if (d !== 0) return d
      return String(b.updateTime || '').localeCompare(String(a.updateTime || ''))
    })
}

export function preferredApplyResume(list) {
  const usable = pickApplyResumes(list)
  return (
    usable.find((item) => (item.title || '').includes('校招') && item.isDefault === 1)
    || usable.find((item) => (item.title || '').includes('校招'))
    || usable.find((item) => item.isDefault === 1)
    || usable[0]
    || null
  )
}

/** 合并档案技能与简历 skillDesc，并按职位 tagNames 标记命中。 */
export function mergePreviewSkills(profileSkills, skillDesc, jobTagNames) {
  const LEVELS = ['入门', '掌握', '熟悉', '熟练', '精通']
  const jobSet = new Set((jobTagNames || []).map((n) => String(n).toLowerCase()))
  const map = new Map()
  for (const sk of profileSkills || []) {
    const name = sk.tagName || sk.name
    if (!name) continue
    map.set(String(name).toLowerCase(), {
      name,
      proficiencyName: sk.proficiencyName || LEVELS[Math.min(5, Math.max(1, Number(sk.proficiency) || 3)) - 1],
      matched: jobSet.has(String(name).toLowerCase())
    })
  }
  for (const part of String(skillDesc || '').split(/[、,，;；/|\n]+/)) {
    const raw = part.trim().replace(/[。.\s]+$/g, '')
    if (!raw) continue
    const base = raw.replace(/\s*(入门|掌握|熟悉|熟练|精通)$/u, '').trim() || raw
    const key = raw.toLowerCase()
    if (map.has(key) || map.has(base.toLowerCase())) continue
    map.set(key, {
      name: base,
      proficiencyName: '',
      matched: jobSet.has(base.toLowerCase()) || jobSet.has(key)
    })
  }
  return [...map.values()].sort((a, b) => Number(b.matched) - Number(a.matched) || a.name.localeCompare(b.name, 'zh'))
}
