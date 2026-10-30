package com.bishe.job.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class JobSaveDTO {

    @NotNull(message = "请选择职位分类")
    private Long categoryId;

    @NotBlank(message = "职位名称不能为空")
    @Size(max = 128, message = "职位名称长度不能超过 128")
    private String title;

    @NotBlank(message = "工作省份不能为空")
    @Size(max = 32, message = "省份长度不能超过 32")
    private String province;

    @NotBlank(message = "工作城市不能为空")
    @Size(max = 32, message = "城市长度不能超过 32")
    private String city;

    @Size(max = 32, message = "区县长度不能超过 32")
    private String district;

    @Size(max = 255, message = "工作地址长度不能超过 255")
    private String address;

    @NotNull(message = "最低月薪不能为空")
    @Min(value = 0, message = "最低月薪不能小于 0")
    private Integer salaryMin;

    @NotNull(message = "最高月薪不能为空")
    @Min(value = 0, message = "最高月薪不能小于 0")
    private Integer salaryMax;

    @NotNull(message = "发薪月数不能为空")
    @Min(value = 12, message = "发薪月数需在 12 到 24 之间")
    @Max(value = 24, message = "发薪月数需在 12 到 24 之间")
    private Integer salaryMonths;

    @NotNull(message = "学历要求不能为空")
    @Min(value = 0, message = "学历要求取值不正确")
    @Max(value = 4, message = "学历要求取值不正确")
    private Integer education;

    @NotNull(message = "经验要求不能为空")
    @Min(value = 0, message = "经验要求取值不正确")
    @Max(value = 5, message = "经验要求取值不正确")
    private Integer experienceReq;

    @NotNull(message = "工作性质不能为空")
    @Min(value = 1, message = "工作性质取值不正确")
    @Max(value = 3, message = "工作性质取值不正确")
    private Integer jobType;

    @NotNull(message = "招聘人数不能为空")
    @Min(value = 1, message = "招聘人数至少为 1")
    private Integer headcount;

    private String description;

    private String requirement;

    @Size(max = 500, message = "福利待遇长度不能超过 500")
    private String welfare;

    @Size(max = 20, message = "技能标签最多选择 20 个")
    private List<Long> tagIds;
}
