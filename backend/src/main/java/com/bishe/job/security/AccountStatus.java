package com.bishe.job.security;

/**
 * sys_user.status：0 待审核，1 正常，2 禁用，3 已驳回。
 */
public final class AccountStatus {

    public static final int PENDING = 0;
    public static final int ACTIVE = 1;
    public static final int DISABLED = 2;
    public static final int REJECTED = 3;

    private AccountStatus() {
    }

    public static boolean isActive(Integer status) {
        return status != null && status == ACTIVE;
    }

    /**
     * 不能登录或继续访问时的提示。禁用账号的旧令牌会立刻失效。
     */
    public static String denyMessage(Integer status) {
        if (status == null) {
            return "账号状态异常";
        }
        return switch (status) {
            case PENDING -> "账号待审核，暂不能登录";
            case DISABLED -> "账号已被禁用";
            case REJECTED -> "账号审核未通过，暂不能登录";
            default -> "账号状态异常，暂不能登录";
        };
    }
}
