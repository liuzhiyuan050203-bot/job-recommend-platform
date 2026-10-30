package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.BusinessException;
import com.bishe.job.dto.CompanyRegisterRequest;
import com.bishe.job.dto.LoginRequest;
import com.bishe.job.dto.StudentRegisterRequest;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.StuProfile;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.StuProfileMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.AccountStatus;
import com.bishe.job.security.JwtUtil;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.service.AuthService;
import com.bishe.job.service.UserAssembler;
import com.bishe.job.vo.LoginVO;
import com.bishe.job.vo.UserVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private static final Pattern EMAIL = Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    private static final Pattern PHONE = Pattern.compile("^1\\d{10}$");

    private final SysUserMapper sysUserMapper;
    private final StuProfileMapper stuProfileMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final UserAssembler userAssembler;

    @Override
    public LoginVO login(LoginRequest request) {
        String username = request.getUsername().trim();
        SysUser user = sysUserMapper.selectOne(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getUsername, username));
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BusinessException(400, "用户名或密码错误");
        }
        if (!AccountStatus.isActive(user.getStatus())) {
            throw new BusinessException(400, AccountStatus.denyMessage(user.getStatus()));
        }

        LocalDateTime now = LocalDateTime.now();
        SysUser patch = new SysUser();
        patch.setId(user.getId());
        patch.setLastLoginTime(now);
        sysUserMapper.updateById(patch);

        LoginVO vo = new LoginVO();
        vo.setToken(jwtUtil.createToken(user.getId(), user.getUsername(), user.getRole()));
        vo.setUser(userAssembler.toVO(user.getId()));
        log.info("用户登录成功: {}", user.getUsername());
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public UserVO registerStudent(StudentRegisterRequest request) {
        String username = request.getUsername().trim();
        assertUsernameAvailable(username);
        String phone = normalizePhone(request.getPhone());
        String email = normalizeEmail(request.getEmail());
        String studentNo = blankToNull(request.getStudentNo());
        if (studentNo != null) {
            Long count = stuProfileMapper.selectCount(new LambdaQueryWrapper<StuProfile>()
                    .eq(StuProfile::getStudentNo, studentNo));
            if (count != null && count > 0) {
                throw new BusinessException(400, "学号已存在");
            }
        }

        SysUser user = new SysUser();
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole(RoleCodes.STUDENT);
        user.setNickname(request.getNickname().trim());
        user.setPhone(phone);
        user.setEmail(email);
        user.setStatus(AccountStatus.ACTIVE);
        user.setDeleted(0);
        try {
            sysUserMapper.insert(user);
            StuProfile profile = new StuProfile();
            profile.setUserId(user.getId());
            profile.setRealName(request.getRealName().trim());
            profile.setGender(request.getGender() == null ? 0 : request.getGender());
            profile.setStudentNo(studentNo);
            profile.setSchool(blankToNull(request.getSchool()));
            profile.setCollege(blankToNull(request.getCollege()));
            profile.setMajor(blankToNull(request.getMajor()));
            profile.setEducation(request.getEducation());
            profile.setGraduationYear(request.getGraduationYear());
            profile.setExpectCity(blankToNull(request.getExpectCity()));
            profile.setExpectDirection(blankToNull(request.getExpectDirection()));
            profile.setDeleted(0);
            stuProfileMapper.insert(profile);
        } catch (DuplicateKeyException e) {
            throw translateDuplicate(e);
        }
        log.info("学生注册成功: {}", username);
        return userAssembler.toVO(user.getId());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public UserVO registerCompany(CompanyRegisterRequest request) {
        String username = request.getUsername().trim();
        assertUsernameAvailable(username);
        String creditCode = request.getCreditCode().trim().toUpperCase();
        Long creditCount = entCompanyMapper.selectCount(new LambdaQueryWrapper<EntCompany>()
                .eq(EntCompany::getCreditCode, creditCode));
        if (creditCount != null && creditCount > 0) {
            throw new BusinessException(400, "统一社会信用代码已存在");
        }
        String phone = normalizePhone(request.getContactPhone());
        String email = normalizeEmail(request.getContactEmail());
        String nickname = blankToNull(request.getNickname());
        if (nickname == null) {
            nickname = request.getCompanyName().trim();
        }
        if (nickname.length() > 64) {
            nickname = nickname.substring(0, 64);
        }

        SysUser user = new SysUser();
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole(RoleCodes.COMPANY);
        user.setNickname(nickname);
        user.setPhone(phone);
        user.setEmail(email);
        user.setStatus(AccountStatus.ACTIVE);
        user.setDeleted(0);
        try {
            sysUserMapper.insert(user);
            EntCompany company = new EntCompany();
            company.setUserId(user.getId());
            company.setCompanyName(request.getCompanyName().trim());
            company.setShortName(blankToNull(request.getShortName()));
            company.setCreditCode(creditCode);
            company.setContactName(request.getContactName().trim());
            company.setContactPhone(phone);
            company.setContactEmail(email);
            company.setIndustry(blankToNull(request.getIndustry()));
            company.setScale(request.getScale() == null ? 0 : request.getScale());
            company.setProvince(blankToNull(request.getProvince()));
            company.setCity(blankToNull(request.getCity()));
            company.setAddress(blankToNull(request.getAddress()));
            company.setAuditStatus(0);
            company.setDeleted(0);
            entCompanyMapper.insert(company);
        } catch (DuplicateKeyException e) {
            throw translateDuplicate(e);
        }
        log.info("企业注册成功: {}，资质待审核", username);
        return userAssembler.toVO(user.getId());
    }

    private void assertUsernameAvailable(String username) {
        Long count = sysUserMapper.selectCount(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getUsername, username));
        if (count != null && count > 0) {
            throw new BusinessException(400, "用户名已存在");
        }
    }

    private BusinessException translateDuplicate(DuplicateKeyException e) {
        String raw = e.getMostSpecificCause() == null ? "" : String.valueOf(e.getMostSpecificCause().getMessage());
        log.warn("注册唯一约束冲突");
        if (raw.contains("uk_sys_user_username")) {
            return new BusinessException(400, "用户名已存在");
        }
        if (raw.contains("uk_ent_company_credit")) {
            return new BusinessException(400, "统一社会信用代码已存在");
        }
        if (raw.contains("uk_stu_profile_student_no")) {
            return new BusinessException(400, "学号已存在");
        }
        return new BusinessException(400, "数据已存在");
    }

    private String normalizePhone(String phone) {
        String value = blankToNull(phone);
        if (value != null && !PHONE.matcher(value).matches()) {
            throw new BusinessException(400, "手机号格式不正确");
        }
        return value;
    }

    private String normalizeEmail(String email) {
        String value = blankToNull(email);
        if (value != null && !EMAIL.matcher(value).matches()) {
            throw new BusinessException(400, "邮箱格式不正确");
        }
        return value;
    }

    private String blankToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
