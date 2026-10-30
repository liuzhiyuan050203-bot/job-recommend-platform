package com.bishe.job.service;

import com.bishe.job.dto.PasswordUpdateRequest;
import com.bishe.job.vo.UserVO;

public interface UserService {

    UserVO current();

    void updatePassword(PasswordUpdateRequest request);
}
