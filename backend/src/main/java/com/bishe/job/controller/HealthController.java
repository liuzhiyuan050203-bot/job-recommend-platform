package com.bishe.job.controller;

import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.Result;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.LinkedHashMap;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class HealthController {

    private final DataSource dataSource;
    private final FastApiClient fastApiClient;

    @GetMapping("/health")
    public Result<Map<String, Object>> health() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("status", "UP");

        String dbStatus = "DOWN";
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement("SELECT 1");
             ResultSet rs = ps.executeQuery()) {
            if (rs.next()) {
                dbStatus = "UP";
            }
        } catch (Exception e) {
            log.warn("数据库健康检查失败: {}", e.getMessage());
        }
        data.put("db", dbStatus);

        String aiStatus = fastApiClient.checkHealth();
        data.put("aiService", aiStatus);

        return Result.success(data);
    }
}
