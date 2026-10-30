package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.vo.AdminUserVO;

public interface AdminUserService {

    PageResult<AdminUserVO> listUsers(Integer role, Integer status, String keyword, long current, long size);

    void updateUserStatus(Long id, Integer status);

    void resetPassword(Long id);
}
