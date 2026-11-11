<template>
  <div class="skill-chips">
    <el-tooltip
      v-for="skill in shown"
      :key="skill.tagId"
      :content="skill.matched ? '命中所投职位的技能要求' : '职位未要求此技能'"
      placement="top"
    >
      <el-tag
        :type="skill.matched ? 'success' : 'info'"
        :effect="skill.matched ? 'light' : 'plain'"
        size="small"
        class="chip"
      >
        <span v-if="skill.matched">✓ </span>{{ skill.tagName }} · {{ skill.proficiencyName || levelName(skill.proficiency) }}
      </el-tag>
    </el-tooltip>
    <span v-if="hidden > 0" class="more">+{{ hidden }}</span>
    <span v-if="!list.length" class="more">暂无技能</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  skills: { type: Array, default: () => [] },
  limit: { type: Number, default: 0 }
})

const LEVELS = ['入门', '熟悉', '掌握', '熟练', '精通']
const levelName = (p) => LEVELS[Math.min(5, Math.max(1, Number(p) || 3)) - 1]
const list = computed(() => props.skills || [])
const shown = computed(() => (props.limit > 0 ? list.value.slice(0, props.limit) : list.value))
const hidden = computed(() => list.value.length - shown.value.length)
</script>

<style scoped>
.skill-chips { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.chip { margin: 0; }
.more { color: var(--el-text-color-secondary); font-size: 12px; }
</style>
