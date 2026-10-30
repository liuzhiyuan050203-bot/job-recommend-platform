package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.dto.CompanyProfileUpdateDTO;
import com.bishe.job.dto.CompanyQualificationDTO;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.CompanyProfileService;
import com.bishe.job.vo.CompanyProfileVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Slf4j
@Service
@RequiredArgsConstructor
public class CompanyProfileServiceImpl implements CompanyProfileService {

    private final EntCompanyMapper entCompanyMapper;
    private final SysUserMapper sysUserMapper;

    @Override
    public CompanyProfileVO getProfile() {
        Long userId = UserContext.get().getId();
        EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                .eq(EntCompany::getUserId, userId));
        if (company == null) {
            CompanyProfileVO vo = new CompanyProfileVO();
            vo.setUserId(userId);
            vo.setAuditStatus(0);
            return vo;
        }
        return toVO(company);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateProfile(CompanyProfileUpdateDTO dto) {
        Long userId = UserContext.get().getId();
        EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                .eq(EntCompany::getUserId, userId));
        if (company == null) {
            throw new BusinessException(404, "企业信息不存在");
        }

        if (StringUtils.hasText(dto.getCompanyName())) {
            company.setCompanyName(dto.getCompanyName().trim());
        }
        company.setShortName(dto.getShortName());
        company.setLogoUrl(dto.getLogoUrl());
        company.setIndustry(dto.getIndustry());
        company.setScale(dto.getScale() != null ? dto.getScale() : 0);
        company.setProvince(dto.getProvince());
        company.setCity(dto.getCity());
        company.setAddress(dto.getAddress());
        company.setWebsite(dto.getWebsite());
        company.setIntro(dto.getIntro());
        company.setContactName(dto.getContactName());
        company.setContactPhone(dto.getContactPhone());
        company.setContactEmail(dto.getContactEmail());

        entCompanyMapper.updateById(company);

        // 同步更新 sys_user 昵称
        SysUser user = sysUserMapper.selectById(userId);
        if (user != null && StringUtils.hasText(company.getCompanyName())) {
            user.setNickname(company.getCompanyName());
            sysUserMapper.updateById(user);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void submitQualification(CompanyQualificationDTO dto) {
        Long userId = UserContext.get().getId();
        EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                .eq(EntCompany::getUserId, userId));
        if (company == null) {
            throw new BusinessException(404, "企业信息不存在");
        }

        String creditCode = dto.getCreditCode().trim();
        // 校验统一社会信用代码是否已被其他企业使用
        EntCompany existingWithCode = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                .eq(EntCompany::getCreditCode, creditCode)
                .ne(EntCompany::getId, company.getId()));
        if (existingWithCode != null) {
            throw new BusinessException(400, "该统一社会信用代码已被其他企业绑定");
        }

        if (StringUtils.hasText(dto.getCompanyName())) {
            company.setCompanyName(dto.getCompanyName().trim());
        }
        company.setCreditCode(creditCode);
        company.setLicenseUrl(dto.getLicenseUrl().trim());
        company.setAuditStatus(0); // 重新置为 0 待审核
        company.setAuditRemark("资质材料已提交，等待管理员审核");
        company.setAuditTime(null);
        company.setAuditorId(null);

        entCompanyMapper.updateById(company);
    }

    private CompanyProfileVO toVO(EntCompany company) {
        CompanyProfileVO vo = new CompanyProfileVO();
        vo.setId(company.getId());
        vo.setUserId(company.getUserId());
        vo.setCompanyName(company.getCompanyName());
        vo.setShortName(company.getShortName());
        vo.setLogoUrl(company.getLogoUrl());
        vo.setIndustry(company.getIndustry());
        vo.setScale(company.getScale());
        vo.setProvince(company.getProvince());
        vo.setCity(company.getCity());
        vo.setAddress(company.getAddress());
        vo.setWebsite(company.getWebsite());
        vo.setIntro(company.getIntro());
        vo.setCreditCode(company.getCreditCode());
        vo.setLicenseUrl(company.getLicenseUrl());
        vo.setContactName(company.getContactName());
        vo.setContactPhone(company.getContactPhone());
        vo.setContactEmail(company.getContactEmail());
        vo.setAuditStatus(company.getAuditStatus());
        vo.setAuditRemark(company.getAuditRemark());
        vo.setAuditTime(company.getAuditTime());
        return vo;
    }
}
