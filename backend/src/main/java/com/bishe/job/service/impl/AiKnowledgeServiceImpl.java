package com.bishe.job.service.impl;

import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.BusinessException;
import com.bishe.job.service.AiKnowledgeService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * 知识库管理只做参数检查和转发，索引与向量仍在 ai-service。
 */
@Service
@RequiredArgsConstructor
public class AiKnowledgeServiceImpl implements AiKnowledgeService {

    private static final long MAX_BYTES = 512L * 1024;
    private static final Set<String> SOURCES = Set.of("knowledge", "cms", "jobs", "uploads", "all");

    private final FastApiClient fastApiClient;

    @Override
    public JsonNode documents(long current, long size, Integer docType, Integer sourceType, String keyword) {
        if (docType != null && (docType < 1 || docType > 7)) {
            throw new BusinessException(400, "docType 取值应为 1 到 7");
        }
        if (sourceType != null && (sourceType < 1 || sourceType > 6)) {
            throw new BusinessException(400, "sourceType 取值应为 1 到 6");
        }
        long page = Math.max(current, 1);
        long pageSize = size < 1 ? 10 : Math.min(size, 50);
        return fastApiClient.ragDocuments(page, pageSize, docType, sourceType, keyword);
    }

    @Override
    public JsonNode stats() {
        return fastApiClient.ragStats();
    }

    @Override
    public JsonNode upload(MultipartFile file, String title, Integer docType) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(400, "文件为空");
        }
        if (file.getSize() > MAX_BYTES) {
            throw new BusinessException(400, "文件不能超过 512KB");
        }
        if (docType == null || docType < 1 || docType > 7) {
            throw new BusinessException(400, "docType 取值应为 1 到 7");
        }
        if (!StringUtils.hasText(title)) {
            throw new BusinessException(400, "标题不能为空");
        }
        String filename = safeName(file.getOriginalFilename());
        String lower = filename.toLowerCase(Locale.ROOT);
        if (!lower.endsWith(".md") && !lower.endsWith(".txt")) {
            throw new BusinessException(400, "只支持 .md 或 .txt 文件");
        }
        try {
            return fastApiClient.ragUpload(filename, file.getBytes(), title.trim(), docType);
        } catch (IOException ex) {
            throw new BusinessException(400, "读取上传文件失败");
        }
    }

    @Override
    public JsonNode reindex(String source, String docKey) {
        if (StringUtils.hasText(docKey)) {
            return fastApiClient.ragReindex(null, docKey.trim());
        }
        if (!StringUtils.hasText(source) || !SOURCES.contains(source.trim())) {
            throw new BusinessException(400, "source 应为 knowledge、cms、jobs、uploads 或 all");
        }
        return fastApiClient.ragReindex(source.trim(), null);
    }

    @Override
    public JsonNode delete(String docKey) {
        if (!StringUtils.hasText(docKey)) {
            throw new BusinessException(400, "docKey 不能为空");
        }
        return fastApiClient.ragDelete(docKey.trim());
    }

    @Override
    public JsonNode search(String q, int topK, Integer docType) {
        if (!StringUtils.hasText(q)) {
            throw new BusinessException(400, "检索问题不能为空");
        }
        if (docType != null && (docType < 1 || docType > 7)) {
            throw new BusinessException(400, "docType 取值应为 1 到 7");
        }
        int limit = topK < 1 ? 4 : Math.min(topK, 10);
        return fastApiClient.ragSearch(q.trim(), limit, docType);
    }

    private String safeName(String original) {
        String name = original == null ? "upload.md" : original.replace('\\', '/');
        int slash = name.lastIndexOf('/');
        if (slash >= 0) {
            name = name.substring(slash + 1);
        }
        name = name.trim();
        return name.isEmpty() ? "upload.md" : name;
    }
}
