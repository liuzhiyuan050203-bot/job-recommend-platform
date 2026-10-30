package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ArticleDTO {

    @NotNull(message = "内容类型不能为空")
    @Min(value = 1, message = "类型：1双选会公告 2就业政策 3新闻资讯")
    @Max(value = 3, message = "类型：1双选会公告 2就业政策 3新闻资讯")
    private Integer articleType;

    @NotBlank(message = "标题不能为空")
    private String title;

    private String coverUrl;

    private String summary;

    @NotBlank(message = "正文内容不能为空")
    private String content;

    private Integer topFlag;

    private Integer status;
}
