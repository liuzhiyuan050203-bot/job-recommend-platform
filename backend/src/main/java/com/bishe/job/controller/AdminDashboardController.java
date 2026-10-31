package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.service.AdminDashboardService;
import com.bishe.job.vo.AdminDashboardVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/dashboard")
@RequiredArgsConstructor
public class AdminDashboardController {

    private final AdminDashboardService adminDashboardService;

    @GetMapping("/overview")
    public Result<AdminDashboardVO> overview() {
        return Result.success(adminDashboardService.overview());
    }
}
