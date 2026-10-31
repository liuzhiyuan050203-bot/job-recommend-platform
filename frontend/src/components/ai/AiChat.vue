<template>
  <div class="chat-shell">
    <el-card class="session-card" shadow="never">
      <div class="session-head">
        <span>会话</span>
        <el-button type="primary" size="small" @click="newChat">新对话</el-button>
      </div>
      <div v-loading="sessionsLoading" class="session-list">
        <div v-if="!sessions.length" class="session-empty">还没有会话</div>
        <div
          v-for="item in sessions"
          :key="item.id"
          class="session-item"
          :class="{ active: item.id === sessionId }"
          @click="openSession(item)"
        >
          <div class="session-title">{{ item.title }}</div>
          <div class="session-actions" @click.stop>
            <el-button link type="primary" @click="rename(item)">重命名</el-button>
            <el-button link type="danger" @click="remove(item)">删除</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="talk-card" shadow="never" :body-style="{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }">
      <div class="talk-head">
        <span class="talk-title">{{ title }}</span>
        <el-tag v-if="offline" type="warning" effect="plain">离线模式</el-tag>
      </div>

      <div ref="scroller" class="messages">
        <div v-if="!messages.length" class="empty">
          <p>可以直接提问，或点一个示例。</p>
          <div class="chips">
            <el-tag
              v-for="item in suggestions"
              :key="item"
              class="chip"
              effect="plain"
              @click="ask(item)"
            >{{ item }}</el-tag>
          </div>
        </div>

        <div v-for="(msg, index) in messages" :key="index" class="bubble" :class="msg.role">
          <div class="bubble-role">{{ msg.role === 'user' ? '我' : title }}</div>
          <div v-if="msg.role === 'user'" class="user-text">{{ msg.content }}</div>
          <template v-else>
            <div v-if="msg.status" class="status-line">
              <el-tag size="small" type="info">{{ msg.status }}</el-tag>
            </div>
            <div v-if="msg.tools.length" class="tool-line">
              <el-tag v-for="tool in msg.tools" :key="tool.name + tool.summary" size="small">
                调用工具 {{ tool.name }}
              </el-tag>
            </div>
            <div v-if="msg.error" class="error-line">{{ msg.error }}</div>
            <div v-if="msg.content" class="markdown" v-html="renderMarkdown(msg.content)" />
            <el-collapse v-if="msg.sources.length" class="sources">
              <el-collapse-item :title="`参考来源（${msg.sources.length}）`" name="sources">
                <div v-for="source in msg.sources" :key="source.index" class="source-item">
                  <div class="source-title">
                    [{{ source.index }}] {{ source.title || '资料' }}
                    <span v-if="source.section"> / {{ source.section }}</span>
                    <span v-if="source.score != null" class="score">相关度 {{ source.score }}</span>
                  </div>
                  <div v-if="source.snippet" class="snippet">{{ source.snippet }}</div>
                </div>
              </el-collapse-item>
            </el-collapse>
            <div v-if="msg.latencyMs != null" class="latency">耗时 {{ (msg.latencyMs / 1000).toFixed(1) }} 秒</div>
          </template>
        </div>
      </div>

      <div class="composer">
        <el-input
          v-model="draft"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 6 }"
          maxlength="2000"
          show-word-limit
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          :disabled="streaming"
          @keydown="onKeydown"
        />
        <div class="composer-actions">
          <el-button v-if="streaming" type="danger" plain @click="stop">停止</el-button>
          <el-button v-else type="primary" :disabled="!draft.trim()" @click="send">发送</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { deleteSession, listMessages, listSessions, renameSession, streamUrl } from '@/api/ai'

const props = defineProps({
  role: { type: String, required: true },
  title: { type: String, required: true }
})

const SUGGESTIONS = {
  student: [
    '三方协议怎么签？',
    '推荐适合我的岗位',
    '北京后端应届薪资大概多少',
    '我投Java后端还缺什么技能'
  ],
  company: [
    '帮我写一个Java后端校招JD',
    '帮我筛选我发布职位的候选人',
    '列出我发布的职位'
  ],
  admin: [
    '哪个城市岗位最多',
    '本月热门技能有哪些',
    '平台概况',
    '推荐算法评估指标'
  ]
}

