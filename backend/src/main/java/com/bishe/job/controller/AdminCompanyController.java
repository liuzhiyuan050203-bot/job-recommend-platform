package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.service.AdminCompanyService;
import com.bishe.job.vo.AdminCompanyVO;
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
@RequestMapping("/api/admin/companies")
@RequiredArgsConstructor
public class AdminCompanyController {

    private final AdminCompanyService adminCompanyService;

    @GetMapping
    public Result<PageResult<AdminCompanyVO>> listCompanies(
            @RequestParam(value = "auditStatus", required = false) Integer auditStatus,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminCompanyService.listCompanies(auditStatus, keyword, current, size));
    }

    @GetMapping("/{id}")
    public Result<AdminCompanyVO> getCompany(@PathVariable("id") Long id) {
        return Result.success(adminCompanyService.getCompany(id));
    }

    @PutMapping("/{id}/audit")
    public Result<Void> auditCompany(@PathVariable("id") Long id,
                                    @Valid @RequestBody AuditDTO dto) {
        adminCompanyService.auditCompany(id, dto);
        return Result.success("企业审核操作成功", null);
    }
}
