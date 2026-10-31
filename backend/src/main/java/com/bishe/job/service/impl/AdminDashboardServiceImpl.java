package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.entity.SparkTaskLog;
import com.bishe.job.mapper.SparkTaskLogMapper;
import com.bishe.job.mapper.StatsQueryMapper;
import com.bishe.job.service.AdminDashboardService;
import com.bishe.job.service.PublicStatsService;
import com.bishe.job.service.RecommendService;
import com.bishe.job.vo.AdminDashboardVO;
import com.bishe.job.vo.RecommendEvalVO;
import com.bishe.job.vo.RecommendMetricVO;
import com.bishe.job.vo.RecommendStatsVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AdminDashboardServiceImpl implements AdminDashboardService {

    private final PublicStatsService publicStatsService;
    private final RecommendService recommendService;
    private final SparkTaskLogMapper sparkTaskLogMapper;
    private final StatsQueryMapper statsQueryMapper;

    @Override
    public AdminDashboardVO overview() {
        AdminDashboardVO vo = new AdminDashboardVO();
        vo.setPlatform(publicStatsService.overview());
        vo.setSpark(latestSpark());
        vo.setRecommend(recommendBrief());
        AdminDashboardVO.AiUsage ai = new AdminDashboardVO.AiUsage();
        ai.setSessionCount(statsQueryMapper.countAiSessions());
        ai.setMessageCount(statsQueryMapper.countAiMessages());
        vo.setAi(ai);
        return vo;
    }

    private AdminDashboardVO.SparkBrief latestSpark() {
        AdminDashboardVO.SparkBrief brief = new AdminDashboardVO.SparkBrief();
        Page<SparkTaskLog> page = new Page<>(1, 1);
        sparkTaskLogMapper.selectPage(page, new LambdaQueryWrapper<SparkTaskLog>()
                .eq(SparkTaskLog::getStatus, 1)
                .orderByDesc(SparkTaskLog::getId));
        if (page.getRecords().isEmpty()) {
            return brief;
        }
        SparkTaskLog latest = page.getRecords().get(0);
        brief.setBatchNo(latest.getBatchNo());
        brief.setTaskCode(latest.getTaskCode());
        brief.setTaskName(latest.getTaskName());
        brief.setStatus(latest.getStatus());
        brief.setEndTime(latest.getEndTime() != null ? latest.getEndTime() : latest.getStartTime());
        return brief;
    }

    private AdminDashboardVO.RecommendBrief recommendBrief() {
        AdminDashboardVO.RecommendBrief brief = new AdminDashboardVO.RecommendBrief();
        RecommendStatsVO stats = recommendService.stats();
        RecommendEvalVO eval = recommendService.evaluation();
        if (stats != null) {
            brief.setBatchNo(stats.getBatchNo());
            brief.setCoverage(stats.getCoverage());
            brief.setUserCount(stats.getUserCount());
            brief.setRecommendCount(stats.getRecommendCount());
            brief.setCfMethod(stats.getCfMethod());
            brief.setAlpha(stats.getAlpha());
        }
        if (eval != null) {
            if (brief.getBatchNo() == null) {
                brief.setBatchNo(eval.getBatchNo());
            }
            if (brief.getCfMethod() == null) {
                brief.setCfMethod(eval.getCfMethod());
            }
            if (brief.getAlpha() == null) {
                brief.setAlpha(eval.getAlpha());
            }
            brief.setNdcgAt10(ndcgAt10(eval));
        }
        return brief;
    }

    private java.math.BigDecimal ndcgAt10(RecommendEvalVO eval) {
        if (eval.getMetrics() != null) {
            for (RecommendMetricVO metric : eval.getMetrics()) {
                if (metric == null || metric.getK() == null || metric.getK() != 10) {
                    continue;
                }
                if ("hybrid".equals(metric.getAlgo()) && metric.getNdcgAtK() != null) {
                    return metric.getNdcgAtK();
                }
            }
        }
        if (eval.getAlsNdcg10() != null) {
            return eval.getAlsNdcg10();
        }
        return eval.getCosineNdcg10();
    }
}
