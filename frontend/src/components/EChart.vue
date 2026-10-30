<template>
  <div
    ref="chartRef"
    class="echart-container"
    :style="{ width, height }"
  ></div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: {
    type: Object,
    required: true
  },
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '360px'
  },
  theme: {
    type: [String, Object],
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const chartRef = ref(null)
const chartInstance = shallowRef(null)
let resizeObserver = null

const resize = () => {
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
}

const initChart = () => {
  if (!chartRef.value) return
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }

  chartInstance.value = echarts.init(chartRef.value, props.theme)

  if (props.loading) {
    chartInstance.value.showLoading()
  } else if (props.option) {
    chartInstance.value.setOption(props.option)
  }

  // 使用 ResizeObserver 监听容器尺寸变化（兼容侧边栏折叠等场景）
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => {
      resize()
    })
    resizeObserver.observe(chartRef.value)
  }

  window.addEventListener('resize', resize)
}

watch(
  () => props.option,
  (newOpt) => {
    if (chartInstance.value && newOpt) {
      chartInstance.value.setOption(newOpt, true)
    }
  },
  { deep: true }
)

watch(
  () => props.loading,
  (loading) => {
    if (!chartInstance.value) return
    if (loading) {
      chartInstance.value.showLoading()
    } else {
      chartInstance.value.hideLoading()
    }
  }
)

onMounted(() => {
  nextTick(() => {
    initChart()
  })
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  window.removeEventListener('resize', resize)
  if (chartInstance.value) {
    chartInstance.value.dispose()
    chartInstance.value = null
  }
})

defineExpose({
  getInstance: () => chartInstance.value,
  resize
})
</script>

<style scoped>
.echart-container {
  min-height: 100px;
}
</style>
