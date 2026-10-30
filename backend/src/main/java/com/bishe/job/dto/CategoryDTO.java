package com.bishe.job.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class CategoryDTO {

    private Long parentId;

    @NotBlank(message = "分类名称不能为空")
    private String name;

    private Integer sortNo;

    private Integer status;
}
