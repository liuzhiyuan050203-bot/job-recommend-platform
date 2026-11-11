<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="fill">
          <template #header>
            <div class="card-header">
              <span class="title">薪资预测</span>
              <span class="hint">已按你的档案预填，可修改后重新预测</span>
            </div>
          </template>
          <el-form ref="formRef" :model="form" :rules="rules" label-width="86px" @submit.prevent="submit">
            <el-form-item label="目标城市" prop="city">
              <el-select v-model="form.city" filterable allow-create default-first-option placeholder="如 北京" style="width: 100%">
                <el-option v-for="c in CITIES" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
            <el-form-item label="技术方向" prop="techDirection">
              <el-select v-model="form.techDirection" filterable placeholder="选择方向" style="width: 100%">
                <el-option v-for="d in directions" :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
            <el-form-item label="学历" prop="education">
              <el-radio-group v-model="form.education">
                <el-radio-button v-for="e in EDUCATION.filter((x) => x.value > 0)" :key="e.value" :value="e.value">{{ e.label }}</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="工作年限" prop="experienceYears">
              <el-input-number v-model="form.experienceYears" :min="0" :max="40" :step="0.5" :precision="1" />
              <span class="unit">年（应届生填 0）</span>
            </el-form-item>
            <el-form-item label="掌握技能">
              <el-select v-model="form.skills" multiple filterable allow-create default-first-option :multiple-limit="15" placeholder="可多选，影响预测" style="width: 100%">
                <el-option v-for="t in skillOptions" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loading" native-type="submit" icon="TrendCharts">开始预测</el-button>
              <el-button @click="fillFromProfile">恢复为我的档案</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="fill">
          <template #header><span class="title">预测结果</span></template>
          <div v-loading="loading" class="result-box">
            <el-empty v-if="!result && !loading" :image-size="80" :description="error || '填写左侧条件后点击「开始预测」'" />
            <template v-if="result">
              <div class="big">{{ yuan(result.predictedSalary) }}<span class="per">/ 月</span></div>
              <div class="range">参考区间 {{ yuan(result.ciLow) }} ~ {{ yuan(result.ciHigh) }}</div>
              <div class="bar">
                <div class="bar-fill" :style="barStyle" />
                <div class="bar-dot" :style="dotStyle" />
              </div>
              <div class="cond">
                {{ result.city }} · {{ result.techDirection }} · {{ labelOf(EDUCATION, result.education) }} ·
                {{ Number(result.experienceYears) > 0 ? `${result.experienceYears} 年经验` : '应届' }}
              </div>
              <div v-if="(result.skills || []).length" class="skills">
                <span class="muted">参与计算的技能：</span>
                <el-tag v-for="s in result.skills" :key="s" size="small" effect="plain">{{ s }}</el-tag>
              </div>
              <el-alert type="info" :closable="false" show-icon class="note">
                <template #title>
                  预测由薪资模型基于真实招聘薪资数据训练得到，仅供求职参考，不代表具体企业报价。
                  <span v-if="result.metrics && result.metrics.mae">模型平均绝对误差约 {{ yuan(result.metrics.mae) }}。</span>
                </template>
              </el-alert>
            </template>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="compare.length" shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">同条件不同城市对比</span>
          <span class="hint">其他条件不变，只换城市</span>
        </div>
      </template>
      <EChart :option="compareOption" height="300px" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import EChart from '@/components/EChart.vue'
import { getCategories, getSkillTags, predictSalary } from '@/api/public'
import { getStudentDashboard } from '@/api/student'
import { EDUCATION, labelOf } from '@/utils/job'

const CITIES = ['北京', '上海', '深圳', '广州', '杭州', '成都', '武汉', '南京', '西安', '苏州']
const formRef = ref()
const loading = ref(false)
const error = ref('')
const result = ref(null)
const compare = ref([])
const directions = ref([])
const skillOptions = ref([])
let profile = null
const form = reactive({ city: '', techDirection: '', education: 2, experienceYears: 0, skills: [] })

const rules = {
  city: [{ required: true, message: '请选择目标城市', trigger: 'change' }],
  techDirection: [{ required: true, message: '请选择技术方向', trigger: 'change' }],
  education: [{ required: true, message: '请选择学历', trigger: 'change' }]
}

function yuan(v) {
  const n = Number(v)
  return Number.isFinite(n) ? `${Math.round(n).toLocaleString('zh-CN')} 元` : '-'
}