marked.setOptions({ gfm: true, breaks: true })

const suggestions = computed(() => SUGGESTIONS[props.role] || [])
const sessions = ref([])
const sessionsLoading = ref(false)
const sessionId = ref(null)
const messages = ref([])
const draft = ref('')
const streaming = ref(false)
const offline = ref(false)
const scroller = ref(null)
let controller = null

function renderMarkdown(text) {
  const html = marked.parse(text || '', { async: false })
  return DOMPurify.sanitize(typeof html === 'string' ? html : '')
}

function blankAssistant() {
  return {
    role: 'assistant',
    content: '',
    sources: [],
    tools: [],
    status: '',
    error: '',
    latencyMs: null,
    mode: ''
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = scroller.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const page = await listSessions(props.role, { current: 1, size: 50 })
    sessions.value = page?.records || []
  } finally {
    sessionsLoading.value = false
  }
}

function mapHistory(row) {
  const extra = row.extra && typeof row.extra === 'object' ? row.extra : {}
  if (row.msgRole === 'user') {
    return { role: 'user', content: row.content || '' }
  }
  return {
    role: 'assistant',
    content: row.content || '',
    sources: Array.isArray(extra.sources) ? extra.sources : [],
    tools: Array.isArray(extra.tools) ? extra.tools : [],
    status: '',
    error: '',
    latencyMs: extra.latency_ms ?? null,
    mode: extra.mode || ''
  }
}

async function openSession(item) {
  if (streaming.value) {
    stop()
  }
  sessionId.value = item.id
  offline.value = false
  const rows = await listMessages(props.role, item.id)
  messages.value = (rows || []).map(mapHistory)
  scrollToBottom()
}

function newChat() {
  if (streaming.value) {
    stop()
  }
  sessionId.value = null
  messages.value = []
  offline.value = false
  draft.value = ''
}

async function rename(item) {
  try {
    const { value } = await ElMessageBox.prompt('会话标题', '重命名', {
      inputValue: item.title,
      inputValidator: (text) => (text && text.trim() && text.trim().length <= 128) || '标题长度为 1 到 128'
    })
    const updated = await renameSession(props.role, item.id, value.trim())
    item.title = updated?.title || value.trim()
  } catch (err) {
    if (err === 'cancel' || err === 'close') {
      return
    }
  }
}

