<template>
  <div
    ref="chartRef"
    class="echart-container"
    :style="{ width, height }"
  ></div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

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
let disposed = false

let echartsLoader = null

function loadEcharts() {
  if (!echartsLoader) {
    echartsLoader = import('echarts').then((mod) => {
      if (mod && typeof mod.init === 'function') {
        return mod
      }
      if (mod?.default && typeof mod.default.init === 'function') {
        return mod.default
      }
      return mod
    })
  }
  return echartsLoader
}

const resize = () => {
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
}

const render = () => {
  if (!chartInstance.value) return
  if (props.loading) {
    chartInstance.value.showLoading()
    return
  }
  chartInstance.value.hideLoading()
  if (props.option) {
    chartInstance.value.setOption(props.option, true)
  }
}

const initChart = async () => {
  const echarts = await loadEcharts()
  if (disposed || !chartRef.value) return
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }

  chartInstance.value = echarts.init(chartRef.value, props.theme)
  render()

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
  () => {
    render()
  },
  { deep: true }
)

watch(
  () => props.loading,
  () => {
    render()
  }
)

onMounted(() => {
  nextTick(() => {
    initChart()
  })
})

onBeforeUnmount(() => {
  disposed = true
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
