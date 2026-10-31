package com.bishe.job.client;

import com.bishe.job.common.BusinessException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.math.BigDecimal;
import java.net.URI;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Component
public class FastApiClient {

    private final RestTemplate restTemplate;
    private final RestTemplate sparkRestTemplate;
    private final RestTemplate aiRestTemplate;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final String internalToken;

    public FastApiClient(RestTemplate restTemplate,
                         ObjectMapper objectMapper,
                         @Value("${fastapi.base-url:http://localhost:8000}") String baseUrl,
                         @Value("${fastapi.internal-token:change-me-internal-token}") String internalToken) {
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl;
        this.internalToken = internalToken;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(3));
        factory.setReadTimeout(Duration.ofSeconds(180));
        this.sparkRestTemplate = new RestTemplate(factory);
        SimpleClientHttpRequestFactory aiFactory = new SimpleClientHttpRequestFactory();
        aiFactory.setConnectTimeout(Duration.ofSeconds(5));
        aiFactory.setReadTimeout(Duration.ofSeconds(300));
        this.aiRestTemplate = new RestTemplate(aiFactory);
    }

    /**
     * 检查 FastAPI 服务健康状态。
     * 发生异常时返回 "DOWN"，不向外抛出异常。
     */
    public String checkHealth() {
        try {
            String url = trimBase() + "/health";
            ResponseEntity<String> response = restTemplate.exchange(
                    url, HttpMethod.GET, new HttpEntity<>(tokenHeaders()), String.class);
            if (response.getStatusCode().is2xxSuccessful()) {
                return "UP";
            }
            return "DOWN";
        } catch (Exception e) {
            log.warn("FastAPI 健康检查失败: {}", e.getMessage());
            return "DOWN";
        }
    }

    public JsonNode runSpark(List<String> tasks) {
        Map<String, Object> body = new LinkedHashMap<>();
        if (tasks != null) {
            body.put("tasks", tasks);
        }
        return post("/spark/run", body);
    }

    public JsonNode listSparkTasks(Integer current, Integer size, String batchNo) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(trimBase() + "/spark/tasks");
        if (current != null) {
            builder.queryParam("current", current);
        }
        if (size != null) {
            builder.queryParam("size", size);
        }
        if (StringUtils.hasText(batchNo)) {
            builder.queryParam("batch_no", batchNo.trim());
        }
        return get(builder);
    }

    public JsonNode runRecommend() {
        return post("/recommend/run", new LinkedHashMap<>());
    }

    public JsonNode recommendUser(long userId, int topK) {
        UriComponentsBuilder builder = UriComponentsBuilder
                .fromHttpUrl(trimBase() + "/recommend/user/" + userId)
                .queryParam("top_k", topK);
        return get(builder);
    }

    public JsonNode predictSalary(String city, String techDirection, Integer education,
                                  BigDecimal experienceYears, String skills) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(trimBase() + "/spark/salary/predict")
                .queryParam("city", city)
                .queryParam("tech_direction", techDirection)
                .queryParam("education", education)
                .queryParam("experience_years", experienceYears);
        if (StringUtils.hasText(skills)) {
            builder.queryParam("skills", skills.trim());
        }
        return get(builder);
    }

    /**
     * 知识库管理接口。连接失败时返回「AI 服务暂不可用」，不把上游堆栈交给调用方。
     */
    public JsonNode ragDocuments(long current, long size, Integer docType, Integer sourceType, String keyword) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(trimBase() + "/rag/admin/documents")
                .queryParam("current", current)
                .queryParam("size", size);
        if (docType != null) {
            builder.queryParam("doc_type", docType);
        }
        if (sourceType != null) {
            builder.queryParam("source_type", sourceType);
        }
        if (StringUtils.hasText(keyword)) {
            builder.queryParam("q", keyword.trim());
        }
        return exchangeAi(builder.build().encode().toUri(), HttpMethod.GET, new HttpEntity<>(tokenHeaders()));
    }

    public JsonNode ragStats() {
        return exchangeAi(URI.create(trimBase() + "/rag/admin/stats"), HttpMethod.GET, new HttpEntity<>(tokenHeaders()));
    }

    public JsonNode ragUpload(String filename, byte[] bytes, String title, int docType) {
        ByteArrayResource resource = new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        };
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", resource);
        body.add("title", title);
        body.add("doc_type", String.valueOf(docType));
        HttpHeaders headers = tokenHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        return exchangeAi(URI.create(trimBase() + "/rag/admin/upload"), HttpMethod.POST, new HttpEntity<>(body, headers));
    }

    public JsonNode ragReindex(String source, String docKey) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(trimBase() + "/rag/admin/reindex");
        if (StringUtils.hasText(docKey)) {
            builder.queryParam("doc_key", docKey.trim());
        } else if (StringUtils.hasText(source)) {
            builder.queryParam("source", source.trim());
        }
        HttpHeaders headers = tokenHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return exchangeAi(builder.build().encode().toUri(), HttpMethod.POST, new HttpEntity<>("{}", headers));
    }

    public JsonNode ragDelete(String docKey) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(trimBase() + "/rag/admin/documents")
                .queryParam("doc_key", docKey);
        return exchangeAi(builder.build().encode().toUri(), HttpMethod.DELETE, new HttpEntity<>(tokenHeaders()));
    }

    public JsonNode ragSearch(String q, int topK, Integer docType) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(trimBase() + "/rag/search")
                .queryParam("q", q)
                .queryParam("top_k", topK);
        if (docType != null) {
            builder.queryParam("doc_type", docType);
        }
        return exchangeAi(builder.build().encode().toUri(), HttpMethod.GET, new HttpEntity<>(tokenHeaders()));
    }

    private JsonNode post(String path, Object body) {
        try {
            HttpHeaders headers = tokenHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            ResponseEntity<JsonNode> response = sparkRestTemplate.exchange(
                    trimBase() + path, HttpMethod.POST, new HttpEntity<>(body, headers), JsonNode.class);
            return unwrap(response.getBody());
        } catch (HttpStatusCodeException e) {
            throw translate(e);
        } catch (RestClientException e) {
            log.warn("分析服务不可用: {}", e.getMessage());
            throw new BusinessException(503, "分析服务不可用");
        }
    }

    private JsonNode get(UriComponentsBuilder builder) {
        try {
            ResponseEntity<JsonNode> response = sparkRestTemplate.exchange(
                    builder.build().encode().toUri(), HttpMethod.GET, new HttpEntity<>(tokenHeaders()), JsonNode.class);
            return unwrap(response.getBody());
        } catch (HttpStatusCodeException e) {
            throw translate(e);
        } catch (RestClientException e) {
            log.warn("分析服务不可用: {}", e.getMessage());
            throw new BusinessException(503, "分析服务不可用");
        }
    }

    private JsonNode unwrap(JsonNode body) {
        if (body == null || body.isNull()) {
            throw new BusinessException(503, "分析服务不可用");
        }
        int code = body.path("code").asInt(500);
        if (code != 200) {
            throw new BusinessException(code, body.path("msg").asText("分析服务不可用"));
        }
        JsonNode data = body.get("data");
        if (data == null || data.isNull()) {
            return objectMapper.createObjectNode();
        }
        return data;
    }

    private JsonNode exchangeAi(URI uri, HttpMethod method, HttpEntity<?> entity) {
        try {
            ResponseEntity<JsonNode> response = aiRestTemplate.exchange(uri, method, entity, JsonNode.class);
            return unwrapAi(response.getBody());
        } catch (HttpStatusCodeException e) {
            throw translateAi(e);
        } catch (RestClientException e) {
            log.warn("AI 服务不可用: {}", e.getMessage());
            throw new BusinessException(503, "AI 服务暂不可用");
        }
    }

    private JsonNode unwrapAi(JsonNode body) {
        if (body == null || body.isNull()) {
            throw new BusinessException(503, "AI 服务暂不可用");
        }
        int code = body.path("code").asInt(500);
        if (code != 200) {
            int http = code >= 400 && code < 500 ? code : 503;
            throw new BusinessException(http, readableAi(body.path("msg").asText("")));
        }
        JsonNode data = body.get("data");
        if (data == null || data.isNull()) {
            return objectMapper.createObjectNode();
        }
        return data;
    }

    private BusinessException translateAi(HttpStatusCodeException exception) {
        try {
            JsonNode node = objectMapper.readTree(exception.getResponseBodyAsString());
            int code = node.path("code").asInt(exception.getStatusCode().value());
            int http = code >= 400 && code < 500 ? code : 503;
            return new BusinessException(http, readableAi(node.path("msg").asText("")));
        } catch (Exception parseError) {
            log.warn("解析 AI 服务错误响应失败");
            return new BusinessException(503, "AI 服务暂不可用");
        }
    }

    private String readableAi(String msg) {
        if (!StringUtils.hasText(msg)) {
            return "AI 服务暂不可用";
        }
        String text = msg.trim();
        if (text.contains("Traceback") || text.contains("Exception") || text.length() > 200) {
            return "AI 服务处理失败";
        }
        return text;
    }

    private BusinessException translate(HttpStatusCodeException exception) {
        String raw = exception.getResponseBodyAsString();
        try {
            JsonNode node = objectMapper.readTree(raw);
            int code = node.path("code").asInt(exception.getStatusCode().value());
            String msg = node.path("msg").asText("分析服务不可用");
            return new BusinessException(code, msg);
        } catch (Exception parseError) {
            log.warn("解析分析服务错误响应失败: {}", parseError.getMessage());
            return new BusinessException(503, "分析服务不可用");
        }
    }

    private HttpHeaders tokenHeaders() {
        HttpHeaders headers = new HttpHeaders();
        if (StringUtils.hasText(internalToken)) {
            headers.set("X-Internal-Token", internalToken);
        }
        return headers;
    }

    private String trimBase() {
        return baseUrl.replaceAll("/+$", "");
    }
}
