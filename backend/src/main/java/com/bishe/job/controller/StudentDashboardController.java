package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.service.StudentDashboardService;
import com.bishe.job.vo.StudentDashboardVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/student/dashboard")
@RequiredArgsConstructor
public class StudentDashboardController {

    private final StudentDashboardService studentDashboardService;

    @GetMapping
    public Result<StudentDashboardVO> dashboard() {
        return Result.success(studentDashboardService.dashboard());
    }
}
