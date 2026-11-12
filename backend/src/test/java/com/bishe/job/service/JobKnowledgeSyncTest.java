package com.bishe.job.service;

import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.BusinessException;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class JobKnowledgeSyncTest {

    @Test
    void afterChangeSyncsGivenJob() {
        FastApiClient client = mock(FastApiClient.class);
        JobKnowledgeSync sync = new JobKnowledgeSync(client, Runnable::run);
        assertDoesNotThrow(() -> sync.afterChange(42L));
        verify(client).ragSyncJobs(List.of(42L));
    }

    @Test
    void clientFailureIsSwallowed() {
        FastApiClient client = mock(FastApiClient.class);
        when(client.ragSyncJobs(any())).thenThrow(new BusinessException(503, "AI 服务暂不可用"));
        JobKnowledgeSync sync = new JobKnowledgeSync(client, Runnable::run);
        assertDoesNotThrow(() -> sync.afterChange(7L));
        verify(client).ragSyncJobs(List.of(7L));
    }

    @Test
    void nullOrInvalidIdSkipped() {
        FastApiClient client = mock(FastApiClient.class);
        JobKnowledgeSync sync = new JobKnowledgeSync(client, Runnable::run);
        sync.afterChange(null);
        sync.afterChange(0L);
        sync.afterChange(-1L);
        verify(client, never()).ragSyncJobs(any());
    }
}
