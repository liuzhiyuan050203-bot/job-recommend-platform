package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.dto.CompanyProfileUpdateDTO;
import com.bishe.job.dto.CompanyQualificationDTO;
import com.bishe.job.service.CompanyProfileService;
import com.bishe.job.vo.CompanyProfileVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/company/profile")
@RequiredArgsConstructor
public class CompanyProfileController {

    private final CompanyProfileService companyProfileService;

    @GetMapping
    public Result<CompanyProfileVO> getProfile() {
        return Result.success(companyProfileService.getProfile());
    }

    @PutMapping
    public Result<Void> updateProfile(@Valid @RequestBody CompanyProfileUpdateDTO dto) {
        companyProfileService.updateProfile(dto);
        return Result.success("企业基本资料保存成功", null);
    }

    @PostMapping("/qualification")
    public Result<Void> submitQualification(@Valid @RequestBody CompanyQualificationDTO dto) {
        companyProfileService.submitQualification(dto);
        return Result.success("资质提交成功，请等待管理员审核", null);
    }
}
