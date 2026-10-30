package com.bishe.job.service.impl;

import com.bishe.job.common.BusinessException;
import com.bishe.job.dto.PasswordUpdateRequest;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.AccountStatus;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.UserAssembler;
import com.bishe.job.service.UserService;
import com.bishe.job.vo.UserVO;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final SysUserMapper sysUserMapper;
    private final PasswordEncoder passwordEncoder;
    private final UserAssembler userAssembler;

    @Override
    public UserVO current() {
        return userAssembler.toVO(UserContext.require().getId());
    }

    @Override
    public void updatePassword(PasswordUpdateRequest request) {
        Long userId = UserContext.require().getId();
        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(401, "账号不存在或已被删除");
        }
        if (!AccountStatus.isActive(user.getStatus())) {
            throw new BusinessException(401, AccountStatus.denyMessage(user.getStatus()));
        }
        if (!passwordEncoder.matches(request.getOldPassword(), user.getPassword())) {
            throw new BusinessException(400, "原密码不正确");
        }
        SysUser patch = new SysUser();
        patch.setId(userId);
        patch.setPassword(passwordEncoder.encode(request.getNewPassword()));
        sysUserMapper.updateById(patch);
    }
}
