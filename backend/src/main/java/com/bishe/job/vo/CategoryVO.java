package com.bishe.job.vo;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class CategoryVO {

    private Long id;
    private Long parentId;
    private String name;
    private Integer sortNo;
    private Integer status;
    private List<CategoryVO> children = new ArrayList<>();
}
