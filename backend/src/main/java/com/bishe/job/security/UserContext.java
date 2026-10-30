package com.bishe.job.security;

import com.bishe.job.common.BusinessException;

/**
 * 当前登录用户上下文。拦截器写入，请求结束清理，避免线程池复用串号。
 */
public final class UserContext {

    private static final ThreadLocal<LoginUser> HOLDER = new ThreadLocal<>();

    private UserContext() {
    }

    public static void set(LoginUser user) {
        HOLDER.set(user);
    }

    public static LoginUser get() {
        return HOLDER.get();
    }

    public static LoginUser require() {
        LoginUser user = get();
        if (user == null || user.getId() == null) {
            throw new BusinessException(401, "未登录或登录已过期");
        }
        return user;
    }

    public static Long getUserId() {
        LoginUser user = get();
        return user == null ? null : user.getId();
    }

    public static Integer getRole() {
        LoginUser user = get();
        return user == null ? null : user.getRole();
    }

    public static void clear() {
        HOLDER.remove();
    }
}
