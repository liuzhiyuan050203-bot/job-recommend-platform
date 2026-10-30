package com.bishe.job.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class BannerDTO {

    @NotBlank(message = "轮播图标题不能为空")
    private String title;

    @NotBlank(message = "图片地址不能为空")
    private String imageUrl;

    private String linkUrl;

    private Integer sortNo;

    private Integer status;

    private LocalDateTime startTime;

    private LocalDateTime endTime;
}
