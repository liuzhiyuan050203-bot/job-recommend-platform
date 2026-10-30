package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.JobSaveDTO;
import com.bishe.job.dto.JobShelfDTO;
import com.bishe.job.service.CompanyJobService;
import com.bishe.job.vo.CompanyJobVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/company/jobs")
@RequiredArgsConstructor
public class CompanyJobController {

    private final CompanyJobService companyJobService;

    @GetMapping
    public Result<PageResult<CompanyJobVO>> page(
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(companyJobService.page(current, size));
    }

    @GetMapping("/{id}")
    public Result<CompanyJobVO> detail(@PathVariable("id") Long id) {
        return Result.success(companyJobService.detail(id));
    }

    @PostMapping
    public Result<CompanyJobVO> create(@Valid @RequestBody JobSaveDTO dto) {
        return Result.success("职位已提交，等待审核", companyJobService.create(dto));
    }

    @PutMapping("/{id}")
    public Result<CompanyJobVO> update(@PathVariable("id") Long id, @Valid @RequestBody JobSaveDTO dto) {
        return Result.success("职位已更新，需重新审核", companyJobService.update(id, dto));
    }

    @PutMapping("/{id}/shelf")
    public Result<Void> shelf(@PathVariable("id") Long id, @Valid @RequestBody JobShelfDTO dto) {
        companyJobService.shelf(id, dto);
        return Result.success("上下架状态已更新", null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable("id") Long id) {
        companyJobService.delete(id);
        return Result.success("职位已删除", null);
    }
}
