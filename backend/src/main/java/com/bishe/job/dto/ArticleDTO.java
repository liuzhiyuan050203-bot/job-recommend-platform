package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class ArticleDTO {

    @NotNull(message = "内容类型不能为空")
    @Min(value = 1, message = "类型：1双选会公告 2就业政策 3新闻资讯")
    @Max(value = 3, message = "类型：1双选会公告 2就业政策 3新闻资讯")
    private Integer articleType;

    @NotBlank(message = "标题不能为空")
    @Size(max = 128, message = "标题长度不能超过 128")
    private String title;

    @Size(max = 512, message = "封面地址长度不能超过 512")
    private String coverUrl;

    @Size(max = 500, message = "摘要长度不能超过 500")
    private String summary;

    @NotBlank(message = "正文内容不能为空")
    private String content;

    @Min(value = 0, message = "置顶取值不合法")
    @Max(value = 1, message = "置顶取值不合法")
    private Integer topFlag;

    @Min(value = 0, message = "状态：0草稿 1已发布 2已下线")
    @Max(value = 2, message = "状态：0草稿 1已发布 2已下线")
    private Integer status;
}
