package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.dto.CompanyRegisterRequest;
import com.bishe.job.dto.LoginRequest;
import com.bishe.job.dto.StudentRegisterRequest;
import com.bishe.job.service.AuthService;
import com.bishe.job.vo.LoginVO;
import com.bishe.job.vo.UserVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 公开认证接口。管理员账号只来自种子数据，不提供注册。
 */
@RestController
@RequestMapping("/api/public/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public Result<LoginVO> login(@Valid @RequestBody LoginRequest request) {
        return Result.success("登录成功", authService.login(request));
    }

    @PostMapping("/register/student")
    public Result<UserVO> registerStudent(@Valid @RequestBody StudentRegisterRequest request) {
        return Result.success("注册成功", authService.registerStudent(request));
    }

    @PostMapping("/register/company")
    public Result<UserVO> registerCompany(@Valid @RequestBody CompanyRegisterRequest request) {
        return Result.success("注册成功，请等待企业资质审核", authService.registerCompany(request));
    }
}
