package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.service.RecommendService;
import com.bishe.job.vo.RecommendJobVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/student/recommend")
@RequiredArgsConstructor
public class StudentRecommendController {

    private final RecommendService recommendService;

    @GetMapping
    public Result<PageResult<RecommendJobVO>> page(
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(recommendService.pageForCurrentStudent(current, size));
    }
}
