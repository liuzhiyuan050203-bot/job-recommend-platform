package com.bishe.job.common;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

/**
 * 分页参数收敛：页码从 1 开始，单页不超过分页插件上限。
 */
public final class Pages {

    private Pages() {
    }

    public static long current(long current) {
        return current < 1 ? 1 : current;
    }

    public static long size(long size) {
        if (size < 1) {
            return 10;
        }
        return Math.min(size, 100);
    }

    public static <T> Page<T> of(long current, long size) {
        return new Page<>(current(current), size(size));
    }
}
