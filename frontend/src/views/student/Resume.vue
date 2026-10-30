<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">我的在线简历</span>
          <el-button type="primary" size="small">保存简历</el-button>
        </div>
      </template>

      <el-form label-width="100px" style="max-width: 800px;">
        <el-form-item label="真实姓名">
          <el-input value="张三" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="最高学历">
          <el-select value="本科" placeholder="选择学历">
            <el-option label="专科" value="专科" />
            <el-option label="本科" value="本科" />
            <el-option label="硕士研究生" value="硕士研究生" />
            <el-option label="博士研究生" value="博士研究生" />
          </el-select>
        </el-form-item>
        <el-form-item label="毕业院校">
          <el-input value="计算机科学与技术学院" placeholder="学校与专业" />
        </el-form-item>
        <el-form-item label="技能标签">
          <div class="tags-group">
            <el-tag closable>Java</el-tag>
            <el-tag type="success" closable>Vue 3</el-tag>
            <el-tag type="warning" closable>PySpark</el-tag>
            <el-tag type="info" closable>RAG / LangChain</el-tag>
            <el-button size="small" icon="Plus">添加标签</el-button>
          </div>
        </el-form-item>
        <el-form-item label="专业经历">
          <el-input
            type="textarea"
            :rows="4"
            placeholder="项目经历、实习经验、获奖情况..."
            value="参与高校就业推荐平台研发，负责 Spark 离线推荐算法及 Vue3 前端交互界面。"
          />
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.tags-group {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
