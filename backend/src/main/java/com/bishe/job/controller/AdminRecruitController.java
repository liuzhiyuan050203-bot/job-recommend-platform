package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.service.RecruitmentService;
import com.bishe.job.vo.AdminOverviewVO;
import com.bishe.job.vo.ApplicationItemVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminRecruitController {

    private final RecruitmentService recruitmentService;

    @GetMapping("/overview")
    public Result<AdminOverviewVO> overview() {
        return Result.success(recruitmentService.overview());
    }

    @GetMapping("/applications")
    public Result<PageResult<ApplicationItemVO>> applications(
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "companyId", required = false) Long companyId,
            @RequestParam(value = "jobId", required = false) Long jobId,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(recruitmentService.adminPage(status, companyId, jobId, keyword, current, size));
    }
}
