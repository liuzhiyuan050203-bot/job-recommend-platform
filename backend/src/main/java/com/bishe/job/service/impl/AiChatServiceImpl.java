package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.AiChatRequest;
import com.bishe.job.dto.AiSessionRenameDTO;
import com.bishe.job.entity.AiMessage;
import com.bishe.job.entity.AiSession;
import com.bishe.job.mapper.AiMessageMapper;
import com.bishe.job.mapper.AiSessionMapper;
import com.bishe.job.security.LoginUser;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.AiChatService;
import com.bishe.job.vo.AiMessageVO;
import com.bishe.job.vo.AiSessionVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletResponse;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 会话落在本库，回答由 ai-service 流式生成。代理按事件原样转发，并在开头补一条 session 事件。
 */
@Slf4j
@Service
public class AiChatServiceImpl implements AiChatService {

    private static final int HISTORY_LIMIT = 6;
    private static final Duration STREAM_TIMEOUT = Duration.ofSeconds(300);

    private final AiSessionMapper sessionMapper;
    private final AiMessageMapper messageMapper;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate transactionTemplate;
    private final HttpClient httpClient;
    private final String baseUrl;
    private final String internalToken;

    public AiChatServiceImpl(AiSessionMapper sessionMapper,
                             AiMessageMapper messageMapper,
                             ObjectMapper objectMapper,
                             PlatformTransactionManager transactionManager,
                             @Value("${fastapi.base-url:http://localhost:8000}") String baseUrl,
                             @Value("${fastapi.internal-token:change-me-internal-token}") String internalToken) {
        this.sessionMapper = sessionMapper;
        this.messageMapper = messageMapper;
        this.objectMapper = objectMapper;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.baseUrl = baseUrl;
        this.internalToken = internalToken;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    @Override
    public ResponseEntity<StreamingResponseBody> open(String role, AiChatRequest request,
                                                       HttpServletResponse httpResponse) {
        int agentType = requireAgent(role);
        LoginUser user = UserContext.require();
        try {
            httpResponse.setBufferSize(128);
        } catch (IllegalStateException ignored) {
            // 响应已提交时保持容器默认缓冲，事件仍会按行 flush
        }
        AiTurn turn = prepare(user.getId(), agentType, request.getQuestion().trim(), request.getSessionId());
        // 流式写出发生在其他线程，先清掉当前线程的登录态，避免线程池复用串号
        UserContext.clear();
        StreamingResponseBody body = outputStream -> proxy(turn, outputStream);
        return ResponseEntity.ok()
                .header("X-Accel-Buffering", "no")
                .header("Cache-Control", "no-cache, no-transform")
                .header("Connection", "keep-alive")
                .contentType(MediaType.parseMediaType("text/event-stream;charset=UTF-8"))
                .body(body);
    }

    @Override
    public PageResult<AiSessionVO> sessions(String role, long current, long size) {
        int agentType = requireAgent(role);
        Long userId = UserContext.require().getId();
        Page<AiSession> page = Pages.of(current, size);
        sessionMapper.selectPage(page, new LambdaQueryWrapper<AiSession>()
                .eq(AiSession::getUserId, userId)
                .eq(AiSession::getAgentType, agentType)
                .orderByDesc(AiSession::getUpdateTime)
                .orderByDesc(AiSession::getId));
        List<AiSessionVO> records = new ArrayList<>();
        for (AiSession row : page.getRecords()) {
            records.add(toSessionVO(row));
        }
        return PageResult.of(page, records);
    }

    @Override
    public List<AiMessageVO> messages(String role, Long sessionId) {
        int agentType = requireAgent(role);
        own(UserContext.require().getId(), agentType, sessionId);
        List<AiMessage> rows = messageMapper.selectList(new LambdaQueryWrapper<AiMessage>()
                .eq(AiMessage::getSessionId, sessionId)
                .orderByAsc(AiMessage::getId));
        List<AiMessageVO> list = new ArrayList<>();
        for (AiMessage row : rows) {
            list.add(toMessageVO(row));
        }
        return list;
    }

    @Override
    public void delete(String role, Long sessionId) {
        int agentType = requireAgent(role);
        AiSession session = own(UserContext.require().getId(), agentType, sessionId);
        sessionMapper.deleteById(session.getId());
    }

    @Override
    public AiSessionVO rename(String role, Long sessionId, AiSessionRenameDTO dto) {
        int agentType = requireAgent(role);
        AiSession session = own(UserContext.require().getId(), agentType, sessionId);
        String title = dto.getTitle().trim();
        if (!StringUtils.hasText(title)) {
            throw new BusinessException(400, "标题不能为空");
        }
        session.setTitle(title);
        session.setUpdateTime(LocalDateTime.now());
        sessionMapper.updateById(session);
        return toSessionVO(sessionMapper.selectById(session.getId()));
    }

    /**
     * 校验或创建会话，写入用户消息，并取出该消息之前的最近 6 条作为历史。
     */
    private AiTurn prepare(Long userId, int agentType, String question, Long sessionId) {
        return transactionTemplate.execute(status -> {
            AiSession session;
            if (sessionId == null) {
                session = new AiSession();
                session.setUserId(userId);
                session.setAgentType(agentType);
                session.setTitle(titleOf(question));
                sessionMapper.insert(session);
            } else {
                session = own(userId, agentType, sessionId);
            }
            AiMessage userMsg = new AiMessage();
            userMsg.setSessionId(session.getId());
            userMsg.setMsgRole("user");
            userMsg.setContent(question);
            messageMapper.insert(userMsg);
            session.setUpdateTime(LocalDateTime.now());
            sessionMapper.updateById(session);

            List<AiMessage> recent = messageMapper.selectList(new LambdaQueryWrapper<AiMessage>()
                    .eq(AiMessage::getSessionId, session.getId())
                    .lt(AiMessage::getId, userMsg.getId())
                    .orderByDesc(AiMessage::getId)
                    .last("LIMIT " + HISTORY_LIMIT));
            Collections.reverse(recent);
            List<HistoryItem> history = new ArrayList<>();
            for (AiMessage message : recent) {
                if (!"user".equals(message.getMsgRole()) && !"assistant".equals(message.getMsgRole())) {
                    continue;
                }
                String content = message.getContent() == null ? "" : message.getContent().trim();
                if (content.isEmpty()) {
                    continue;
                }
                if (content.length() > 2000) {
                    content = content.substring(0, 2000);
                }
                history.add(new HistoryItem(message.getMsgRole(), content));
            }
            return new AiTurn(userId, session.getId(), session.getTitle(), question, RoleCodes.nameOf(agentType), history);
        });
    }

    private void proxy(AiTurn turn, OutputStream outputStream) {
        boolean sawDone = false;
        try {
            writeRaw(outputStream, "data: " + objectMapper.writeValueAsString(sessionEvent(turn)) + "\n\n");
            HttpRequest request = HttpRequest.newBuilder(URI.create(trimBase() + "/agent/chat/stream"))
                    .timeout(STREAM_TIMEOUT)
                    .header("Content-Type", "application/json;charset=UTF-8")
                    .header("Accept", "text/event-stream")
                    .header("X-Internal-Token", internalToken == null ? "" : internalToken)
                    .header("X-User-Id", Long.toString(turn.getUserId()))
                    .header("X-User-Role", turn.getRoleName())
                    .POST(HttpRequest.BodyPublishers.ofString(chatBody(turn), StandardCharsets.UTF_8))
                    .build();
            HttpResponse<InputStream> response;
            try {
                response = httpClient.send(request, HttpResponse.BodyHandlers.ofInputStream());
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                writeErrorAndDone(outputStream);
                return;
            } catch (Exception ex) {
                log.warn("连接 AI 服务失败 sessionId={}: {}", turn.getSessionId(), ex.getMessage());
                writeErrorAndDone(outputStream);
                return;
            }
            try (InputStream in = response.body()) {
                if (response.statusCode() != 200) {
                    log.warn("AI 服务返回状态 {} sessionId={}", response.statusCode(), turn.getSessionId());
                    writeErrorAndDone(outputStream);
                    return;
                }
                BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.startsWith("data:")) {
                        String payload = line.substring(5).trim();
                        if ("[DONE]".equals(payload)) {
                            sawDone = true;
                        } else {
                            rememberDone(turn, payload);
                        }
                    }
                    outputStream.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                    if (line.isEmpty()) {
                        outputStream.flush();
                    }
                }
            }
            if (!sawDone) {
                writeRaw(outputStream, "data: [DONE]\n\n");
            }
        } catch (IOException ex) {
            if (clientGone(ex)) {
                log.info("客户端断开 AI 流 sessionId={}", turn.getSessionId());
                return;
            }
            log.warn("AI 流中断 sessionId={}: {}", turn.getSessionId(), ex.getMessage());
            if (!sawDone) {
                try {
                    writeErrorAndDone(outputStream);
                } catch (IOException ignored) {
                    log.info("错误事件未能写出 sessionId={}", turn.getSessionId());
                }
            }
        }
    }

    private void rememberDone(AiTurn turn, String payload) {
        if (!StringUtils.hasText(payload) || !payload.startsWith("{") || turn.getAssistantSaved().get()) {
            return;
        }
        try {
            JsonNode node = objectMapper.readTree(payload);
            if (!"done".equals(node.path("type").asText())) {
                return;
            }
            saveAssistant(turn.getSessionId(), node);
            turn.getAssistantSaved().set(true);
        } catch (Exception ex) {
            log.warn("保存助手消息失败 sessionId={}: {}", turn.getSessionId(), ex.getMessage());
        }
    }

    private void saveAssistant(long sessionId, JsonNode done) {
        String answer = done.path("answer").asText("");
        ObjectNode extra = objectMapper.createObjectNode();
        extra.set("sources", done.path("sources").isArray() ? done.get("sources") : objectMapper.createArrayNode());
        extra.set("tools", done.path("tools").isArray() ? done.get("tools") : objectMapper.createArrayNode());
        if (done.hasNonNull("latency_ms")) {
            extra.set("latency_ms", done.get("latency_ms"));
        }
        if (done.hasNonNull("first_token_ms")) {
            extra.set("first_token_ms", done.get("first_token_ms"));
        }
        String extraJson;
        try {
            extraJson = objectMapper.writeValueAsString(extra);
        } catch (Exception ex) {
            extraJson = null;
        }
        String storedExtra = extraJson;
        transactionTemplate.executeWithoutResult(status -> {
            AiMessage message = new AiMessage();
            message.setSessionId(sessionId);
            message.setMsgRole("assistant");
            message.setContent(answer);
            message.setExtra(storedExtra);
            messageMapper.insert(message);
            sessionMapper.update(null, new LambdaUpdateWrapper<AiSession>()
                    .eq(AiSession::getId, sessionId)
                    .set(AiSession::getUpdateTime, LocalDateTime.now()));
        });
    }

    private ObjectNode sessionEvent(AiTurn turn) {
        ObjectNode node = objectMapper.createObjectNode();
        node.put("type", "session");
        node.put("session_id", turn.getSessionId());
        node.put("title", turn.getTitle());
        return node;
    }

    private String chatBody(AiTurn turn) throws IOException {
        ObjectNode body = objectMapper.createObjectNode();
        body.put("question", turn.getQuestion());
        body.put("session_id", turn.getSessionId());
        ArrayNode history = body.putArray("history");
        for (HistoryItem item : turn.getHistory()) {
            ObjectNode node = history.addObject();
            node.put("role", item.role());
            node.put("content", item.content());
        }
        return objectMapper.writeValueAsString(body);
    }

    private void writeErrorAndDone(OutputStream outputStream) throws IOException {
        writeRaw(outputStream, "data: {\"type\":\"error\",\"msg\":\"AI 服务暂不可用\"}\n\n");
        writeRaw(outputStream, "data: [DONE]\n\n");
    }

    private void writeRaw(OutputStream outputStream, String text) throws IOException {
        outputStream.write(text.getBytes(StandardCharsets.UTF_8));
        outputStream.flush();
    }

    private boolean clientGone(IOException ex) {
        String msg = ex.getMessage() == null ? "" : ex.getMessage().toLowerCase();
        return msg.contains("broken pipe")
                || msg.contains("connection reset")
                || msg.contains("stream closed")
                || msg.contains("中止")
                || ex.getClass().getSimpleName().contains("ClientAbort");
    }

    private AiSession own(Long userId, int agentType, Long sessionId) {
        if (sessionId == null) {
            throw new BusinessException(404, "会话不存在");
        }
        AiSession session = sessionMapper.selectById(sessionId);
        if (session == null || !userId.equals(session.getUserId()) || !Integer.valueOf(agentType).equals(session.getAgentType())) {
            throw new BusinessException(404, "会话不存在");
        }
        return session;
    }

    private int requireAgent(String role) {
        int agent = switch (role == null ? "" : role) {
            case "student" -> RoleCodes.STUDENT;
            case "company" -> RoleCodes.COMPANY;
            case "admin" -> RoleCodes.ADMIN;
            default -> throw new BusinessException(404, "接口不存在");
        };
        LoginUser user = UserContext.get();
        if (user != null && user.getRole() != null && user.getRole() != agent) {
            throw new BusinessException(403, "无权限，当前角色无法访问该接口");
        }
        return agent;
    }

    private String titleOf(String question) {
        String text = question.trim().replaceAll("\\s+", " ");
        if (text.codePointCount(0, text.length()) <= 20) {
            return text;
        }
        return text.substring(0, text.offsetByCodePoints(0, 20));
    }

    private String trimBase() {
        return baseUrl.replaceAll("/+$", "");
    }

    private AiSessionVO toSessionVO(AiSession row) {
        AiSessionVO vo = new AiSessionVO();
        vo.setId(row.getId());
        vo.setTitle(row.getTitle());
        vo.setAgentType(row.getAgentType());
        vo.setCreateTime(row.getCreateTime());
        vo.setUpdateTime(row.getUpdateTime());
        return vo;
    }

    private AiMessageVO toMessageVO(AiMessage row) {
        AiMessageVO vo = new AiMessageVO();
        vo.setId(row.getId());
        vo.setSessionId(row.getSessionId());
        vo.setMsgRole(row.getMsgRole());
        vo.setContent(row.getContent());
        vo.setCreateTime(row.getCreateTime());
        if (StringUtils.hasText(row.getExtra())) {
            try {
                vo.setExtra(objectMapper.readTree(row.getExtra()));
            } catch (Exception ex) {
                log.warn("消息 extra 不是合法 JSON id={}", row.getId());
            }
        }
        return vo;
    }

    @Getter
    private static final class AiTurn {
        private final Long userId;
        private final Long sessionId;
        private final String title;
        private final String question;
        private final String roleName;
        private final List<HistoryItem> history;
        private final AtomicBoolean assistantSaved = new AtomicBoolean(false);

        private AiTurn(Long userId, Long sessionId, String title, String question, String roleName, List<HistoryItem> history) {
            this.userId = userId;
            this.sessionId = sessionId;
            this.title = title;
            this.question = question;
            this.roleName = roleName;
            this.history = history;
        }
    }

    private record HistoryItem(String role, String content) {
    }
}
