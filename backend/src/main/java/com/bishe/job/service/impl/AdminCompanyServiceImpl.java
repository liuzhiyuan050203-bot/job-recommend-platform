package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.AdminCompanyService;
import com.bishe.job.vo.AdminCompanyVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminCompanyServiceImpl implements AdminCompanyService {

    private final EntCompanyMapper entCompanyMapper;
    private final SysUserMapper sysUserMapper;

    @Override
    public PageResult<AdminCompanyVO> listCompanies(Integer auditStatus, String keyword, long current, long size) {
        Page<EntCompany> page = Pages.of(current, size);
        LambdaQueryWrapper<EntCompany> wrapper = new LambdaQueryWrapper<>();

        if (auditStatus != null) {
            wrapper.eq(EntCompany::getAuditStatus, auditStatus);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.and(w -> w.like(EntCompany::getCompanyName, kw)
                    .or().like(EntCompany::getShortName, kw)
                    .or().like(EntCompany::getCreditCode, kw)
                    .or().like(EntCompany::getContactName, kw));
        }

        // 待审核 (0) 优先显示
        wrapper.orderByAsc(EntCompany::getAuditStatus)
                .orderByDesc(EntCompany::getUpdateTime)
                .orderByDesc(EntCompany::getId);

        entCompanyMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<Long> userIds = page.getRecords().stream().map(EntCompany::getUserId).distinct().toList();
        Map<Long, SysUser> userMap = sysUserMapper.selectBatchIds(userIds).stream()
                .collect(Collectors.toMap(SysUser::getId, u -> u));

        List<AdminCompanyVO> list = page.getRecords().stream().map(c -> {
            AdminCompanyVO vo = toVO(c);
            SysUser u = userMap.get(c.getUserId());
            if (u != null) {
                vo.setUsername(u.getUsername());
            }
            return vo;
        }).toList();

        return PageResult.of(page, list);
    }

    @Override
    public AdminCompanyVO getCompany(Long id) {
        EntCompany company = entCompanyMapper.selectById(id);
        if (company == null) {
            throw new BusinessException(404, "企业不存在");
        }
        AdminCompanyVO vo = toVO(company);
        SysUser user = sysUserMapper.selectById(company.getUserId());
        if (user != null) {
            vo.setUsername(user.getUsername());
        }
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void auditCompany(Long id, AuditDTO dto) {
        Long adminId = UserContext.get().getId();
        EntCompany company = entCompanyMapper.selectById(id);
        if (company == null) {
            throw new BusinessException(404, "企业不存在");
        }

        company.setAuditStatus(dto.getAuditStatus());
        company.setAuditRemark(dto.getAuditRemark());
        company.setAuditTime(LocalDateTime.now());
        company.setAuditorId(adminId);

        entCompanyMapper.updateById(company);
    }

    private AdminCompanyVO toVO(EntCompany company) {
        AdminCompanyVO vo = new AdminCompanyVO();
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
        vo.setAuditorId(company.getAuditorId());
        vo.setCreateTime(company.getCreateTime());
        return vo;
    }
}
