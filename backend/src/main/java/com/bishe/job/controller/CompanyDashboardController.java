package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.service.CompanyDashboardService;
import com.bishe.job.vo.CompanyDashboardVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/company/dashboard")
@RequiredArgsConstructor
public class CompanyDashboardController {

    private final CompanyDashboardService companyDashboardService;

    @GetMapping
    public Result<CompanyDashboardVO> dashboard() {
        return Result.success(companyDashboardService.dashboard());
    }
}
