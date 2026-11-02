package com.bishe.job.service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * PDF 解析技能写入个人档案后，同步到默认在线简历的 skillDesc；
 * 并识别测试/污染简历标题，避免把技能写进 UX-IDOR 一类夹具简历。
 */
public final class ResumeSkillSync {

    /** 测试、越权、流程夹具简历标题；投递弹窗与默认简历选取都会排除。 */
    private static final Pattern TEST_TITLE = Pattern.compile(
            "UX-IDOR|越权|测试简历|_勿用|流程测试|匹配测试|详情整理|推荐测试|隔离职位|夹具",
            Pattern.CASE_INSENSITIVE);

    private ResumeSkillSync() {
    }

    public static boolean isTestTitle(String title) {
        if (title == null || title.isBlank()) {
            return false;
        }
        return TEST_TITLE.matcher(title).find();
    }

    /**
     * 把技能名合并进 skillDesc：保留原有文字顺序，追加尚未出现的技能（顿号分隔）。
     */
    public static String mergeSkillDesc(String existing, List<String> skillNames) {
        LinkedHashSet<String> ordered = new LinkedHashSet<>();
        if (existing != null && !existing.isBlank()) {
            for (String part : existing.split("[、,，;；/\\|\\n]+")) {
                String name = part.trim().replaceAll("[。.\\s]+$", "");
                // 去掉「Spark 入门」这类后缀里的熟练度词，只留技能本体作去重键时仍保留原文片段
                if (!name.isEmpty()) {
                    ordered.add(name);
                }
            }
        }
        List<String> added = new ArrayList<>();
        if (skillNames != null) {
            for (String raw : skillNames) {
                if (raw == null || raw.isBlank()) {
                    continue;
                }
                String name = raw.trim();
                if (!containsIgnoreCase(ordered, name)) {
                    ordered.add(name);
                    added.add(name);
                }
            }
        }
        if (ordered.isEmpty()) {
            return existing == null ? "" : existing;
        }
        // 若原先为空或只有空白，直接用顿号连接；否则在原文本后追加新增项，尽量少改学生手写内容
        if (existing == null || existing.isBlank()) {
            return String.join("、", ordered) + "。";
        }
        if (added.isEmpty()) {
            return existing;
        }
        String trimmed = existing.stripTrailing();
        if (trimmed.endsWith("。") || trimmed.endsWith(".")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        String joiner = trimmed.isEmpty() ? "" : "、";
        return trimmed + joiner + String.join("、", added) + "。";
    }

    public static String campusResumeTitle(String realName, String nickname) {
        String base = (realName != null && !realName.isBlank()) ? realName.trim()
                : (nickname != null && !nickname.isBlank() ? nickname.trim() : "我的");
        return base + "-校招简历";
    }

    private static boolean containsIgnoreCase(Iterable<String> names, String target) {
        String needle = target.toLowerCase(Locale.ROOT);
        for (String name : names) {
            if (name.toLowerCase(Locale.ROOT).equals(needle)) {
                return true;
            }
            // 「Spark 入门」视为已含 Spark
            if (name.toLowerCase(Locale.ROOT).startsWith(needle + " ")
                    || name.toLowerCase(Locale.ROOT).startsWith(needle + "　")) {
                return true;
            }
        }
        return false;
    }
}