const span = computed(() => {
  const r = result.value
  if (!r) return { lo: 0, hi: 1 }
  const lo = Math.max(0, Number(r.ciLow) * 0.8)
  const hi = Number(r.ciHigh) * 1.2
  return { lo, hi: hi > lo ? hi : lo + 1 }
})
const pct = (v) => `${Math.min(100, Math.max(0, ((Number(v) - span.value.lo) / (span.value.hi - span.value.lo)) * 100))}%`
const barStyle = computed(() => ({ left: pct(result.value?.ciLow), width: `calc(${pct(result.value?.ciHigh)} - ${pct(result.value?.ciLow)})` }))
const dotStyle = computed(() => ({ left: pct(result.value?.predictedSalary) }))

const compareOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (v) => `${v} 元/月` },
  grid: { left: 12, right: 16, top: 16, bottom: 8, containLabel: true },
  xAxis: { type: 'category', data: compare.value.map((c) => c.city) },
  yAxis: { type: 'value', name: '元/月' },
  series: [{
    type: 'bar',
    data: compare.value.map((c) => ({ value: Math.round(c.salary), itemStyle: { color: c.city === result.value?.city ? '#e6a23c' : '#409eff' } })),
    itemStyle: { borderRadius: [4, 4, 0, 0] },
    label: { show: true, position: 'top', formatter: ({ value }) => `${(value / 1000).toFixed(1)}k` }
  }]
}))

function params(city) {
  let skills = ''
  for (const s of form.skills) {
    const next = skills ? `${skills},${s}` : s
    if (next.length > 200) break
    skills = next
  }
  return { city, techDirection: form.techDirection, education: form.education, experienceYears: form.experienceYears ?? 0, skills: skills || undefined }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  error.value = ''
  try {
    result.value = await predictSalary(params(form.city))
    const others = CITIES.filter((c) => c !== form.city).slice(0, 5)
    const res = await Promise.allSettled([form.city, ...others].map((c) => predictSalary(params(c))))
    compare.value = res
      .map((r, i) => (r.status === 'fulfilled' ? { city: [form.city, ...others][i], salary: Number(r.value.predictedSalary) } : null))
      .filter(Boolean)
  } catch (e) {
    result.value = null
    compare.value = []
    error.value = '预测失败，请检查条件后重试'
  } finally {
    loading.value = false
  }
}

function fillFromProfile() {
  const p = profile || {}
  form.city = p.city || ''
  form.techDirection = p.techDirection || ''
  form.education = p.education || 2
  form.experienceYears = Number(p.experienceYears || 0)
  form.skills = [...(p.skills || [])].slice(0, 15)
}

function leafNames(nodes, acc = []) {
  for (const node of nodes || []) {
    if (node.children && node.children.length) leafNames(node.children, acc)
    else acc.push(node.name)
  }
  return acc
}

onMounted(async () => {
  const [board, cats, tags] = await Promise.allSettled([getStudentDashboard(), getCategories(), getSkillTags()])
  profile = board.status === 'fulfilled' ? board.value?.profile : null
  directions.value = cats.status === 'fulfilled' ? leafNames(cats.value) : []
  skillOptions.value = tags.status === 'fulfilled' ? [...new Set((tags.value || []).map((t) => t.name))] : []
  fillFromProfile()
  if (form.city && form.techDirection) submit()
})
</script>

<style scoped>
.fill { height: 100%; }
.el-row { row-gap: 16px; }
.unit { margin-left: 8px; color: var(--el-text-color-secondary); font-size: 13px; }
.result-box { min-height: 260px; }
.big { font-size: 36px; font-weight: 700; color: #409eff; }
.per { font-size: 16px; color: var(--el-text-color-secondary); margin-left: 6px; font-weight: 400; }
.range { margin-top: 6px; color: var(--el-text-color-regular); }
.bar { position: relative; height: 10px; background: #edf2f7; border-radius: 5px; margin: 16px 0; }
.bar-fill { position: absolute; top: 0; bottom: 0; background: #b3d8ff; border-radius: 5px; }
.bar-dot { position: absolute; top: -4px; width: 18px; height: 18px; margin-left: -9px; border-radius: 50%; background: #409eff; border: 3px solid #fff; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2); }
.cond { color: var(--el-text-color-regular); }
.skills { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 10px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.note { margin-top: 16px; }
</style>
