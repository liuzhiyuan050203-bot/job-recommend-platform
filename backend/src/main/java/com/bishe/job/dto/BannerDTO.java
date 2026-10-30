package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class BannerDTO {

    @NotBlank(message = "轮播图标题不能为空")
    @Size(max = 128, message = "轮播图标题长度不能超过 128")
    private String title;

    @NotBlank(message = "图片地址不能为空")
    @Size(max = 512, message = "图片地址长度不能超过 512")
    private String imageUrl;

    @Size(max = 512, message = "跳转地址长度不能超过 512")
    private String linkUrl;

    private Integer sortNo;

    @Min(value = 0, message = "状态取值不合法")
    @Max(value = 1, message = "状态取值不合法")
    private Integer status;

    private LocalDateTime startTime;

    private LocalDateTime endTime;
}
