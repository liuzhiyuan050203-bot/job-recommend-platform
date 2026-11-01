package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.ApplicationStatusDTO;
import com.bishe.job.dto.InterviewNoticeDTO;
import com.bishe.job.service.RecruitmentService;
import com.bishe.job.service.ResumeFileService;
import com.bishe.job.vo.ApplicationDetailVO;
import com.bishe.job.vo.ApplicationItemVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/company/applications")
@RequiredArgsConstructor
public class CompanyApplicationController {

    private final RecruitmentService recruitmentService;
    private final ResumeFileService resumeFileService;

    @GetMapping
    public Result<PageResult<ApplicationItemVO>> page(
            @RequestParam(value = "jobId", required = false) Long jobId,
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(recruitmentService.companyPage(jobId, status, keyword, current, size));
    }

    @GetMapping("/{id}")
    public Result<ApplicationDetailVO> detail(@PathVariable("id") Long id) {
        return Result.success(recruitmentService.companyDetail(id));
    }

    @PutMapping("/{id}/status")
    public Result<Void> status(@PathVariable("id") Long id, @Valid @RequestBody ApplicationStatusDTO dto) {
        recruitmentService.changeStatus(id, dto);
        return Result.success("投递状态已更新", null);
    }

    @PostMapping("/{id}/interviews")
    public Result<Long> notice(@PathVariable("id") Long id, @Valid @RequestBody InterviewNoticeDTO dto) {
        return Result.success("通知已发送", recruitmentService.sendNotice(id, dto));
    }

    /** 仅投递到本企业职位的简历原件。 */
    @GetMapping("/{id}/resume-file")
    public ResponseEntity<byte[]> resumeFile(@PathVariable("id") Long id) {
        return StudentResumeController.attachment(resumeFileService.downloadForCompany(id));
    }
}
