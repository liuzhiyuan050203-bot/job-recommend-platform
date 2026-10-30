package com.bishe.job.service;

import com.bishe.job.common.BusinessException;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 投递状态机。合法迁移只有：
 * <ul>
 *   <li>0 待初筛 → 1 笔试、2 面试中、4 未通过</li>
 *   <li>1 笔试 → 2 面试中、4 未通过</li>
 *   <li>2 面试中 → 3 已录用、4 未通过</li>
 * </ul>
 * 3 已录用、4 未通过是终态，不能再迁出。状态取值与 job_application.status 一致。
 */
public final class ApplicationStateMachine {

    private static final Map<Integer, Set<Integer>> NEXT = Map.of(
            0, Set.of(1, 2, 4),
            1, Set.of(2, 4),
            2, Set.of(3, 4)
    );

    private static final Map<Integer, String> NAMES = Map.of(
            0, "待初筛",
            1, "笔试",
            2, "面试中",
            3, "已录用",
            4, "未通过"
    );

    private ApplicationStateMachine() {
    }

    public static boolean canTransit(int from, int to) {
        return NEXT.getOrDefault(from, Set.of()).contains(to);
    }

    /**
     * 非法迁移抛出业务异常，文案为「不允许从 X 变为 Y」。
     */
    public static void assertCanTransit(int from, int to) {
        if (!canTransit(from, to)) {
            throw new BusinessException(400, "不允许从「" + nameOf(from) + "」变为「" + nameOf(to) + "」");
        }
    }

    public static List<Integer> nextOf(Integer from) {
        if (from == null) {
            return List.of();
        }
        Set<Integer> next = NEXT.get(from);
        if (next == null || next.isEmpty()) {
            return List.of();
        }
        return next.stream().sorted().toList();
    }

    public static String nameOf(Integer status) {
        if (status == null) {
            return "";
        }
        return NAMES.getOrDefault(status, String.valueOf(status));
    }
}