async function remove(item) {
  try {
    await ElMessageBox.confirm(`删除会话「${item.title}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  await deleteSession(props.role, item.id)
  if (sessionId.value === item.id) {
    newChat()
  }
  await loadSessions()
}

function ask(text) {
  if (streaming.value) {
    return
  }
  draft.value = text
  send()
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

function stop() {
  if (controller) {
    controller.abort()
    controller = null
  }
  streaming.value = false
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant') {
    last.status = ''
  }
}

function applyEvent(evt, assistant) {
  if (!evt || typeof evt !== 'object') {
    return
  }
  if (evt.type === 'session') {
    sessionId.value = evt.session_id
    return
  }
  if (evt.type === 'meta') {
    assistant.mode = evt.mode || ''
    offline.value = evt.mode === 'offline'
    return
  }
  if (evt.type === 'status') {
    assistant.status = evt.text || ''
    return
  }
  if (evt.type === 'tool') {
    assistant.tools.push({ name: evt.name || 'tool', summary: evt.summary || '' })
    assistant.status = `调用工具 ${evt.name || ''}`.trim()
    return
  }
  if (evt.type === 'sources') {
    assistant.sources = Array.isArray(evt.items) ? evt.items : []
    return
  }
  if (evt.type === 'delta') {
    assistant.content += evt.text || ''
    return
  }
  if (evt.type === 'error') {
    assistant.error = evt.msg || '对话失败'
    assistant.status = ''
    return
  }
  if (evt.type === 'done') {
    if (evt.answer) {
      assistant.content = evt.answer
    }
    if (Array.isArray(evt.sources)) {
      assistant.sources = evt.sources
    }
    if (Array.isArray(evt.tools) && evt.tools.length) {
      assistant.tools = evt.tools
    }
    assistant.latencyMs = evt.latency_ms ?? assistant.latencyMs
    assistant.status = ''
  }
}

function handleBlock(block, assistant) {
  const lines = block.split(/\r?\n/)
  for (const line of lines) {
    if (!line.startsWith('data:')) {
      continue
    }
    const payload = line.slice(5).trim()
    if (!payload || payload === '[DONE]') {
      continue
    }
    try {
      applyEvent(JSON.parse(payload), assistant)
    } catch {
      // 半包已在外层缓冲，解析失败的单行忽略
    }
  }
}

async function send() {
  const question = draft.value.trim()
  if (!question || streaming.value) {
    return
  }
  draft.value = ''
  messages.value.push({ role: 'user', content: question })
  const assistant = blankAssistant()
  messages.value.push(assistant)
  streaming.value = true
  scrollToBottom()
  controller = new AbortController()
  const token = localStorage.getItem('token')
  try {
    const response = await fetch(streamUrl(props.role), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify({
        question,
        ...(sessionId.value ? { sessionId: sessionId.value } : {})
      }),
      signal: controller.signal
    })
    if (!response.ok) {
      messages.value.splice(-2, 2)
      let msg = '发送失败'
      try {
        const data = await response.json()
        msg = data.msg || msg
      } catch {
        // 非 JSON 错误保持默认文案
      }
      ElMessage.error(msg)
      streaming.value = false
      return
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      let splitAt = buffer.indexOf('\n\n')
      while (splitAt >= 0) {
        const block = buffer.slice(0, splitAt)
        buffer = buffer.slice(splitAt + 2)
        handleBlock(block, assistant)
        scrollToBottom()
        splitAt = buffer.indexOf('\n\n')
      }
    }
    if (buffer.trim()) {
      handleBlock(buffer, assistant)
    }
    assistant.status = ''
    await loadSessions()
  } catch (err) {
    if (err?.name === 'AbortError') {
      assistant.status = ''
      return
    }
    assistant.error = assistant.error || '网络连接异常'
    assistant.status = ''
  } finally {
    streaming.value = false
    controller = null
    scrollToBottom()
  }
}

onMounted(loadSessions)
</script>

<style scoped>
.chat-shell {
  display: flex;
  gap: 16px;
  height: calc(100vh - 168px);
  min-height: 520px;
}
.session-card,
.talk-card {
  height: 100%;
  min-height: 0;
}
.session-card {
  width: 260px;
  flex: none;
  display: flex;
  flex-direction: column;
}
.session-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.session-head,
.talk-head,
.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.session-list {
  margin-top: 12px;
  overflow: auto;
  flex: 1;
}
.session-empty {
  color: #909399;
  font-size: 13px;
}
.session-item {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
}
.session-item.active {
  background: #ecf5ff;
}
.session-item:hover {
  background: #f5f7fa;
}
.session-title {
  font-size: 14px;
  line-height: 1.4;
  word-break: break-all;
}
.session-actions {
  display: flex;
  gap: 4px;
}
.talk-card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.talk-card :deep(.el-card__body) {
  height: 100%;
}
.talk-title {
  font-weight: 600;
  font-size: 16px;
}
.messages {
  flex: 1;
  overflow: auto;
  margin: 12px 0;
  min-height: 0;
}
.empty {
  color: #606266;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  cursor: pointer;
}
.bubble {
  margin-bottom: 14px;
  max-width: 100%;
}
.bubble.user .user-text {
  white-space: pre-wrap;
  background: #ecf5ff;
  border-radius: 8px;
  padding: 10px 12px;
}
.bubble-role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.status-line,
.tool-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}
.error-line {
  color: #f56c6c;
  margin-bottom: 6px;
}
.markdown {
  line-height: 1.7;
  word-break: break-word;
}
.markdown :deep(pre) {
  background: #f6f8fa;
  padding: 10px;
  overflow: auto;
  border-radius: 6px;
}
.markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
}
.markdown :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
}
.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
}
.sources {
  margin-top: 8px;
}
.source-item {
  margin-bottom: 8px;
}
.source-title {
  font-size: 13px;
}
.score,
.latency,
.snippet {
  color: #909399;
  font-size: 12px;
}
.snippet {
  margin-top: 2px;
}
.composer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
