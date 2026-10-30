package com.bishe.job.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.StuProfile;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.StuProfileMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.vo.CompanyProfileVO;
import com.bishe.job.vo.StudentProfileVO;
import com.bishe.job.vo.UserVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/**
 * 把账号和角色资料组装成对外 VO，不包含密码。
 */
@Component
@RequiredArgsConstructor
public class UserAssembler {

    private final SysUserMapper sysUserMapper;
    private final StuProfileMapper stuProfileMapper;
    private final EntCompanyMapper entCompanyMapper;

    public UserVO toVO(Long userId) {
        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(401, "账号不存在或已被删除");
        }
        UserVO vo = new UserVO();
        vo.setId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setRole(user.getRole());
        vo.setRoleName(RoleCodes.nameOf(user.getRole()));
        vo.setNickname(user.getNickname());
        vo.setPhone(user.getPhone());
        vo.setEmail(user.getEmail());
        vo.setAvatar(user.getAvatar());
        vo.setStatus(user.getStatus());
        vo.setLastLoginTime(user.getLastLoginTime());

        if (Integer.valueOf(RoleCodes.STUDENT).equals(user.getRole())) {
            StuProfile profile = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                    .eq(StuProfile::getUserId, user.getId()));
            vo.setProfile(toProfile(profile));
        } else if (Integer.valueOf(RoleCodes.COMPANY).equals(user.getRole())) {
            EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                    .eq(EntCompany::getUserId, user.getId()));
            vo.setCompany(toCompany(company));
            vo.setCompanyAuditStatus(company == null ? null : company.getAuditStatus());
        }
        return vo;
    }

    private StudentProfileVO toProfile(StuProfile profile) {
        if (profile == null) {
            return null;
        }
        StudentProfileVO vo = new StudentProfileVO();
        vo.setId(profile.getId());
        vo.setUserId(profile.getUserId());
        vo.setRealName(profile.getRealName());
        vo.setGender(profile.getGender());
        vo.setGenderName(genderName(profile.getGender()));
        vo.setBirthday(profile.getBirthday());
        vo.setStudentNo(profile.getStudentNo());
        vo.setSchool(profile.getSchool());
        vo.setCollege(profile.getCollege());
        vo.setMajor(profile.getMajor());
        vo.setEducation(profile.getEducation());
        vo.setEducationName(educationName(profile.getEducation()));
        vo.setGraduationYear(profile.getGraduationYear());
        vo.setExpectCity(profile.getExpectCity());
        vo.setExpectSalaryMin(profile.getExpectSalaryMin());
        vo.setExpectSalaryMax(profile.getExpectSalaryMax());
        vo.setExpectDirection(profile.getExpectDirection());
        vo.setSelfIntro(profile.getSelfIntro());
        return vo;
    }

    private CompanyProfileVO toCompany(EntCompany company) {
        if (company == null) {
            return null;
        }
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

    private String genderName(Integer gender) {
        if (gender == null) {
            return "未知";
        }
        return switch (gender) {
            case 1 -> "男";
            case 2 -> "女";
            default -> "未知";
        };
    }

    private String educationName(Integer education) {
        if (education == null) {
            return null;
        }
        return switch (education) {
            case 1 -> "专科";
            case 2 -> "本科";
            case 3 -> "硕士";
            case 4 -> "博士";
            default -> "未知";
        };
    }
}
