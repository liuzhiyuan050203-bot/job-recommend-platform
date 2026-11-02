# 技能相关 API 审计结果

- 时间（Asia/Shanghai）：2026-11-03 00:23:56 CST
- 基址：`http://localhost:8080/api`
- 账号：学生 `student` / 企业 `company`（第二企业 `uxcom1793636635` 仅用于 IDOR）
- 汇总：**PASS=19 FAIL=0**

## 检查项

| 结果 | 项目 | 关键字段（脱敏） |
| --- | --- | --- |
| PASS | 学生登录 student | token_len=193 |
| PASS | 企业登录 company | token_len=193 |
| PASS | 注册第二企业用于IDOR | companyId=241 username=uxcom1793636635 |
| PASS | 第二企业过审 | companyId=241 |
| PASS | 第二企业登录 | token_len=208 |
| PASS | 列出技能标签 GET /public/skill-tags | count=58 sample=[{"id":1,"name":"Java","direction":"后端开发"},{"id":2,"name":"Spring Boot","direction":"后端开发"},{"id":3,"name":"MySQL","direction":"后端开发"},{"id":4,"name":"Redis","direction":"后端开发"},{"id":5,"name":"Vue","direction":"前端开发"}] |
| PASS | 获取学生技能 GET /student/skills (上传前) | names=["Python","Java","Spring Boot","MySQL","Redis","Vue","Spark"] count=7 |
| PASS | 推荐列表(合并技能前) GET /student/recommend | total=20 sample=[{"positionId":10508,"title":"游戏体验设计实习生（遗忘之海）","matchScore":80.87,"reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"source":"batch"},{"positionId":10178,"title":"用户渠道运营","matchScore":64.42,"reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"source":"batch"},{"positionId":9373,"title":"嵌入式开发工程师（校招）-云帆科技","matchScore":57.65,"reason":"与你相似的同学也投递了该职位","skillNames":null,"source":"batch"},{"positionId":7081,"title":"固件开发工程师-瓯海物联","matchScore":57.40,"reason":"与你相似的同学也投递了该职位","skillNames":null,"source":"batch"},{"positionId":10451,"title":"音乐商务实习生（子弹工作室）","matchScore":56.60,"reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"source":"batch"}] |
| PASS | 上传简历 PDF POST /student/resume/upload | {"code":200,"msg":"解析完成","resumeId":677,"textPreview":"Resume - Zhang San Skills: Java, Spring Boot, MySQL, Vue, Docker, Redis Education: Bachelor CS Project: campus job recommend with Spark and RAG","skills":[{"tagId":1,"name":"Java","direction":"后端开发","evidence":"…ume - Zhang San Skills: Java, Spring Boot, MySQL, Vu…"},{"tagId":2,"name":"Spring Boot","direction":"后端开发","evidence":"…Zhang San Skills: Java, Spring Boot, MySQL, Vue, Docker, Re…"},{"tagId":3,"name":"MySQL","direction":"后端开发","evidence":"…lls: Java, Spring Boot, MySQL, Vue, Docker, Redis Edu…"},{"tagId":4,"name":"Redis","direction":"后端开发","evidence":"…ot, MySQL, Vue, Docker, Redis Education: Bachelor CS…"},{"tagId":5,"name":"Vue","direction":"前端开发","evidence":"…va, Spring Boot, MySQL, Vue, Docker, Redis Educatio…"},{"tagId":7,"name":"Spark","direction":"数据开发","evidence":"…mpus job recommend with Spark and RAG"},{"tagId":10,"name":"Docker","direction":"后端开发","evidence":"…pring Boot, MySQL, Vue, Docker, Redis Education: Bache…"}]} |
| PASS | 合并建议技能 POST /student/resume/skills | tagIds=[1,2,3,4,5,7,10] resp={"code":200,"msg":"已合并到我的技能","data":null} |
| PASS | 获取学生技能(合并后) | names=["Python","Java","Spring Boot","MySQL","Redis","Vue","Spark","Docker"] |
| PASS | 推荐列表(合并技能后) | total=20 overlap=[{"positionId":10508,"title":"游戏体验设计实习生（遗忘之海）","reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"overlap":["Java","Spring Boot","MySQL"]},{"positionId":10178,"title":"用户渠道运营","reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"overlap":["Java","Spring Boot","MySQL"]},{"positionId":9373,"title":"嵌入式开发工程师（校招）-云帆科技","reason":"与你相似的同学也投递了该职位","skillNames":null,"overlap":[]},{"positionId":7081,"title":"固件开发工程师-瓯海物联","reason":"与你相似的同学也投递了该职位","skillNames":null,"overlap":[]},{"positionId":10451,"title":"音乐商务实习生（子弹工作室）","reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"overlap":["Java","Spring Boot","MySQL"]}] |
| PASS | 企业创建职位(含 skill/tagIds) | {"id":11404,"title":"UX技能职位1793636635","tagIds":[1,3,5],"tagNames":["Java","MySQL","Vue"],"auditStatus":0} |
| PASS | 企业更新职位技能标签 | {"id":11404,"title":"UX技能职位1793636635-upd","tagIds":[1,3],"tagNames":["Java","MySQL"]} |
| PASS | 企业候选人列表 GET /company/applications | total=43 keys=["applyTime","city","companyId","companyName","education","educationName","id","jobId","jobTitle","major","nextStatuses","remark","resumeId","school","status","statusName","studentName","updateTime","userId"] sample=[{"id":2309,"studentName":"安全甲","jobTitle":"越权隔离职位1793629002","resumeId":679,"status":2,"statusName":"面试中","school":"测试大学","educationName":"本科"},{"id":2307,"studentName":"陈晓","jobTitle":"招聘流程测试1793628692","resumeId":677,"status":3,"statusName":"已录用","school":"华中科技大学","educationName":"本科"},{"id":2306,"studentName":"安全甲","jobTitle":"越权隔离职位1793628684","resumeId":675,"status":2,"statusName":"面试中","school":"测试大学","educationName":"本科"}] |
| PASS | 准备IDOR投递样本 | jobId=11405 appId=2310 resumeId=677 |
| PASS | 企业候选人详情(含skills) | {"id":2310,"studentName":"陈晓","skills":[{"id":1,"tagId":1,"tagName":"Java","proficiency":4},{"id":2,"tagId":2,"tagName":"Spring Boot","proficiency":4},{"id":3,"tagId":3,"tagName":"MySQL","proficiency":4},{"id":4,"tagId":6,"tagName":"Python","proficiency":5},{"id":5,"tagId":7,"tagName":"Spark","proficiency":3},{"id":6,"tagId":5,"tagName":"Vue","proficiency":3},{"id":7,"tagId":4,"tagName":"Redis","proficiency":4},{"id":2923,"tagId":10,"tagName":"Docker","proficiency":3}],"resumeSkillDesc":"Java","resumeId":677,"keys":["applyTime","city","companyId","companyName","education","educationName","expectCity","graduationYear","id","interviews","jobId","jobTitle","logs","major","nextStatuses","phone","remark","resume","resumeId","school","skills","status","statusName","studentName","updateTime","userId"]} |
| PASS | IDOR:其他企业不能下载申请人简历原件 | owner_http=200 owner_head=%PDF-1.4 other_http=403 |
| PASS | IDOR:其他企业不能看投递详情 | http=403 code=403 msg=无权查看该投递 |

## 补充摘录

### 上传前技能
```json
[{"id":4,"tagId":6,"tagName":"Python","proficiency":5},{"id":1,"tagId":1,"tagName":"Java","proficiency":4},{"id":2,"tagId":2,"tagName":"Spring Boot","proficiency":4},{"id":3,"tagId":3,"tagName":"MySQL","proficiency":4},{"id":7,"tagId":4,"tagName":"Redis","proficiency":4},{"id":6,"tagId":5,"tagName":"Vue","proficiency":3},{"id":5,"tagId":7,"tagName":"Spark","proficiency":3}]
```

### 解析建议技能
```json
["Java","Spring Boot","MySQL","Redis","Vue","Spark","Docker"] ids=[1,2,3,4,5,7,10]
```

### 合并后技能
```json
[{"id":4,"tagId":6,"tagName":"Python","proficiency":5},{"id":1,"tagId":1,"tagName":"Java","proficiency":4},{"id":2,"tagId":2,"tagName":"Spring Boot","proficiency":4},{"id":3,"tagId":3,"tagName":"MySQL","proficiency":4},{"id":7,"tagId":4,"tagName":"Redis","proficiency":4},{"id":6,"tagId":5,"tagName":"Vue","proficiency":3},{"id":5,"tagId":7,"tagName":"Spark","proficiency":3},{"id":2923,"tagId":10,"tagName":"Docker","proficiency":3}]
```

### 推荐（合并前）reasons
```json
["与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","与你相似的同学也投递了该职位","与你相似的同学也投递了该职位","与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位"]
```

### 推荐（合并后）与技能重叠
```json
[{"positionId":10508,"title":"游戏体验设计实习生（遗忘之海）","reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"overlap":["Java","Spring Boot","MySQL"]},{"positionId":10178,"title":"用户渠道运营","reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"overlap":["Java","Spring Boot","MySQL"]},{"positionId":9373,"title":"嵌入式开发工程师（校招）-云帆科技","reason":"与你相似的同学也投递了该职位","skillNames":null,"overlap":[]},{"positionId":7081,"title":"固件开发工程师-瓯海物联","reason":"与你相似的同学也投递了该职位","skillNames":null,"overlap":[]},{"positionId":10451,"title":"音乐商务实习生（子弹工作室）","reason":"与你的 Java/MySQL/Spring Boot 技能匹配度 67%；位于你期望的城市杭州；与你相似的同学也投递了该职位","skillNames":null,"overlap":["Java","Spring Boot","MySQL"]}]
```

### 候选人列表字段 keys
```json
["applyTime","city","companyId","companyName","education","educationName","id","jobId","jobTitle","major","nextStatuses","remark","resumeId","school","status","statusName","studentName","updateTime","userId"]
```

> 未记录 JWT / 密码。服务未停止。
