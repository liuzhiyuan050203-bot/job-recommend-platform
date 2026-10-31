package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.service.RecommendService;
import com.bishe.job.vo.RecommendEvalVO;
import com.bishe.job.vo.RecommendStatsVO;
import com.bishe.job.vo.SparkRunVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/recommend")
@RequiredArgsConstructor
public class AdminRecommendController {

    private final RecommendService recommendService;

    @PostMapping("/run")
    public Result<SparkRunVO> run() {
        return Result.success("推荐任务已提交", recommendService.run());
    }

    @GetMapping("/eval")
    public Result<RecommendEvalVO> evaluation() {
        return Result.success(recommendService.evaluation());
    }

    @GetMapping("/stats")
    public Result<RecommendStatsVO> stats() {
        return Result.success(recommendService.stats());
    }
}
