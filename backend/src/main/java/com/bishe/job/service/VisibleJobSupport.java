package com.bishe.job.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.JobPositionMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/**
 * 学生侧可见职位：审核通过、已上架，且企业资质已通过。
 */
@Component
@RequiredArgsConstructor
public class VisibleJobSupport {

    private final JobPositionMapper jobPositionMapper;
    private final EntCompanyMapper entCompanyMapper;

    public JobPosition require(Long jobId) {
        JobPosition job = jobId == null ? null : jobPositionMapper.selectById(jobId);
        if (job == null
                || !Integer.valueOf(1).equals(job.getAuditStatus())
                || !Integer.valueOf(1).equals(job.getShelfStatus())) {
            throw new BusinessException(404, "职位不存在或已下架");
        }
        EntCompany company = entCompanyMapper.selectById(job.getCompanyId());
        if (company == null || !Integer.valueOf(1).equals(company.getAuditStatus())) {
            throw new BusinessException(404, "职位不存在或已下架");
        }
        return job;
    }
}
