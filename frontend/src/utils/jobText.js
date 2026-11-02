// 职位正文兜底解析：后端详情已给出 descriptionItems / requirementItems，
// 这里只在字段缺失（旧接口、收藏卡片等）时把 JSON 数组/对象、带序号文本、字面量 \n 整理成条目，
// 保证页面上不出现方括号、引号和抓取元数据。
const BULLET = /^\s*(?:[（(]?\d{1,2}[)）.、．:：](?!\d)|[•·\-*●▪]|[一二三四五六七八九十][、.])\s*/
const META = /^(【(校招官网投递|来源|项目\/方向|工作城市|抓取时间)】|岗位名称[:：]|本条记录由.*同步|投递链接[:：])/
const LIST_KEYS = ['requirements', 'requirement', 'duties', 'items', 'content', 'text', 'list']

function clean(line) {
  return String(line).replace(BULLET, '').replace(/[。；;，,\s]+$/, '').trim()
}

export function splitItems(text) {
  if (text == null) return []
  return String(text)
    .replace(/\\r\\n|\\n/g, '\n')
    .split(/\r?\n|；|;/)
    .map((s) => s.trim())
    .filter((s) => s && !META.test(s))
    .map(clean)
    .filter(Boolean)
}

function fromNode(node) {
  if (node == null) return []
  if (Array.isArray(node)) {
    return node.flatMap((item) => (item && typeof item === 'object'
      ? splitItems(item.text || item.content || item.name || item.value || '')
      : splitItems(item)))
  }
  if (typeof node === 'object') {
    for (const key of LIST_KEYS) {
      if (node[key] != null) {
        const items = fromNode(node[key])
        if (items.length) return items
      }
    }
    return [] // 纯元数据对象（如 provenance）不当正文展示
  }
  return splitItems(node)
}

export function parseJobText(raw) {
  if (raw == null) return []
  let value = String(raw).trim()
  if (!value) return []
  if (/^[[{"]/.test(value)) {
    try {
      let node = JSON.parse(value)
      if (typeof node === 'string' && /^[[{]/.test(node.trim())) node = JSON.parse(node)
      return fromNode(node)
    } catch {
      value = value.replace(/^[[{\s"]+|[\]}\s"]+$/g, '').replace(/\\"/g, '"').replace(/"\s*,\s*"/g, '\n').replace(/"/g, '')
    }
  }
  return splitItems(value)
}

// 从职位名称、职责、要求文本里识别技能词表中的标签。
// 英文标签要求前后不是字母（避免 Go 命中 Google、C 命中 CSS），不区分大小写；
// 同时比较去空格写法（SpringBoot ↔ Spring Boot）。
export function extractSkillIds(text, tags) {
  const raw = String(text || '')
  if (!raw.trim() || !Array.isArray(tags)) return []
  const lower = raw.toLowerCase()
  const compact = lower.replace(/\s+/g, '')
  const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const hits = []
  for (const tag of tags) {
    const name = String(tag?.name || '').trim().toLowerCase()
    if (!name) continue
    const ascii = /^[\x20-\x7e]+$/.test(name)
    let found
    if (ascii) {
      const pattern = (s) => new RegExp(`(^|[^a-z])${escape(s)}(?![a-z+#])`)
      found = pattern(name).test(lower) || pattern(name.replace(/\s+/g, '')).test(compact)
    } else {
      found = lower.includes(name) || compact.includes(name.replace(/\s+/g, ''))
    }
    if (found) hits.push(tag.id)
  }
  return hits
}
