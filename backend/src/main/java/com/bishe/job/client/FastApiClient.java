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
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Component
public class FastApiClient {

    private final RestTemplate restTemplate;
    private final RestTemplate sparkRestTemplate;
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
