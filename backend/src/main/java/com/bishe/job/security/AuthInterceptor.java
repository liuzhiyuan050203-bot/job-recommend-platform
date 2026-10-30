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
import org.springframework.web.util.UrlPathHelper;

import java.nio.charset.StandardCharsets;

/**
 * 登录与角色拦截。
 * <p>
 * /api/public/**、/api/health 放行，但若携带有效令牌会写入当前用户（可选认证），
 * 无效或过期令牌按匿名处理，不返回 401；/api/student/** 仅学生；/api/company/** 仅企业；
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
        if (suspicious(request, uri)) {
            return reject(response, 400, "非法请求路径");
        }
        if (isPublic(uri)) {
            authenticateOptional(request);
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

    /**
     * 公开接口上的可选认证：令牌有效且账号正常时写入 UserContext，否则保持匿名。
     * 不因无效令牌拒绝请求。
     */
    private void authenticateOptional(HttpServletRequest request) {
        String token = resolveToken(request);
        if (!StringUtils.hasText(token)) {
            return;
        }
        try {
            Long userId = jwtUtil.parseUserId(token);
            SysUser user = sysUserMapper.selectById(userId);
            if (user == null || !AccountStatus.isActive(user.getStatus())) {
                return;
            }
            Integer companyAuditStatus = null;
            if (Integer.valueOf(RoleCodes.COMPANY).equals(user.getRole())) {
                EntCompany company = entCompanyMapper.selectOne(new LambdaQueryWrapper<EntCompany>()
                        .eq(EntCompany::getUserId, user.getId()));
                companyAuditStatus = company == null ? null : company.getAuditStatus();
            }
            LoginUser loginUser = new LoginUser();
            loginUser.setId(user.getId());
            loginUser.setUsername(user.getUsername());
            loginUser.setRole(user.getRole());
            loginUser.setStatus(user.getStatus());
            loginUser.setNickname(user.getNickname());
            loginUser.setCompanyAuditStatus(companyAuditStatus);
            UserContext.set(loginUser);
        } catch (JwtException | IllegalArgumentException ex) {
            log.debug("公开接口忽略无效令牌");
        }
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

    /**
     * 计算用于权限判断的路径：必须与 Spring MVC 路由匹配时看到的路径一致，
     * 因此先做 URL 解码、去掉 ;矩阵参数、合并多余斜杠，防止 /api/%61dmin、/api/admin;x 之类绕过角色校验。
     */
    private String requestPath(HttpServletRequest request) {
        UrlPathHelper helper = new UrlPathHelper();
        helper.setUrlDecode(true);
        helper.setRemoveSemicolonContent(true);
        String uri = helper.getPathWithinApplication(request);
        uri = uri.replaceAll("/{2,}", "/");
        if (uri.length() > 1 && uri.endsWith("/")) {
            uri = uri.substring(0, uri.length() - 1);
        }
        return uri;
    }

    /**
     * 含路径穿越的请求一律 400。同时看容器给出的路径、原始百分号编码（%2e%2e）和解码后的结果，
     * 避免编码点号被还原成 .. 之后绕过角色前缀判断。
     */
    private boolean suspicious(HttpServletRequest request, String uri) {
        String raw = request.getRequestURI() == null ? "" : request.getRequestURI();
        String lower = raw.toLowerCase();
        String decoded = raw;
        try {
            decoded = java.net.URLDecoder.decode(raw, StandardCharsets.UTF_8);
        } catch (IllegalArgumentException ex) {
            return true;
        }
        return hasDotDot(uri) || hasDotDot(raw) || hasDotDot(decoded)
                || lower.contains("%2e%2e") || lower.contains("%2e.") || lower.contains(".%2e")
                || lower.contains("%5c")
                || uri.contains("\\") || raw.contains("\\") || decoded.contains("\\")
                || uri.contains("/./") || decoded.contains("/./");
    }

    private boolean hasDotDot(String value) {
        return value != null && value.contains("..");
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
