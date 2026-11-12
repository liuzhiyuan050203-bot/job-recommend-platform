package com.bishe.job.service;

import com.bishe.job.client.FastApiClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 职位发布、审核、上下架或删除后，把变更异步同步到 AI 知识库。
 * 在事务提交之后才调用，失败只记日志，不影响职位业务操作。
 */
@Slf4j
@Service
public class JobKnowledgeSync {

    private final FastApiClient fastApiClient;
    private final Executor executor;

    @Autowired
    public JobKnowledgeSync(FastApiClient fastApiClient) {
        this(fastApiClient, defaultExecutor());
    }

    JobKnowledgeSync(FastApiClient fastApiClient, Executor executor) {
        this.fastApiClient = fastApiClient;
        this.executor = executor;
    }

    private static Executor defaultExecutor() {
        AtomicInteger seq = new AtomicInteger();
        ThreadFactory factory = runnable -> {
            Thread thread = new Thread(runnable, "job-kb-sync-" + seq.incrementAndGet());
            thread.setDaemon(true);
            return thread;
        };
        return Executors.newFixedThreadPool(2, factory);
    }

    /**
     * 事务提交后异步同步该职位；无事务时立即提交到后台线程。
     */
    public void afterChange(Long jobId) {
        if (jobId == null || jobId <= 0) {
            return;
        }
        Runnable task = () -> syncQuietly(jobId);
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    submit(task);
                }
            });
            return;
        }
        submit(task);
    }

    private void submit(Runnable task) {
        try {
            executor.execute(task);
        } catch (Exception ex) {
            log.warn("知识库同步任务提交失败（不影响职位操作）: {}", ex.getMessage());
        }
    }

    void syncQuietly(Long jobId) {
        try {
            fastApiClient.ragSyncJobs(List.of(jobId));
        } catch (Exception ex) {
            log.warn("知识库同步职位 {} 失败（不影响职位操作）: {}", jobId, ex.getMessage());
        }
    }
}
