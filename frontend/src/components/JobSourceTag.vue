<template>
  <span v-if="meta || estimated" class="job-source-tag">
    <el-tooltip v-if="meta && sourceCode !== 'platform'" :content="tip" placement="top">
      <el-tag size="small" :type="meta.type" effect="plain">{{ meta.short }}</el-tag>
    </el-tooltip>
    <el-tag v-else-if="meta && showPlatform" size="small" :type="meta.type" effect="plain">{{ meta.short }}</el-tag>
    <el-tooltip v-if="estimated && showEstimate" :content="ESTIMATE_TIP" placement="top">
      <el-tag size="small" type="warning" effect="light">估算薪资</el-tag>
    </el-tooltip>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { ESTIMATE_TIP, isEstimatedSalary, sourceMeta } from '@/utils/job'

const props = defineProps({
  job: { type: Object, default: null },
  /** 企业发布职位也显示来源标签（默认不显示，减少噪音） */
  showPlatform: { type: Boolean, default: false },
  showEstimate: { type: Boolean, default: true }
})

const sourceCode = computed(() => props.job?.sourceCode || '')
const meta = computed(() => sourceMeta(sourceCode.value))
const estimated = computed(() => isEstimatedSalary(props.job))
const tip = computed(() => {
  if (sourceCode.value === 'ext_ats') return '外部来源：同步自企业招聘官网公开职位，需到官网投递'
  if (sourceCode.value === 'self_crawl') return '校招官网同步：同步自企业校招官网公开职位，需到官网投递'
  return ''
})
</script>

<style scoped>
.job-source-tag {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
</style>
