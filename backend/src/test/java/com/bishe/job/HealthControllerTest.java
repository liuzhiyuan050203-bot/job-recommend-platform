package com.bishe.job;

import com.bishe.job.client.FastApiClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 健康检查接口。AI 服务的健康探测用 Mock 替身，测试结果不受本机 FastAPI 是否在运行影响。
 */
@SpringBootTest
@AutoConfigureMockMvc
class HealthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private FastApiClient fastApiClient;

    @Test
    void reportsAiDownWhenAiServiceUnavailable() throws Exception {
        when(fastApiClient.checkHealth()).thenReturn("DOWN");
        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.status").value("UP"))
                .andExpect(jsonPath("$.data.db").value("UP"))
                .andExpect(jsonPath("$.data.aiService").value("DOWN"));
    }

    @Test
    void reportsAiUpWhenAiServiceHealthy() throws Exception {
        when(fastApiClient.checkHealth()).thenReturn("UP");
        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("UP"))
                .andExpect(jsonPath("$.data.aiService").value("UP"));
    }
}
