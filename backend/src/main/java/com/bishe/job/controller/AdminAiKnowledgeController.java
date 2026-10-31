package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.service.AiKnowledgeService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 管理员知识库代理。调用方只带自己的 JWT，内部令牌由服务端附加。
 */
@RestController
@RequestMapping("/api/admin/ai/knowledge")
@RequiredArgsConstructor
public class AdminAiKnowledgeController {

    private final AiKnowledgeService aiKnowledgeService;

    @GetMapping("/documents")
    public Result<JsonNode> documents(
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size,
            @RequestParam(value = "docType", required = false) Integer docType,
            @RequestParam(value = "doc_type", required = false) Integer docTypeSnake,
            @RequestParam(value = "sourceType", required = false) Integer sourceType,
            @RequestParam(value = "source_type", required = false) Integer sourceTypeSnake,
            @RequestParam(value = "q", required = false) String q) {
        return Result.success(aiKnowledgeService.documents(
                current, size, first(docType, docTypeSnake), first(sourceType, sourceTypeSnake), q));
    }

    @GetMapping("/stats")
    public Result<JsonNode> stats() {
        return Result.success(aiKnowledgeService.stats());
    }

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<JsonNode> upload(@RequestParam("file") MultipartFile file,
                                    @RequestParam("title") String title,
                                    @RequestParam(value = "docType", required = false) Integer docType,
                                    @RequestParam(value = "doc_type", required = false) Integer docTypeSnake) {
        return Result.success(aiKnowledgeService.upload(file, title, first(docType, docTypeSnake)));
    }

    @PostMapping("/reindex")
    public Result<JsonNode> reindex(@RequestParam(value = "source", required = false) String source,
                                     @RequestParam(value = "docKey", required = false) String docKey,
                                     @RequestParam(value = "doc_key", required = false) String docKeySnake) {
        String key = hasText(docKey) ? docKey : docKeySnake;
        return Result.success(aiKnowledgeService.reindex(source, key));
    }

    @DeleteMapping("/documents")
    public Result<JsonNode> delete(@RequestParam(value = "docKey", required = false) String docKey,
                                    @RequestParam(value = "doc_key", required = false) String docKeySnake) {
        return Result.success(aiKnowledgeService.delete(hasText(docKey) ? docKey : docKeySnake));
    }

    @GetMapping("/search")
    public Result<JsonNode> search(@RequestParam("q") String q,
                                    @RequestParam(value = "topK", required = false) Integer topK,
                                    @RequestParam(value = "top_k", required = false) Integer topKSnake,
                                    @RequestParam(value = "docType", required = false) Integer docType,
                                    @RequestParam(value = "doc_type", required = false) Integer docTypeSnake) {
        int limit = topK != null ? topK : (topKSnake != null ? topKSnake : 4);
        return Result.success(aiKnowledgeService.search(q, limit, first(docType, docTypeSnake)));
    }

    private Integer first(Integer primary, Integer fallback) {
        return primary != null ? primary : fallback;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
