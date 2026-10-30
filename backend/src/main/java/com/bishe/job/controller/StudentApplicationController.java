package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.ApplicationCreateDTO;
import com.bishe.job.service.RecruitmentService;
import com.bishe.job.vo.ApplicationDetailVO;
import com.bishe.job.vo.ApplicationItemVO;
import com.bishe.job.vo.InterviewVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/student")
@RequiredArgsConstructor
public class StudentApplicationController {

    private final RecruitmentService recruitmentService;

    @PostMapping("/applications")
    public Result<Long> apply(@Valid @RequestBody ApplicationCreateDTO dto) {
        return Result.success("投递成功", recruitmentService.apply(dto));
    }

    @GetMapping("/applications")
    public Result<PageResult<ApplicationItemVO>> page(
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(recruitmentService.studentPage(status, current, size));
    }

    @GetMapping("/applications/{id}")
    public Result<ApplicationDetailVO> detail(@PathVariable("id") Long id) {
        return Result.success(recruitmentService.studentDetail(id));
    }

    @GetMapping("/interviews/upcoming")
    public Result<List<InterviewVO>> upcoming() {
        return Result.success(recruitmentService.upcomingInterviews());
    }
}
