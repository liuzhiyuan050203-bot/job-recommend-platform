package com.bishe.job.dto;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

/**
 * 把解析得到的技能标签并入当前学生的 stu_skill。
 */
@Data
public class ResumeSkillMergeDTO {

    @NotEmpty(message = "请选择要合并的技能")
    @Size(max = 30, message = "一次最多合并 30 项技能")
    private List<@NotNull(message = "技能编号不能为空") Long> tagIds;
}
