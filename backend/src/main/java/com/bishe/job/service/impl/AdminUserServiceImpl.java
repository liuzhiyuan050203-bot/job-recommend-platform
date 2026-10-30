package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.AdminUserService;
import com.bishe.job.vo.AdminUserVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.Collections;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminUserServiceImpl implements AdminUserService {

    private final SysUserMapper sysUserMapper;
    private final PasswordEncoder passwordEncoder;

    @Override
    public PageResult<AdminUserVO> listUsers(Integer role, Integer status, String keyword, long current, long size) {
        Page<SysUser> page = Pages.of(current, size);
        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<>();

        if (role != null) {
            wrapper.eq(SysUser::getRole, role);
        }
        if (status != null) {
            wrapper.eq(SysUser::getStatus, status);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.and(w -> w.like(SysUser::getUsername, kw)
                    .or().like(SysUser::getNickname, kw)
                    .or().like(SysUser::getPhone, kw)
                    .or().like(SysUser::getEmail, kw));
        }
        wrapper.orderByDesc(SysUser::getId);

        sysUserMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<AdminUserVO> list = page.getRecords().stream().map(this::toVO).toList();
        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateUserStatus(Long id, Integer status) {
        Long currentAdminId = UserContext.get().getId();
        if (id.equals(currentAdminId) && status == 2) {
            throw new BusinessException(400, "不能禁用当前登录的管理员账号");
        }

        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        user.setStatus(status);
        sysUserMapper.updateById(user);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void resetPassword(Long id) {
        SysUser user = sysUserMapper.selectById(id);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        user.setPassword(passwordEncoder.encode("123456"));
        sysUserMapper.updateById(user);
    }

    private AdminUserVO toVO(SysUser user) {
        AdminUserVO vo = new AdminUserVO();
        vo.setId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setRole(user.getRole());
        vo.setRoleName(RoleCodes.nameOf(user.getRole()));
        vo.setNickname(user.getNickname());
        vo.setPhone(user.getPhone());
        vo.setEmail(user.getEmail());
        vo.setAvatar(user.getAvatar());
        vo.setStatus(user.getStatus());
        vo.setAuditRemark(user.getAuditRemark());
        vo.setLastLoginTime(user.getLastLoginTime());
        vo.setCreateTime(user.getCreateTime());
        return vo;
    }
}
