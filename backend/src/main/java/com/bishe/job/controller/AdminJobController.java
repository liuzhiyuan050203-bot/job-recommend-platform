package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.service.AdminJobService;
import com.bishe.job.vo.AdminJobVO;
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
@RequestMapping("/api/admin/jobs")
@RequiredArgsConstructor
public class AdminJobController {

    private final AdminJobService adminJobService;

    @GetMapping
    public Result<PageResult<AdminJobVO>> listJobs(
            @RequestParam(value = "auditStatus", required = false) Integer auditStatus,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminJobService.listJobs(auditStatus, keyword, current, size));
    }

    @PutMapping("/{id}/audit")
    public Result<Void> auditJob(@PathVariable("id") Long id,
                                 @Valid @RequestBody AuditDTO dto) {
        adminJobService.auditJob(id, dto);
        return Result.success("职位审核操作成功", null);
    }
}
