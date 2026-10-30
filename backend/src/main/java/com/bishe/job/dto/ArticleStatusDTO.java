package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ArticleStatusDTO {

    @NotNull(message = "状态不能为空")
    @Min(value = 0, message = "状态：0草稿 1已发布 2已下线")
    @Max(value = 2, message = "状态：0草稿 1已发布 2已下线")
    private Integer status;
}
