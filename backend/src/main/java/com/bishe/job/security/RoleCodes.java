package com.bishe.job.security;

/**
 * 与 sys_user.role 一致的角色编码。对外角色名统一为 student / company / admin。
 */
public final class RoleCodes {

    public static final int STUDENT = 1;
    public static final int COMPANY = 2;
    public static final int ADMIN = 3;

    private RoleCodes() {
    }

    public static String nameOf(Integer role) {
        if (role == null) {
            return "";
        }
        return switch (role) {
            case STUDENT -> "student";
            case COMPANY -> "company";
            case ADMIN -> "admin";
            default -> "";
        };
    }
}
