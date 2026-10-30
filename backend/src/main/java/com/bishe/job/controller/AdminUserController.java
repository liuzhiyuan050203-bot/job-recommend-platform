package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.UserStatusDTO;
import com.bishe.job.service.AdminUserService;
import com.bishe.job.vo.AdminUserVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/users")
@RequiredArgsConstructor
public class AdminUserController {

    private final AdminUserService adminUserService;

    @GetMapping
    public Result<PageResult<AdminUserVO>> listUsers(
            @RequestParam(value = "role", required = false) Integer role,
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminUserService.listUsers(role, status, keyword, current, size));
    }

    @PutMapping("/{id}/status")
    public Result<Void> updateStatus(@PathVariable("id") Long id,
                                    @Valid @RequestBody UserStatusDTO dto) {
        adminUserService.updateUserStatus(id, dto.getStatus());
        return Result.success("账号状态更新成功", null);
    }

    @PutMapping("/{id}/reset-password")
    public Result<Void> resetPassword(@PathVariable("id") Long id) {
        adminUserService.resetPassword(id);
        return Result.success("密码已成功重置为 123456", null);
    }
}
