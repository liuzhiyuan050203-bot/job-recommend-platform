package com.bishe.job.service;

import com.bishe.job.vo.JobSourceVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 把职位的岗位职责、任职要求、福利整理成给人看的条目。
 *
 * <p>真实职位（data/import_real_jobs.py 从校招官网同步）在 requirement 里存的是抓取元数据 JSON
 * （{"provenance": {...}}），description 前几行是【来源】【抓取时间】等元数据，welfare 是投递链接。
 * 这些字段保留在库里供溯源，展示时在这里拆开：元数据进 {@link JobSourceVO}，正文拆成条目，
 * 「薪资为平台按方向与城市估算」这句标出估算薪资。也兼容 JSON 数组、带序号文本和字面量 \n。</p>
 */
public final class JobTextCleaner {

    public static final String ESTIMATE_MARK = "薪资为平台按方向与城市估算";
    public static final String ESTIMATE_NOTE = "该职位来自校招官网公开信息，官网未公布薪资，此处薪资为平台按技术方向与城市估算，仅供参考，以官网为准。";

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Pattern META_LINE = Pattern.compile("^【(校招官网投递|来源|项目/方向|工作城市|抓取时间)】\\s*(.*)$");
    private static final Pattern NAME_LINE = Pattern.compile("^岗位名称[:：]");
    private static final Pattern SYNC_LINE = Pattern.compile("^本条记录由.*同步");
    private static final Pattern APPLY_LINE = Pattern.compile("^投递链接[:：]\\s*(\\S+)\\s*$");
    private static final Pattern BULLET = Pattern.compile("^\\s*(?:[（(]?\\d{1,2}[)）.、．:：](?!\\d)|[•·\\-*●▪]|[一二三四五六七八九十][、.])\\s*");
    private static final Pattern URL = Pattern.compile("https?://\\S+");
    private static final String[] LIST_KEYS = {"requirements", "requirement", "duties", "items", "content", "text", "list"};
    private static final String[] ITEM_KEYS = {"text", "content", "name", "value", "desc"};

    private JobTextCleaner() {
    }

    /** 整理结果。 */
    public record Cleaned(List<String> descriptionItems, List<String> requirementItems, String welfare,
                          JobSourceVO source, boolean salaryEstimated) {
    }

    public static Cleaned clean(String description, String requirement, String welfare) {
        JobSourceVO source = new JobSourceVO();
        boolean estimated = false;

        List<String> requirementItems = new ArrayList<>();
        String req = requirement == null ? "" : requirement.trim();
        if (looksLikeJson(req)) {
            JsonNode node = parse(req);
            if (node != null) {
                estimated |= readProvenance(node, source);
                requirementItems.addAll(itemsOf(node));
            } else {
                requirementItems.addAll(splitText(stripJsonPunctuation(req)));
            }
        } else {
            requirementItems.addAll(splitText(req));
        }

        List<String> descriptionItems = new ArrayList<>();
        for (String line : lines(description)) {
            Matcher meta = META_LINE.matcher(line);
            if (meta.find()) {
                fillFromMeta(source, meta.group(1), meta.group(2).trim());
                continue;
            }
            if (NAME_LINE.matcher(line).find()) {
                continue;
            }
            if (SYNC_LINE.matcher(line).find() || line.contains(ESTIMATE_MARK)) {
                estimated |= line.contains(ESTIMATE_MARK);
                if (source.getType() == null) {
                    source.setType(JobSourceVO.CRAWLER);
                }
                continue;
            }
            String item = stripBullet(line);
            if (!item.isEmpty()) {
                descriptionItems.add(item);
            }
        }

        List<String> welfareParts = new ArrayList<>();
        for (String line : lines(welfare)) {
            Matcher apply = APPLY_LINE.matcher(line);
            if (apply.find()) {
                if (source.getApplyUrl() == null) {
                    source.setApplyUrl(apply.group(1));
                }
                continue;
            }
            welfareParts.add(line);
        }

        if (source.getType() == null) {
            source.setType(JobSourceVO.PLATFORM);
            source.setLabel("企业发布");
        } else if (source.getLabel() == null) {
            source.setLabel(source.getSite() == null ? "校招官网同步" : source.getSite());
        }
        return new Cleaned(descriptionItems, requirementItems, String.join("\n", welfareParts), source, estimated);
    }

    private static boolean looksLikeJson(String text) {
        return text.startsWith("{") || text.startsWith("[") || (text.startsWith("\"") && text.endsWith("\""));
    }

    private static JsonNode parse(String text) {
        try {
            JsonNode node = MAPPER.readTree(text);
            // 双重编码："[\"1. xx\"]" 先解成字符串再解一次
            if (node != null && node.isTextual() && looksLikeJson(node.asText().trim())) {
                JsonNode inner = parse(node.asText().trim());
                return inner == null ? node : inner;
            }
            return node;
        } catch (Exception ex) {
            return null;
        }
    }

