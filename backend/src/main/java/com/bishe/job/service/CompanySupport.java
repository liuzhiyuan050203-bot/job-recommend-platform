package com.bishe.job.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.security.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class CompanySupport {

    private final EntCompanyMapper entCompanyMapper;

    public EntCompany requireCurrent() {
        Long userId = UserContext.require().getId();
        EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                .eq(EntCompany::getUserId, userId));
        if (company == null) {
            throw new BusinessException(403, "企业资料不存在");
        }
        return company;
    }
}
