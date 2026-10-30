package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class PostCreateDTO {

    @NotNull(message = "帖子类型不能为空")
    @Min(value = 1, message = "类型：1面经 2企业评价")
    @Max(value = 2, message = "类型：1面经 2企业评价")
    private Integer postType;

    @NotBlank(message = "标题不能为空")
    @Size(max = 128, message = "标题长度最多 128 字")
    private String title;

    @NotBlank(message = "内容不能为空")
    private String content;

    @Min(value = 1, message = "评分范围 1-5")
    @Max(value = 5, message = "评分范围 1-5")
    private Integer rating;

    private Long companyId;

    private Long positionId;
}
