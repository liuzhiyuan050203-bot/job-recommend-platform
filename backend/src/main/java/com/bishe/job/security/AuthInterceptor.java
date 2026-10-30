package com.bishe.job.security;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.common.Result;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;

/**
 * 登录与角色拦截。
 * <p>
 * /api/public/**、/api/health 放行；/api/student/** 仅学生；/api/company/** 仅企业；
 * /api/admin/** 仅管理员；其余 /api/** 登录即可。每次请求都会核对数据库中的账号状态，
 * 禁用后旧令牌立即失效。企业资质未通过时，只允许访问 /api/company/profile/**。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    static final String COMPANY_AUDIT_DENIED = "企业资质未审核通过";

    private final JwtUtil jwtUtil;
    private final SysUserMapper sysUserMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final ObjectMapper objectMapper;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        UserContext.clear();
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String uri = requestPath(request);
        if (isPublic(uri)) {
            return true;
        }

        String token = resolveToken(request);
        if (!StringUtils.hasText(token)) {
            return reject(response, 401, "未登录或登录已过期");
        }

        Long userId;
        try {
            userId = jwtUtil.parseUserId(token);
        } catch (ExpiredJwtException e) {
            return reject(response, 401, "登录已过期，请重新登录");
        } catch (JwtException | IllegalArgumentException e) {
            return reject(response, 401, "登录令牌无效，请重新登录");
        }

        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            return reject(response, 401, "账号不存在或已被删除");
        }
        if (!AccountStatus.isActive(user.getStatus())) {
            return reject(response, 401, AccountStatus.denyMessage(user.getStatus()));
        }

        Integer requiredRole = requiredRole(uri);
        if (requiredRole != null && !requiredRole.equals(user.getRole())) {
            return reject(response, 403, "无权限，当前角色无法访问该接口");
        }

        Integer companyAuditStatus = null;
        if (Integer.valueOf(RoleCodes.COMPANY).equals(user.getRole())) {
            EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                    .eq(EntCompany::getUserId, user.getId()));
            companyAuditStatus = company == null ? null : company.getAuditStatus();
            boolean companyApi = requiredRole != null && requiredRole == RoleCodes.COMPANY;
            if (companyApi && !isCompanyProfile(uri) && (companyAuditStatus == null || companyAuditStatus != 1)) {
                return reject(response, 403, COMPANY_AUDIT_DENIED);
            }
        }

        LoginUser loginUser = new LoginUser();
        loginUser.setId(user.getId());
        loginUser.setUsername(user.getUsername());
        loginUser.setRole(user.getRole());
        loginUser.setStatus(user.getStatus());
        loginUser.setNickname(user.getNickname());
        loginUser.setCompanyAuditStatus(companyAuditStatus);
        UserContext.set(loginUser);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        UserContext.clear();
    }

    private boolean isPublic(String uri) {
        return "/api/health".equals(uri) || "/api/public".equals(uri) || uri.startsWith("/api/public/");
    }

    private Integer requiredRole(String uri) {
        if ("/api/student".equals(uri) || uri.startsWith("/api/student/")) {
            return RoleCodes.STUDENT;
        }
        if ("/api/company".equals(uri) || uri.startsWith("/api/company/")) {
            return RoleCodes.COMPANY;
        }
        if ("/api/admin".equals(uri) || uri.startsWith("/api/admin/")) {
            return RoleCodes.ADMIN;
        }
        return null;
    }

    private boolean isCompanyProfile(String uri) {
        return "/api/company/profile".equals(uri) || uri.startsWith("/api/company/profile/");
    }

    private String resolveToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (!StringUtils.hasText(header)) {
            return null;
        }
        String value = header.trim();
        if (value.length() > 7 && value.regionMatches(true, 0, "Bearer ", 0, 7)) {
            String token = value.substring(7).trim();
            return token.isEmpty() ? null : token;
        }
        return null;
    }

    private String requestPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String contextPath = request.getContextPath();
        if (StringUtils.hasText(contextPath) && uri.startsWith(contextPath)) {
            uri = uri.substring(contextPath.length());
        }
        if (uri.length() > 1 && uri.endsWith("/")) {
            uri = uri.substring(0, uri.length() - 1);
        }
        return uri;
    }

    private boolean reject(HttpServletResponse response, int code, String msg) throws Exception {
        if (response.isCommitted()) {
            return false;
        }
        response.setStatus(code);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        objectMapper.writeValue(response.getWriter(), Result.error(code, msg));
        return false;
    }
}
