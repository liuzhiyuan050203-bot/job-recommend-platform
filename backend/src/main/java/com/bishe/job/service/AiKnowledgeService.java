package com.bishe.job.service;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;
import org.springframework.web.multipart.MultipartFile;

/**
 * 管理员知识库，转发到 ai-service /rag/admin 与 /rag/search。
 */
public interface AiKnowledgeService {

    JsonNode documents(long current, long size, Integer docType, Integer sourceType, String keyword);

    JsonNode stats();

    JsonNode upload(MultipartFile file, String title, Integer docType);

    JsonNode reindex(String source, String docKey);

    JsonNode delete(String docKey);

    JsonNode search(String q, int topK, Integer docType);

    JsonNode syncJobs(List<Long> jobIds);
}
