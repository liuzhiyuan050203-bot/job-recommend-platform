package com.bishe.job.vo;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AiMessageVO {

    private Long id;
    private Long sessionId;
    private String msgRole;
    private String content;
    /** 助手消息的 sources / tools / latency_ms，用户消息为空。 */
    private JsonNode extra;
    private LocalDateTime createTime;
}