    private static boolean readProvenance(JsonNode node, JobSourceVO source) {
        if (!node.isObject()) {
            return false;
        }
        JsonNode p = node.has("provenance") && node.get("provenance").isObject() ? node.get("provenance") : node;
        String site = text(p, "source", "crawl_source", "platform");
        String company = text(p, "company_label", "company");
        if (site == null && company == null && !p.has("apply_url")) {
            return flag(node);
        }
        source.setType(JobSourceVO.CRAWLER);
        source.setSite(site);
        source.setLabel(company == null ? site : company + "校招官网");
        source.setApplyUrl(text(p, "apply_url", "url"));
        source.setCrawledAt(text(p, "crawled_at"));
        source.setProject(text(p, "project"));
        source.setWorkCities(text(p, "work_cities"));
        return flag(node) || flag(p);
    }

    private static boolean flag(JsonNode node) {
        for (String key : new String[]{"salary_estimated", "is_estimated_salary", "is_estimated"}) {
            if (node.has(key) && node.get(key).asBoolean(false)) {
                return true;
            }
        }
        return false;
    }

    private static List<String> itemsOf(JsonNode node) {
        List<String> out = new ArrayList<>();
        if (node.isArray()) {
            for (JsonNode item : node) {
                String text = item.isTextual() || item.isNumber() ? item.asText() : text(item, ITEM_KEYS);
                if (text != null) {
                    out.addAll(splitText(text));
                }
            }
        } else if (node.isObject()) {
            for (String key : LIST_KEYS) {
                if (node.has(key)) {
                    out.addAll(itemsOf(node.get(key)));
                    if (!out.isEmpty()) {
                        break;
                    }
                }
            }
        } else if (node.isTextual()) {
            out.addAll(splitText(node.asText()));
        }
        return out;
    }

    private static String text(JsonNode node, String... keys) {
        if (node == null || !node.isObject()) {
            return null;
        }
        for (String key : keys) {
            JsonNode v = node.get(key);
            if (v != null && !v.isNull() && !v.asText().isBlank()) {
                return v.asText().trim();
            }
        }
        return null;
    }

    private static void fillFromMeta(JobSourceVO source, String key, String value) {
        source.setType(JobSourceVO.CRAWLER);
        switch (key) {
            case "校招官网投递" -> {
                Matcher m = URL.matcher(value);
                if (source.getApplyUrl() == null && m.find()) {
                    source.setApplyUrl(m.group());
                }
            }
            case "来源" -> {
                String[] parts = value.split("\\s*/\\s*");
                if (source.getSite() == null && parts.length > 0) {
                    source.setSite(parts[0]);
                }
                if (source.getLabel() == null && parts.length > 1) {
                    source.setLabel(parts[1] + "校招官网");
                }
            }
            case "项目/方向" -> {
                if (source.getProject() == null) {
                    source.setProject(value.split("\\s*/\\s*")[0]);
                }
            }
            case "工作城市" -> {
                if (source.getWorkCities() == null) {
                    source.setWorkCities(value);
                }
            }
            case "抓取时间" -> {
                if (source.getCrawledAt() == null) {
                    source.setCrawledAt(value);
                }
            }
            default -> {
            }
        }
    }

    /** 按换行（含字面量 \n）、中英文分号拆分，去掉序号与空行。 */
    static List<String> splitText(String text) {
        List<String> out = new ArrayList<>();
        for (String line : lines(text)) {
            for (String piece : line.split("[；;]")) {
                String item = stripBullet(piece);
                if (!item.isEmpty()) {
                    out.add(item);
                }
            }
        }
        return out;
    }

    private static List<String> lines(String text) {
        List<String> out = new ArrayList<>();
        if (text == null) {
            return out;
        }
        String normalized = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n");
        for (String line : normalized.split("\n")) {
            String t = line.trim();
            if (!t.isEmpty()) {
                out.add(t);
            }
        }
        return out;
    }

    private static String stripBullet(String text) {
        String t = text.trim();
        Matcher m = BULLET.matcher(t);
        if (m.find()) {
            t = t.substring(m.end());
        }
        return t.replaceAll("[。；;，,\\s]+$", "").trim();
    }

    /** JSON 解析失败时兜底：去掉方括号、引号、转义，保留文字。 */
    private static String stripJsonPunctuation(String text) {
        return text.replaceAll("^[\\[{\\s\"]+|[\\]}\\s\"]+$", "")
                .replace("\\\"", "\"")
                .replaceAll("\"\\s*,\\s*\"", "\n")
                .replace("\"", "");
    }
}
