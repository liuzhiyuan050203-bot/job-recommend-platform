package com.bishe.job.service;

import com.bishe.job.dto.CompanyRegisterRequest;
import com.bishe.job.dto.LoginRequest;
import com.bishe.job.dto.StudentRegisterRequest;
import com.bishe.job.vo.LoginVO;
import com.bishe.job.vo.UserVO;

public interface AuthService {

    LoginVO login(LoginRequest request);

    UserVO registerStudent(StudentRegisterRequest request);

    UserVO registerCompany(CompanyRegisterRequest request);
}
