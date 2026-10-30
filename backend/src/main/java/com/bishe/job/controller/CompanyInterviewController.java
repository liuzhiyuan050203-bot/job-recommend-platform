package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.InterviewResultDTO;
import com.bishe.job.service.RecruitmentService;
import com.bishe.job.vo.InterviewVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/company/interviews")
@RequiredArgsConstructor
public class CompanyInterviewController {

    private final RecruitmentService recruitmentService;

    @GetMapping
    public Result<PageResult<InterviewVO>> page(
            @RequestParam(value = "interviewStatus", required = false) Integer interviewStatus,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(recruitmentService.companyInterviews(interviewStatus, current, size));
    }

    @PutMapping("/{id}/result")
    public Result<Void> result(@PathVariable("id") Long id, @Valid @RequestBody InterviewResultDTO dto) {
        recruitmentService.saveInterviewResult(id, dto);
        return Result.success("面试结果已记录", null);
    }
}
