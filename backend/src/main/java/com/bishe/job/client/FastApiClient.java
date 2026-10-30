package com.bishe.job.client;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Slf4j
@Component
public class FastApiClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public FastApiClient(RestTemplate restTemplate,
                         @Value("${fastapi.base-url:http://localhost:8000}") String baseUrl) {
        this.restTemplate = restTemplate;
        this.baseUrl = baseUrl;
    }

    /**
     * 检查 FastAPI 服务健康状态
     * 发生异常时返回 "DOWN"，不向外抛出异常
     *
     * @return "UP" 或 "DOWN"
     */
    public String checkHealth() {
        try {
            String url = baseUrl.replaceAll("/+$", "") + "/health";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            if (response.getStatusCode().is2xxSuccessful()) {
                return "UP";
            }
            return "DOWN";
        } catch (Exception e) {
            log.warn("FastAPI 健康检查失败: {}", e.getMessage());
            return "DOWN";
        }
    }
}
