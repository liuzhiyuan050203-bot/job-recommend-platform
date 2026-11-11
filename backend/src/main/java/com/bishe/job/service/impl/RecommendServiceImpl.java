package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.entity.SparkTaskLog;
import com.bishe.job.mapper.JobQueryMapper;
import com.bishe.job.mapper.RecommendQueryMapper;
import com.bishe.job.mapper.SparkTaskLogMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.PositionTags;
import com.bishe.job.service.RecommendService;
import com.bishe.job.vo.PositionTagVO;
import com.bishe.job.vo.PublicJobVO;
import com.bishe.job.vo.RecommendEvalVO;
import com.bishe.job.vo.RecommendJobVO;
import com.bishe.job.vo.RecommendMetricVO;
import com.bishe.job.vo.RecommendStatsVO;
import com.bishe.job.vo.SimilarJobVO;
import com.bishe.job.vo.SparkRunVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendServiceImpl implements RecommendService {

    private static final int REALTIME_LIMIT = 50;
    private static final int FALLBACK_LIMIT = 40;

    private final RecommendQueryMapper recommendQueryMapper;
    private final JobQueryMapper jobQueryMapper;
    private final SparkTaskLogMapper sparkTaskLogMapper;
    private final PositionTags positionTags;
    private final FastApiClient fastApiClient;
    private final ObjectMapper objectMapper;

    @Override
    public PageResult<RecommendJobVO> pageForCurrentStudent(long current, long size) {
        Long userId = UserContext.require().getId();
        long pageCurrent = Pages.current(current);
        long pageSize = Pages.size(size);
        try {
            if (recommendQueryMapper.countLatest(userId) > 0) {
                Page<RecommendJobVO> page = Pages.of(current, size);
                recommendQueryMapper.pageLatest(page, userId);
                if (page.getTotal() > 0) {
                    fillRecommendTags(page.getRecords());
                    for (RecommendJobVO row : page.getRecords()) {
                        row.setSource("batch");
                    }
                    return PageResult.of(page);
                }
                // 离线结果全部被过滤（已投递/已下架）时继续走实时或兜底
            }
        } catch (Exception ex) {
            log.error("读取离线推荐失败，改走实时或兜底", ex);
        }
        try {
            PageResult<RecommendJobVO> realtime = pageRealtime(userId, pageCurrent, pageSize);
            if (realtime.getTotal() > 0) {
                return realtime;
            }
        } catch (Exception ex) {
            log.warn("实时推荐不可用，改用数据库兜底: {}", ex.getMessage());
        }
        return pageFallback(userId, pageCurrent, pageSize);
    }

    @Override
    public List<SimilarJobVO> similarJobs(Long jobId, long size) {
        PublicJobVO visible = jobQueryMapper.selectVisible(jobId);
        if (visible == null) {
            throw new BusinessException(404, "职位不存在或已下架");
        }
        int limit = (int) size;
        if (limit < 1) {
            limit = 6;
        }
        if (limit > 20) {
            limit = 20;
        }
        List<SimilarJobVO> rows = recommendQueryMapper.similar(jobId, limit);
        double peak = 0;
        for (SimilarJobVO row : rows) {
            if (row.getRawScore() != null) {
                peak = Math.max(peak, row.getRawScore());
            }
        }
        List<Long> ids = new ArrayList<>();
        for (SimilarJobVO row : rows) {
            double raw = row.getRawScore() == null ? 0 : row.getRawScore();
            row.setSimilarity(peak <= 0 ? 0 : round2(raw / peak * 100));
            if (row.getId() != null) {
                ids.add(row.getId());
            }
        }
        Map<Long, List<PositionTagVO>> tags = positionTags.of(ids);
        for (SimilarJobVO row : rows) {
            List<String> names = new ArrayList<>();
            for (PositionTagVO tag : tags.getOrDefault(row.getId(), List.of())) {
                names.add(tag.getTagName());
            }
            row.setTagNames(names);
            row.setSalaryEstimated(PublicJobServiceImpl.isEstimatedSource(row.getSourceCode()));
        }
        return rows;
    }

    @Override
    public SparkRunVO run() {
        JsonNode data = fastApiClient.runRecommend();
        SparkRunVO vo = new SparkRunVO();
        vo.setBatchNo(text(data, "batchNo"));
        vo.setStatus(text(data, "status"));
        List<String> names = new ArrayList<>();
        if (data.path("tasks").isArray()) {
            data.path("tasks").forEach(node -> names.add(node.asText()));
        }
        vo.setTasks(names);
        if (!StringUtils.hasText(vo.getBatchNo())) {
            throw new BusinessException(503, "分析服务不可用");
        }
        return vo;
    }

    @Override
    public RecommendEvalVO evaluation() {
        RecommendEvalVO vo = new RecommendEvalVO();
        List<RecommendMetricVO> metrics = recommendQueryMapper.latestEval();
        vo.setMetrics(metrics == null ? List.of() : metrics);
        if (metrics != null && !metrics.isEmpty()) {
            RecommendMetricVO first = metrics.get(0);
            vo.setBatchNo(first.getBatchNo());
            vo.setCfMethod(first.getCfMethod());
            for (RecommendMetricVO metric : metrics) {
                if ("hybrid".equals(metric.getAlgo()) && metric.getAlpha() != null) {
                    vo.setAlpha(metric.getAlpha());
                    break;
                }
            }
        }
        SparkTaskLog task = latestRecommendTask();
        if (task != null && StringUtils.hasText(task.getParamsJson())) {
            try {
                JsonNode params = objectMapper.readTree(task.getParamsJson());
                if (!StringUtils.hasText(vo.getBatchNo())) {
                    vo.setBatchNo(text(params, "batchNo"));
                }
                if (!StringUtils.hasText(vo.getCfMethod())) {
                    vo.setCfMethod(text(params, "cfMethod"));
                }
                if (vo.getAlpha() == null && params.hasNonNull("alpha")) {
                    vo.setAlpha(BigDecimal.valueOf(params.get("alpha").asDouble()).setScale(4, RoundingMode.HALF_UP));
                }
                vo.setFusion(text(params, "fusion"));
                if (params.has("adaptiveAlpha") && !params.get("adaptiveAlpha").isNull()) {
                    vo.setAdaptiveAlpha(params.get("adaptiveAlpha").asBoolean());
                }
                if (params.hasNonNull("halfLifeDays")) {
                    vo.setHalfLifeDays(params.get("halfLifeDays").asInt());
                }
                vo.setSummary(text(params, "cfChoiceReason"));
                if (params.hasNonNull("cosineNdcg10")) {
                    vo.setCosineNdcg10(BigDecimal.valueOf(params.get("cosineNdcg10").asDouble()).setScale(4, RoundingMode.HALF_UP));
                }
                if (params.hasNonNull("alsNdcg10")) {
                    vo.setAlsNdcg10(BigDecimal.valueOf(params.get("alsNdcg10").asDouble()).setScale(4, RoundingMode.HALF_UP));
                }
            } catch (Exception ex) {
                log.warn("解析推荐任务参数失败: {}", ex.getMessage());
            }
        }
        if (vo.getHalfLifeDays() == null) {
            vo.setHalfLifeDays(45);
        }
        return vo;
    }

    @Override
    public RecommendStatsVO stats() {
        RecommendStatsVO vo = recommendQueryMapper.latestStats();
        if (vo == null) {
            vo = new RecommendStatsVO();
        }
        if (vo.getUserCount() == null) {
            vo.setUserCount(0L);
        }
        if (vo.getRecommendCount() == null) {
            vo.setRecommendCount(0L);
        }
        if (vo.getPositionCount() == null) {
            vo.setPositionCount(0L);
        }
        int catalog = recommendQueryMapper.countVisibleJobs();
        vo.setCatalogSize((long) catalog);
        if (catalog > 0) {
            vo.setCoverage(BigDecimal.valueOf(vo.getPositionCount())
                    .divide(BigDecimal.valueOf(catalog), 4, RoundingMode.HALF_UP));
        } else {
            vo.setCoverage(BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP));
        }
        RecommendEvalVO eval = evaluation();
        if (!StringUtils.hasText(vo.getBatchNo())) {
            vo.setBatchNo(eval.getBatchNo());
        }
        vo.setCfMethod(eval.getCfMethod());
        vo.setAlpha(eval.getAlpha());
        return vo;
    }

    private PageResult<RecommendJobVO> pageRealtime(Long userId, long current, long size) {
        JsonNode data = fastApiClient.recommendUser(userId, REALTIME_LIMIT);
        List<RecommendJobVO> all = new ArrayList<>();
        if (data.path("items").isArray()) {
            int rank = 1;
            for (JsonNode node : data.path("items")) {
                RecommendJobVO vo = fromNode(node);
                if (vo.getPositionId() == null || vo.getPositionId() <= 0) {
                    continue;
                }
                if (vo.getRankNo() == null) {
                    vo.setRankNo(rank);
                }
                vo.setSource("realtime");
                all.add(vo);
                rank++;
            }
        }
        return slice(all, current, size);
    }

    private PageResult<RecommendJobVO> pageFallback(Long userId, long current, long size) {
        try {
            List<RecommendJobVO> rows = recommendQueryMapper.fallback(userId, FALLBACK_LIMIT);
            double peak = 0;
            for (RecommendJobVO row : rows) {
                if (row.getRawScore() != null) {
                    peak = Math.max(peak, row.getRawScore());
                }
            }
            int rank = 1;
            for (RecommendJobVO row : rows) {
                double raw = row.getRawScore() == null ? 0 : row.getRawScore();
                BigDecimal score = BigDecimal.valueOf(peak <= 0 ? 0 : raw / peak * 100)
                        .setScale(2, RoundingMode.HALF_UP);
                if (score.compareTo(BigDecimal.valueOf(100)) > 0) {
                    score = new BigDecimal("100.00");
                }
                row.setMatchScore(score);
                row.setContentScore(score);
                row.setCfScore(BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP));
                row.setRankNo(rank++);
                row.setReason(fallbackReason(row));
                row.setSource("fallback");
            }
            fillRecommendTags(rows);
            return slice(rows, current, size);
        } catch (Exception ex) {
            log.error("推荐兜底查询失败", ex);
            return PageResult.empty(current, size);
        }
    }

    private String fallbackReason(RecommendJobVO row) {
        List<String> parts = new ArrayList<>();
        if (StringUtils.hasText(row.getSkillNames())) {
            String[] names = row.getSkillNames().split("/");
            String shown = String.join("/", Arrays.copyOf(names, Math.min(3, names.length)));
            parts.add("与你的 " + shown + " 技能匹配");
        }
        if (Integer.valueOf(1).equals(row.getDirectionHit()) && StringUtils.hasText(row.getExpectDirection())) {
            parts.add("符合你期望的" + row.getExpectDirection() + "方向");
        }
        if (Integer.valueOf(1).equals(row.getCityHit()) && StringUtils.hasText(row.getExpectCity())) {
            parts.add("位于你期望的城市" + row.getExpectCity());
        }
        if (parts.isEmpty()) {
            int applyCount = row.getApplyCount() == null ? 0 : row.getApplyCount();
            parts.add(applyCount >= 3 ? "热门职位" : "综合你的技能与求职意向推荐");
        }
        String text = String.join("；", parts);
        if (text.length() > 255) {
            return text.substring(0, 252) + "...";
        }
        return text;
    }

    private void fillRecommendTags(List<RecommendJobVO> records) {
        if (records == null || records.isEmpty()) {
            return;
        }
        List<Long> ids = records.stream().map(RecommendJobVO::getPositionId).filter(Objects::nonNull).distinct().toList();
        Map<Long, List<PositionTagVO>> tags = positionTags.of(ids);
        for (RecommendJobVO row : records) {
            List<String> names = new ArrayList<>();
            for (PositionTagVO tag : tags.getOrDefault(row.getPositionId(), List.of())) {
                if (StringUtils.hasText(tag.getTagName())) {
                    names.add(tag.getTagName());
                }
            }
            row.setTagNames(names);
        }
    }

    private RecommendJobVO fromNode(JsonNode node) {
        RecommendJobVO vo = new RecommendJobVO();
        vo.setPositionId(node.path("positionId").asLong(0));
        vo.setTitle(node.path("title").asText(""));
        vo.setCompanyName(node.path("companyName").asText(""));
        vo.setCity(node.path("city").asText(""));
        vo.setProvince(node.path("province").asText(""));
        vo.setTechDirection(node.path("techDirection").asText(""));
        vo.setSalaryMin(node.path("salaryMin").isNumber() ? node.path("salaryMin").asInt() : null);
        vo.setSalaryMax(node.path("salaryMax").isNumber() ? node.path("salaryMax").asInt() : null);
        vo.setSalaryMonths(node.path("salaryMonths").isNumber() ? node.path("salaryMonths").asInt() : null);
        vo.setEducation(node.path("education").isNumber() ? node.path("education").asInt() : null);
        vo.setMatchScore(decimal(node, "matchScore"));
        vo.setCfScore(decimal(node, "cfScore"));
        vo.setContentScore(decimal(node, "contentScore"));
        if (node.path("rankNo").isNumber()) {
            vo.setRankNo(node.path("rankNo").asInt());
        }
        vo.setReason(node.path("reason").asText(""));
        if (node.path("tagNames").isArray()) {
            List<String> tags = new ArrayList<>();
            node.path("tagNames").forEach(item -> {
                if (StringUtils.hasText(item.asText())) {
                    tags.add(item.asText());
                }
            });
            vo.setTagNames(tags);
        }
        return vo;
    }

    private PageResult<RecommendJobVO> slice(List<RecommendJobVO> all, long current, long size) {
        int from = (int) ((current - 1) * size);
        if (from >= all.size()) {
            return new PageResult<>(List.of(), all.size(), current, size);
        }
        int to = (int) Math.min(all.size(), from + size);
        return new PageResult<>(new ArrayList<>(all.subList(from, to)), all.size(), current, size);
    }

    private SparkTaskLog latestRecommendTask() {
        return sparkTaskLogMapper.selectOne(new LambdaQueryWrapper<SparkTaskLog>()
                .eq(SparkTaskLog::getTaskCode, "recommend")
                .eq(SparkTaskLog::getStatus, 1)
                .orderByDesc(SparkTaskLog::getId)
                .last("LIMIT 1"));
    }

    private BigDecimal decimal(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull() || !value.isNumber()) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        BigDecimal score = BigDecimal.valueOf(value.asDouble()).setScale(2, RoundingMode.HALF_UP);
        if (score.compareTo(BigDecimal.ZERO) < 0) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        if (score.compareTo(new BigDecimal("100")) > 0) {
            return new BigDecimal("100.00");
        }
        return score;
    }

    private double round2(double value) {
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP).doubleValue();
    }

    private String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            return null;
        }
        String text = value.asText();
        return StringUtils.hasText(text) ? text : null;
    }
}
