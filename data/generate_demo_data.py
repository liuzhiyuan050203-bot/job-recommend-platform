#!/usr/bin/env python3
"""可复现的高校校园招聘演示数据生成器。

连接 MariaDB，按固定随机种子生成企业、职位、学生和行为日志。
重复运行会先删除本脚本写入的演示数据（用户名前缀 demo_、信用代码前缀 DEMO），
不触碰 seed.sql 的 admin/student/company，也不删除测试脚本留下的账号。

用法:
  /workspace/bishe/.venv/bin/python data/generate_demo_data.py
  /workspace/bishe/.venv/bin/python data/generate_demo_data.py --seed 20261031
  /workspace/bishe/.venv/bin/python data/generate_demo_data.py --clean

连接参数可用环境变量覆盖: MYSQL_HOST MYSQL_PORT MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE。
统计时间锚点固定为 2026-10-31，不随运行当天变化。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import pymysql

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "raw" / "jobs_raw.csv"

N_COMPANIES = 30
N_STUDENTS = 200
N_JOBS = 3200
DEFAULT_SEED = 20261031
ANCHOR = datetime(2026, 10, 31, 18, 0, 0)
BEHAVIOR_START = datetime(2026, 5, 1, 0, 0, 0)
BEHAVIOR_END = datetime(2026, 10, 31, 23, 59, 59)
TAXONOMY_TIME = datetime(2026, 10, 1, 9, 0, 0)
DEMO_PASSWORD = "Demo@123"
DEMO_SALT = b"$2b$10$Dem0JobPlatf0rmSalt01u"
USER_RE = r"^demo_(corp|stu)_[0-9]+$"
CREDIT_RE = r"^DEMO[0-9]{14}$"
SEED_USERNAMES = ("admin", "student", "company")

# 城市: 省份用 ECharts 地图口径；系数相对一线，二线约低 20%–35%。
CITIES = {
    "北京": ("北京", 1.00, ("海淀区", "朝阳区", "昌平区")),
    "上海": ("上海", 1.00, ("浦东新区", "徐汇区", "杨浦区")),
    "深圳": ("广东", 1.00, ("南山区", "福田区", "宝安区")),
    "广州": ("广东", 1.00, ("天河区", "海珠区", "黄埔区")),
    "杭州": ("浙江", 0.80, ("西湖区", "余杭区", "滨江区")),
    "南京": ("江苏", 0.78, ("鼓楼区", "江宁区", "雨花台区")),
    "苏州": ("江苏", 0.78, ("工业园区", "高新区", "吴中区")),
    "厦门": ("福建", 0.76, ("思明区", "湖里区", "集美区")),
    "成都": ("四川", 0.72, ("高新区", "武侯区", "锦江区")),
    "武汉": ("湖北", 0.72, ("洪山区", "东湖高新区", "江汉区")),
    "天津": ("天津", 0.72, ("南开区", "滨海新区", "河西区")),
    "西安": ("陕西", 0.70, ("雁塔区", "高新区", "长安区")),
    "长沙": ("湖南", 0.70, ("岳麓区", "雨花区", "开福区")),
    "合肥": ("安徽", 0.70, ("高新区", "蜀山区", "包河区")),
    "重庆": ("重庆", 0.70, ("渝北区", "江北区", "沙坪坝区")),
    "郑州": ("河南", 0.68, ("金水区", "高新区", "郑东新区")),
    "济南": ("山东", 0.66, ("历下区", "高新区", "市中区")),
    "青岛": ("山东", 0.66, ("市南区", "崂山区", "黄岛区")),
    "大连": ("辽宁", 0.65, ("高新园区", "沙河口区", "中山区")),
    "沈阳": ("辽宁", 0.65, ("浑南区", "和平区", "皇姑区")),
}
CITY_WEIGHTS = {
    "北京": 14, "上海": 12, "深圳": 12, "广州": 8, "杭州": 8,
    "成都": 6, "武汉": 5, "南京": 5, "西安": 4, "苏州": 4,
    "长沙": 3, "合肥": 3, "重庆": 3, "天津": 3, "厦门": 2,
    "郑州": 2, "济南": 2, "青岛": 2, "大连": 1, "沈阳": 1,
}
TIER1 = {"北京", "上海", "深圳", "广州"}

# 叶子分类名即 tech_direction / skill_tag.direction。
PARENTS = [("技术研发", 1), ("产品设计", 2)]
LEAVES = [
    ("后端开发", "技术研发", 1),
    ("前端开发", "技术研发", 2),
    ("数据开发", "技术研发", 3),
    ("人工智能", "技术研发", 4),
    ("云原生开发", "技术研发", 5),
    ("算法工程", "技术研发", 6),
    ("测试开发", "技术研发", 7),
    ("运维开发", "技术研发", 8),
    ("移动开发", "技术研发", 9),
    ("嵌入式开发", "技术研发", 10),
    ("产品经理", "产品设计", 1),
    ("UI设计", "产品设计", 2),
]
DIRECTIONS = [name for name, _parent, _sort in LEAVES]
DIR_WEIGHTS = {
    "后端开发": 18, "前端开发": 14, "数据开发": 10, "人工智能": 10,
    "算法工程": 8, "测试开发": 8, "云原生开发": 6, "移动开发": 6,
    "运维开发": 5, "产品经理": 5, "嵌入式开发": 5, "UI设计": 5,
}
# 一线、应届、本科、校招的月薪区间（元）。其他组合再乘城市、学历、经验、性质系数。
BASE_SALARY = {
    "后端开发": (15000, 25000),
    "前端开发": (14000, 23000),
    "数据开发": (16000, 27000),
    "人工智能": (18000, 32000),
    "云原生开发": (16000, 28000),
    "算法工程": (20000, 35000),
    "测试开发": (11000, 19000),
    "运维开发": (11000, 19000),
    "移动开发": (14000, 24000),
    "嵌入式开发": (12000, 21000),
    "产品经理": (13000, 23000),
    "UI设计": (10000, 18000),
}
EDU_FACTOR = {0: 0.95, 1: 0.82, 2: 1.00, 3: 1.20, 4: 1.42}
EXP_FACTOR = {0: 1.02, 1: 1.00, 2: 1.08, 3: 1.30, 4: 1.55, 5: 1.85}
TYPE_FACTOR = {1: 1.08, 2: 0.36, 3: 1.00}
EDU_NAME = {0: "学历不限", 1: "专科", 2: "本科", 3: "硕士", 4: "博士"}
EXP_NAME = {
    0: "经验不限", 1: "应届毕业生", 2: "一年以内经验",
    3: "一到三年经验", 4: "三到五年经验", 5: "五年以上经验",
}

ALL_TAGS = [
    ("Java", "后端开发"), ("Spring Boot", "后端开发"), ("MySQL", "后端开发"),
    ("Redis", "后端开发"), ("Kafka", "后端开发"), ("Go", "后端开发"),
    ("C++", "后端开发"), ("MyBatis", "后端开发"), ("Spring Cloud", "后端开发"),
    ("RabbitMQ", "后端开发"), ("Docker", "后端开发"),
    ("Vue", "前端开发"), ("React", "前端开发"), ("TypeScript", "前端开发"),
    ("JavaScript", "前端开发"), ("Node.js", "前端开发"),
    ("Python", "数据开发"), ("Spark", "数据开发"), ("Hadoop", "数据开发"),
    ("Flink", "数据开发"), ("Hive", "数据开发"), ("HBase", "数据开发"), ("SQL", "数据开发"),
    ("LangChain", "人工智能"), ("机器学习", "人工智能"), ("PyTorch", "人工智能"),
    ("TensorFlow", "人工智能"), ("Pandas", "人工智能"),
    ("Kubernetes", "云原生开发"), ("Prometheus", "云原生开发"),
    ("Jenkins", "云原生开发"), ("Git", "云原生开发"),
    ("XGBoost", "算法工程"), ("特征工程", "算法工程"),
    ("推荐系统", "算法工程"), ("深度学习", "算法工程"),
    ("Selenium", "测试开发"), ("JMeter", "测试开发"),
    ("Postman", "测试开发"), ("Pytest", "测试开发"),
    ("Linux", "运维开发"), ("Shell", "运维开发"), ("Ansible", "运维开发"),
    ("Android", "移动开发"), ("iOS", "移动开发"),
    ("Flutter", "移动开发"), ("Kotlin", "移动开发"),
    ("C语言", "嵌入式开发"), ("RTOS", "嵌入式开发"), ("STM32", "嵌入式开发"),
    ("Axure", "产品经理"), ("需求分析", "产品经理"), ("原型设计", "产品经理"),
    ("Figma", "UI设计"), ("Sketch", "UI设计"), ("交互设计", "UI设计"),
]
TAG_DIR = {}
TAGS_BY_DIR = defaultdict(list)
for _name, _direction in ALL_TAGS:
    if _name in TAG_DIR:
        raise RuntimeError(f"技能标签重名: {_name}")
    TAG_DIR[_name] = _direction
    TAGS_BY_DIR[_direction].append(_name)
# 不进入 TAGS_BY_DIR，避免改变原有标签抽样消耗的随机数。只在后期月份替换进人工智能/算法岗位。
EXTRA_TAGS = [("大模型", "人工智能")]
for _name, _direction in EXTRA_TAGS:
    if _name in TAG_DIR:
        raise RuntimeError(f"技能标签重名: {_name}")
    TAG_DIR[_name] = _direction
CROSS_TAGS = ["Docker", "Linux", "Git", "MySQL", "Python"]
RELATED = {
    "后端开发": ["云原生开发", "数据开发"],
    "前端开发": ["移动开发", "UI设计"],
    "数据开发": ["人工智能", "后端开发"],
    "人工智能": ["算法工程", "数据开发"],
    "算法工程": ["人工智能", "数据开发"],
    "云原生开发": ["运维开发", "后端开发"],
    "测试开发": ["后端开发", "运维开发"],
    "运维开发": ["云原生开发", "后端开发"],
    "移动开发": ["前端开发", "后端开发"],
    "嵌入式开发": ["后端开发", "移动开发"],
    "产品经理": ["UI设计", "数据开发"],
    "UI设计": ["产品经理", "前端开发"],
}

# name, short, industry, scale, city, slug, focus
COMPANY_SPECS = [
    ("云帆科技有限公司", "云帆科技", "互联网", 6, "北京", "yunfan", "在线协作与业务中台"),
    ("栖迟网络有限公司", "栖迟网络", "社交网络", 3, "北京", "qichi", "兴趣社区与内容分发"),
    ("极光数智有限公司", "极光数智", "人工智能", 5, "上海", "jiguang", "企业智能决策与知识引擎"),
    ("衡石安全科技有限公司", "衡石安全", "网络安全", 4, "上海", "hengshi", "应用安全与攻防演练平台"),
    ("星河云科有限公司", "星河云科", "云计算", 5, "深圳", "xinghe", "容器云与可观测平台"),
    ("知微金融科技有限公司", "知微金科", "金融科技", 5, "深圳", "zhiwei", "支付清结算与风控中台"),
    ("青禾互娱有限公司", "青禾互娱", "数字娱乐", 4, "广州", "qinghe", "休闲游戏与实时对战"),
    ("南风出行科技有限公司", "南风出行", "智能出行", 6, "广州", "nanfeng", "出行调度与地图服务"),
    ("澜舟信息有限公司", "澜舟信息", "企业服务", 4, "杭州", "lanzhou", "协同办公与低代码"),
    ("海盐电子商务有限公司", "海盐电商", "电子商务", 5, "杭州", "haiyan", "品牌零售与供应链"),
    ("沐白设计有限公司", "沐白设计", "互联网", 2, "杭州", "mubai", "体验设计与设计系统"),
    ("梧桐数据有限公司", "梧桐数据", "大数据", 4, "成都", "wutong", "离线数仓与指标平台"),
    ("听澜医疗科技有限公司", "听澜医疗", "医疗健康", 3, "成都", "tinglan", "互联网医院与随访系统"),
    ("拾光教育科技有限公司", "拾光教育", "在线教育", 3, "武汉", "shiguang", "职业教育与学习平台"),
    ("江城智联有限公司", "江城智联", "产业互联网", 4, "武汉", "jiangcheng", "制造协同与设备联网"),
    ("砚田软件有限公司", "砚田软件", "软件", 3, "南京", "yantian", "行业软件与集成交付"),
    ("金陵云测科技有限公司", "金陵云测", "软件测试", 3, "南京", "jinling", "质量中台与自动化测试"),
    ("远山智造有限公司", "远山智造", "工业软件", 4, "西安", "yuanshan", "工业仿真与生产执行"),
    ("秦云科技有限公司", "秦云科技", "云计算", 3, "西安", "qinyun", "混合云与运维平台"),
    ("北宸智能装备有限公司", "北宸智能", "智能制造", 4, "苏州", "beichen", "产线控制与边缘计算"),
    ("麓山电子有限公司", "麓山电子", "消费电子", 4, "长沙", "lushan", "智能硬件与配套应用"),
    ("澄光半导体有限公司", "澄光半导体", "半导体", 5, "合肥", "chengguang", "芯片设计配套软件"),
    ("两江数字科技有限公司", "两江数字", "政务数字化", 4, "重庆", "liangjiang", "城市治理与数据中台"),
    ("锦程物流科技有限公司", "锦程物流", "智慧物流", 5, "天津", "jincheng", "运力调度与仓储系统"),
    ("瓯海物联科技有限公司", "瓯海物联", "物联网", 3, "厦门", "ouhai", "设备接入与远程运维"),
    ("嵩岳网络有限公司", "嵩岳网络", "互联网", 3, "郑州", "songyue", "本地生活与商家服务"),
    ("朔方能源科技有限公司", "朔方能源", "能源互联网", 4, "济南", "shuofang", "能源监控与负荷预测"),
    ("岛城海洋信息有限公司", "岛城海洋", "海洋信息", 3, "青岛", "daocheng", "海洋监测与数据平台"),
    ("滨城软件有限公司", "滨城软件", "软件", 2, "大连", "bincheng", "口岸信息化与企业应用"),
    ("辽河智能科技有限公司", "辽河智能", "人工智能", 3, "沈阳", "liaohe", "工业视觉与质检算法"),
]
CONTACTS = [
    "周启明", "林知夏", "陈景行", "赵清和", "孙亦安", "吴承志", "郑晓舟", "王叙白", "冯嘉树", "陈望舒",
    "褚明远", "卫星澜", "蒋南枝", "沈予安", "韩清越", "杨书衡", "朱晚宁", "秦牧之", "许知行", "何清晏",
    "吕景澄", "施予怀", "张叙之", "孔令仪", "曹予白", "严清和", "华景行", "金夏至", "魏知远", "陶安宁",
]
ROLES = {
    "后端开发": ["Java后端开发工程师", "服务端开发工程师", "业务中台开发工程师", "Spring Boot后端工程师"],
    "前端开发": ["前端开发工程师", "Vue前端工程师", "Web前端工程师", "React前端工程师"],
    "数据开发": ["大数据开发工程师", "数据开发工程师", "实时计算工程师", "数仓开发工程师"],
    "人工智能": ["机器学习工程师", "AI应用开发工程师", "NLP工程师", "智能应用工程师"],
    "云原生开发": ["云原生开发工程师", "容器平台开发工程师", "DevOps开发工程师"],
    "算法工程": ["算法工程师", "推荐算法工程师", "搜索算法工程师", "机器学习算法工程师"],
    "测试开发": ["测试开发工程师", "自动化测试工程师", "质量效能工程师"],
    "运维开发": ["运维开发工程师", "SRE开发工程师", "运维平台工程师"],
    "移动开发": ["Android开发工程师", "iOS开发工程师", "Flutter开发工程师", "移动端开发工程师"],
    "嵌入式开发": ["嵌入式软件工程师", "嵌入式开发工程师", "固件开发工程师"],
    "产品经理": ["产品经理", "B端产品经理", "校园产品经理", "数据产品经理"],
    "UI设计": ["UI设计师", "体验设计师", "视觉设计师", "交互设计师"],
}
WELFARE_POOL = ["五险一金", "补充公积金", "带薪年假", "年度体检", "餐补", "住房补贴", "免费班车", "弹性工作", "节日福利", "定期团建", "通讯补贴", "年度旅游"]
SCHOOLS = [
    ("滨海理工大学", "计算机学院"), ("江城大学", "软件学院"), ("临江学院", "信息工程学院"),
    ("星海工业大学", "计算机科学与技术学院"), ("南山大学", "电子信息学院"), ("西湖科技大学", "计算机学院"),
    ("锦官大学", "软件学院"), ("汉口理工大学", "人工智能学院"), ("金陵软件学院", "软件工程学院"),
    ("长安电子科技大学", "计算机学院"), ("湘江大学", "信息科学与工程学院"), ("庐州学院", "大数据学院"),
    ("山城大学", "计算机学院"), ("渤海理工大学", "软件学院"), ("鹭岛大学", "信息学院"),
    ("嵩岳师范大学", "计算机与信息工程学院"), ("泉城大学", "软件学院"), ("琴岛学院", "信息工程学院"),
    ("辽东大学", "计算机学院"), ("沈水理工大学", "软件学院"),
]
MAJORS = {
    "后端开发": ["软件工程", "计算机科学与技术"],
    "前端开发": ["软件工程", "数字媒体技术"],
    "数据开发": ["数据科学与大数据技术", "计算机科学与技术"],
    "人工智能": ["人工智能", "智能科学与技术"],
    "云原生开发": ["软件工程", "网络工程"],
    "算法工程": ["人工智能", "计算机科学与技术"],
    "测试开发": ["软件工程", "计算机科学与技术"],
    "运维开发": ["网络工程", "软件工程"],
    "移动开发": ["软件工程", "物联网工程"],
    "嵌入式开发": ["电子信息工程", "物联网工程"],
    "产品经理": ["信息管理与信息系统", "软件工程"],
    "UI设计": ["数字媒体技术", "视觉传达设计"],
}
SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜")
MALE_GIVEN = ["子轩", "浩然", "俊杰", "博文", "天佑", "明轩", "宇航", "嘉懿", "煜城", "睿渊", "弘文", "哲瀚", "皓轩", "致远", "峻熙", "文博", "昊然", "景行", "修杰", "楷瑞"]
FEMALE_GIVEN = ["一诺", "欣怡", "雨桐", "诗涵", "可馨", "梦琪", "若溪", "清妍", "芷若", "晓彤", "佳宁", "思琪", "婉婷", "静怡", "雨涵", "欣妍", "梓涵", "雅琴", "安然", "语汐"]
PROJECTS = ["校园二手交易平台", "实验室设备预约系统", "课程作业互评站", "社团活动报名小程序", "校园食堂评价榜", "毕业论文选题助手"]


def _check_catalog() -> None:
    if len(COMPANY_SPECS) != N_COMPANIES or len(CONTACTS) != N_COMPANIES:
        raise RuntimeError("企业目录数量不正确")
    if set(CITY_WEIGHTS) != set(CITIES):
        raise RuntimeError("城市权重与城市表不一致")
    if sum(CITY_WEIGHTS.values()) != 100 or sum(DIR_WEIGHTS.values()) != 100:
        raise RuntimeError("权重之和不是 100")
    if set(DIR_WEIGHTS) != set(DIRECTIONS) or set(BASE_SALARY) != set(DIRECTIONS):
        raise RuntimeError("方向配置不完整")
    missing_city = {spec[4] for spec in COMPANY_SPECS} - set(CITIES)
    if missing_city:
        raise RuntimeError(f"企业城市未定义: {missing_city}")
    if {spec[4] for spec in COMPANY_SPECS} != set(CITIES):
        raise RuntimeError("有城市没有对应企业")
    for direction in DIRECTIONS:
        if len(TAGS_BY_DIR[direction]) < 3:
            raise RuntimeError(f"{direction} 技能标签少于 3 个")
        for rel in RELATED[direction]:
            if rel not in DIRECTIONS:
                raise RuntimeError(f"关联方向不存在: {rel}")
    if not (50 <= len(ALL_TAGS) <= 60):
        raise RuntimeError(f"技能标签数量 {len(ALL_TAGS)} 不在 50–60")
    if len(DEMO_SALT) != 29:
        raise RuntimeError("BCrypt 盐长度不正确")


_check_catalog()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成高校就业推荐平台演示数据")
    parser.add_argument("--clean", action="store_true", help="只删除演示数据，不重新插入")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"随机种子，默认 {DEFAULT_SEED}")
    return parser.parse_args()


def db_config() -> dict:
    port_text = os.environ.get("MYSQL_PORT", "3306")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise SystemExit(f"MYSQL_PORT 不是整数: {port_text}") from exc
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": port,
        "user": os.environ.get("MYSQL_USER", "job"),
        "password": os.environ.get("MYSQL_PASSWORD", "job123"),
        "database": os.environ.get("MYSQL_DATABASE", "job_platform"),
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": 10,
        "read_timeout": 180,
        "write_timeout": 180,
    }


def connect():
    cfg = db_config()
    try:
        return pymysql.connect(**cfg)
    except pymysql.MySQLError as exc:
        raise SystemExit(f"连接数据库失败 {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}: {exc}") from exc


def password_hash() -> str:
    hashed = bcrypt.hashpw(DEMO_PASSWORD.encode(), DEMO_SALT).decode()
    if not bcrypt.checkpw(DEMO_PASSWORD.encode(), hashed.encode()):
        raise RuntimeError("BCrypt 自检失败")
    return hashed


def weighted_choice(rng: random.Random, labels: list, weights: list):
    return rng.choices(labels, weights=weights, k=1)[0]


def expand_quota(total: int, weights: dict) -> list:
    names = list(weights)
    weight_sum = sum(weights.values())
    raw = [total * weights[name] / weight_sum for name in names]
    counts = [int(value) for value in raw]
    left = total - sum(counts)
    order = sorted(range(len(names)), key=lambda i: (raw[i] - counts[i], -i), reverse=True)
    for i in range(left):
        counts[order[i]] += 1
    output = []
    for name, count in zip(names, counts):
        output.extend([name] * count)
    if len(output) != total:
        raise RuntimeError("配额展开失败")
    return output


def round_salary(value: float) -> int:
    return int(round(value / 500.0)) * 500


def chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def choose_job_tags(rng: random.Random, direction: str) -> list[str]:
    same = TAGS_BY_DIR[direction][:]
    rng.shuffle(same)
    upper = min(6, len(same) + 1)
    count = rng.randint(3, upper)
    cross = 1 if count > 3 and rng.random() < 0.45 else 0
    same_count = min(len(same), count - cross)
    chosen = same[:same_count]
    if cross and len(chosen) < 6:
        pool = [name for name in CROSS_TAGS if name not in chosen and TAG_DIR[name] != direction]
        if pool:
            chosen.append(rng.choice(pool))
    return chosen


def choose_student_skills(rng: random.Random, direction: str) -> list[tuple[str, int]]:
    same = TAGS_BY_DIR[direction][:]
    rng.shuffle(same)
    related = []
    for other in RELATED[direction]:
        related.extend(TAGS_BY_DIR[other])
    rng.shuffle(related)
    count = rng.randint(3, 8)
    cross = 0
    if count >= 5 and related and rng.random() < 0.55:
        cross = 1
    if count >= 7 and len(related) > 1 and rng.random() < 0.4:
        cross = min(2, cross + 1)
    same_count = min(len(same), max(3, count - cross))
    while cross > 0 and same_count <= cross:
        cross -= 1
    chosen = same[:same_count]
    have = set(chosen)
    added = 0
    for name in related:
        if added >= cross:
            break
        if name not in have:
            chosen.append(name)
            have.add(name)
            added += 1
    levels = []
    for index, _name in enumerate(chosen):
        if index < same_count:
            levels.append(rng.randint(3, 5))
        else:
            levels.append(rng.randint(1, 3))
    return list(zip(chosen, levels))


def build_companies() -> list[dict]:
    companies = []
    for index, spec in enumerate(COMPANY_SPECS):
        name, short, industry, scale, city, slug, focus = spec
        province, _factor, districts = CITIES[city]
        created = datetime(2025, 9, 1, 10, 0, 0) + timedelta(days=index, hours=index % 5)
        companies.append({
            "username": f"demo_corp_{index + 1:02d}",
            "nickname": f"{short}招聘",
            "phone": f"1391000{index + 1:04d}",
            "email": f"hr{index + 1:02d}@{slug}.example",
            "company_name": name,
            "short_name": short,
            "industry": industry,
            "scale": scale,
            "province": province,
            "city": city,
            "address": f"{city}市{districts[0]}科技园路{18 + index * 6}号",
            "website": f"https://www.{slug}.example",
            "intro": f"{short}专注{industry}，{focus}。研发中心位于{city}，面向高校招聘应届生与实习生。",
            "credit_code": f"DEMO{index + 1:014d}",
            "contact_name": CONTACTS[index],
            "contact_phone": f"1391000{index + 1:04d}",
            "contact_email": f"hr{index + 1:02d}@{slug}.example",
            "create_time": created,
            "audit_time": created + timedelta(days=2),
        })
    return companies


def salary_band(rng: random.Random, direction: str, city: str, education: int, experience: int, job_type: int) -> tuple[int, int, int]:
    base_min, base_max = BASE_SALARY[direction]
    factor = CITIES[city][1] * EDU_FACTOR[education] * EXP_FACTOR[experience] * TYPE_FACTOR[job_type]
    jitter = 0.98 + rng.random() * 0.04
    low = max(2500, round_salary(base_min * factor * jitter))
    high = max(low + (1000 if job_type == 2 else 2000), round_salary(base_max * factor * jitter))
    if job_type == 2:
        months = 12
    else:
        months = weighted_choice(rng, [12, 13, 14, 15, 16], [12, 34, 30, 16, 8])
    return low, high, months


def build_jobs(rng: random.Random, companies: list[dict]) -> list[dict]:
    directions = expand_quota(N_JOBS, DIR_WEIGHTS)
    rng.shuffle(directions)
    company_index = [i % N_COMPANIES for i in range(N_JOBS)]
    rng.shuffle(company_index)
    # 这里仍按均匀月份消耗随机数，保证薪资、城市、方向抽样与改动前一致。
    # 真正的发布时间在行为生成之后由 reshape_calendar 改成春招/秋招波动。
    months_ago = expand_quota(N_JOBS, {month: 1 for month in range(12)})
    rng.shuffle(months_ago)
    city_names = list(CITY_WEIGHTS)
    city_weights = [CITY_WEIGHTS[name] for name in city_names]
    jobs = []
    for index in range(N_JOBS):
        direction = directions[index]
        company = companies[company_index[index]]
        if rng.random() < 0.45:
            city = company["city"]
        else:
            city = weighted_choice(rng, city_names, city_weights)
        province, _factor, districts = CITIES[city]
        district = rng.choice(districts)
        job_type = weighted_choice(rng, [3, 2, 1], [50, 28, 22])
        if job_type == 2:
            education = weighted_choice(rng, [1, 2, 3], [18, 72, 10])
            experience = weighted_choice(rng, [0, 1, 2], [20, 60, 20])
            headcount = rng.randint(1, 8)
        elif job_type == 3:
            education = weighted_choice(rng, [0, 1, 2, 3, 4], [8, 6, 58, 24, 4])
            experience = weighted_choice(rng, [0, 1, 2], [22, 68, 10])
            headcount = rng.randint(3, 20)
        else:
            education = weighted_choice(rng, [0, 1, 2, 3, 4], [10, 8, 52, 25, 5])
            experience = weighted_choice(rng, [0, 2, 3, 4, 5], [10, 18, 40, 22, 10])
            headcount = rng.randint(1, 5)
        salary_min, salary_max, months = salary_band(rng, direction, city, education, experience, job_type)
        tags = choose_job_tags(rng, direction)
        role = rng.choice(ROLES[direction])
        suffix = {1: "", 2: "（实习）", 3: "（校招）"}[job_type]
        title = f"{role}{suffix}-{company['short_name']}"
        year = ANCHOR.year
        month = ANCHOR.month - months_ago[index]
        while month <= 0:
            month += 12
            year -= 1
        publish = datetime(year, month, 1 + rng.randrange(27), 9 + rng.randrange(10), rng.randrange(60), 0)
        create_time = publish - timedelta(days=1 + rng.randrange(7), hours=rng.randrange(6))
        if create_time < company["create_time"]:
            create_time = company["create_time"] + timedelta(hours=2)
        shelf = 0 if rng.random() < 0.04 else 1
        welfare = "、".join(rng.sample(WELFARE_POOL, rng.randint(4, 6)))
        skill_text = "、".join(tags[:4])
        jobs.append({
            "company_index": company_index[index],
            "category": direction,
            "title": title,
            "direction": direction,
            "province": province,
            "city": city,
            "district": district,
            "address": f"{city}市{district}{rng.choice(['科技园路', '软件大道', '创新路', '科苑路', '学府路'])}{rng.randint(8, 188)}号",
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_months": months,
            "education": education,
            "experience_req": experience,
            "job_type": job_type,
            "headcount": headcount,
            "description": (
                f"1. 负责{direction}相关功能的设计与编码，参与{city}研发团队的日常迭代；\n"
                f"2. 基于{skill_text}完成模块开发、联调与问题排查；\n"
                f"3. 编写必要的设计说明和单元测试，保证接口稳定；\n"
                f"4. 与产品、测试同学协作，按项目节奏交付需求。"
            ),
            "requirement": (
                f"1. {EDU_NAME[education]}，{EXP_NAME[experience]}，计算机或相关专业优先；\n"
                f"2. 掌握{skill_text}，具备清晰的编码与沟通习惯；\n"
                f"3. 有课程项目、竞赛或实习经历者优先；\n"
                f"4. 能接受{city}工作，愿意在团队中持续改进。"
            ),
            "welfare": welfare,
            "shelf_status": shelf,
            "publish_time": publish,
            "create_time": create_time,
            "tag_names": tags,
            "view_count": 0,
            "favorite_count": 0,
            "apply_count": 0,
        })
    return jobs


def build_students(rng: random.Random) -> list[dict]:
    students = []
    city_names = list(CITY_WEIGHTS)
    city_weights = [CITY_WEIGHTS[name] for name in city_names]
    dir_names = list(DIR_WEIGHTS)
    dir_weights = [DIR_WEIGHTS[name] for name in dir_names]
    for index in range(N_STUDENTS):
        direction = weighted_choice(rng, dir_names, dir_weights)
        city = weighted_choice(rng, city_names, city_weights)
        if rng.random() < 0.8:
            secondary = rng.choice(RELATED[direction])
        else:
            secondary = rng.choice([name for name in DIRECTIONS if name != direction])
        education = weighted_choice(rng, [2, 3, 1, 4], [70, 22, 6, 2])
        grad_year = weighted_choice(rng, [2025, 2026, 2027], [15, 70, 15])
        gender = 1 if rng.random() < 0.55 else 2
        given = rng.choice(MALE_GIVEN if gender == 1 else FEMALE_GIVEN)
        real_name = rng.choice(SURNAMES) + given
        school, college = rng.choice(SCHOOLS)
        major = rng.choice(MAJORS[direction])
        skills = choose_student_skills(rng, direction)
        age = {1: 22, 2: 22, 3: 25, 4: 28}[education]
        birthday = datetime(grad_year - age, 1 + rng.randrange(12), 1 + rng.randrange(28)).date()
        factor = CITIES[city][1] * EDU_FACTOR[education]
        base_min, base_max = BASE_SALARY[direction]
        expect_min = max(3000, round_salary(base_min * factor * 0.90))
        expect_max = max(expect_min + 2000, round_salary(base_max * factor * 1.05))
        skill_text = "、".join(name for name, _level in skills[:4])
        created = datetime(2026, 3, 1, 9, 0, 0) + timedelta(hours=index * 3)
        students.append({
            "username": f"demo_stu_{index + 1:03d}",
            "nickname": real_name,
            "phone": f"1392000{index + 1:04d}",
            "email": f"demo_stu_{index + 1:03d}@stu.example",
            "real_name": real_name,
            "gender": gender,
            "birthday": birthday,
            "student_no": f"D{grad_year}{index + 1:05d}",
            "school": school,
            "college": college,
            "major": major,
            "education": education,
            "graduation_year": grad_year,
            "city": city,
            "direction": direction,
            "secondary": secondary,
            "expect_salary_min": expect_min,
            "expect_salary_max": expect_max,
            "skills": skills,
            "self_intro": f"{school}{major}{EDU_NAME[education]}，{grad_year}届，期望在{city}从事{direction}。熟悉{skill_text}。",
            "create_time": created,
            "audit_time": created + timedelta(days=1),
        })
    return students


def behavior_time(rng: random.Random, publish: datetime) -> datetime:
    start = publish if publish > BEHAVIOR_START else BEHAVIOR_START
    if start >= BEHAVIOR_END:
        return BEHAVIOR_END
    span = int((BEHAVIOR_END - start).total_seconds())
    if span <= 1:
        return start
    return start + timedelta(seconds=rng.randrange(span))


def pick_biased(rng: random.Random, pool: list[int]) -> int:
    core = min(20, len(pool))
    if rng.random() < 0.70:
        return pool[rng.randrange(core)]
    return pool[rng.randrange(len(pool))]


def sample_biased(rng: random.Random, pool: list[int], count: int) -> list[int]:
    if not pool or count <= 0:
        return []
    count = min(count, len(pool))
    core_n = min(20, len(pool))
    from_core = min(count, core_n, max(1, int(round(count * 0.70))))
    chosen = rng.sample(pool[:core_n], from_core)
    rest = [job_index for job_index in pool if job_index not in chosen]
    need = count - len(chosen)
    if need > 0 and rest:
        chosen.extend(rng.sample(rest, min(need, len(rest))))
    return chosen


def build_behaviors(rng: random.Random, students: list[dict], jobs: list[dict]):
    on_shelf = [index for index, job in enumerate(jobs) if job["shelf_status"] == 1]
    by_dir_city = defaultdict(list)
    by_dir = defaultdict(list)
    for index in on_shelf:
        job = jobs[index]
        by_dir_city[(job["direction"], job["city"])].append(index)
        by_dir[job["direction"]].append(index)
    behaviors = []
    favorites = []
    applications = []
    for student_index, student in enumerate(students):
        primary = by_dir_city.get((student["direction"], student["city"])) or []
        if len(primary) < 12:
            primary = by_dir.get(student["direction"]) or on_shelf
        secondary = by_dir.get(student["secondary"]) or on_shelf
        n_view = 90 + rng.randrange(31)
        n_fav = 8 + rng.randrange(7)
        n_apply = 2 + rng.randrange(4)
        view_jobs = []
        for _ in range(n_view):
            roll = rng.random()
            if roll < 0.82:
                pool = primary
            elif roll < 0.94:
                pool = secondary
            else:
                pool = on_shelf
            view_jobs.append(pick_biased(rng, pool))
        fav_jobs = sample_biased(rng, primary, n_fav)
        viewed = set(view_jobs)
        for job_index in fav_jobs:
            if job_index not in viewed:
                view_jobs.append(job_index)
                viewed.add(job_index)
        apply_jobs = rng.sample(fav_jobs, min(n_apply, len(fav_jobs)))
        for job_index in view_jobs:
            behaviors.append((student_index, 1, job_index, 1, behavior_time(rng, jobs[job_index]["publish_time"])))
        for job_index in fav_jobs:
            when = behavior_time(rng, jobs[job_index]["publish_time"])
            behaviors.append((student_index, 2, job_index, 3, when))
            favorites.append((student_index, job_index, when))
        for job_index in apply_jobs:
            when = behavior_time(rng, jobs[job_index]["publish_time"])
            behaviors.append((student_index, 3, job_index, 5, when))
            applications.append((student_index, job_index, when))
    view_counter, fav_counter, apply_counter = Counter(), Counter(), Counter()
    for _student, behavior_type, job_index, _weight, _when in behaviors:
        if behavior_type == 1:
            view_counter[job_index] += 1
        elif behavior_type == 2:
            fav_counter[job_index] += 1
        else:
            apply_counter[job_index] += 1
    for index, job in enumerate(jobs):
        job["view_count"] = view_counter[index]
        job["favorite_count"] = fav_counter[index]
        job["apply_count"] = apply_counter[index]
    behaviors.sort(key=lambda item: (item[4], item[0], item[1], item[2]))
    favorites.sort(key=lambda item: (item[2], item[0], item[1]))
    applications.sort(key=lambda item: (item[2], item[0], item[1]))
    return behaviors, favorites, applications


def build_csv_rows(companies: list[dict], jobs: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed + 97)
    edu_text = {
        0: ["学历不限", "不限", "学历不限"],
        1: ["大专", "专科及以上", "大专及以上"],
        2: ["本科", "本科及以上", "统招本科"],
        3: ["硕士", "硕士及以上", "研究生"],
        4: ["博士", "博士研究生", "博士及以上"],
    }
    exp_text = {
        0: ["经验不限", "不限"],
        1: ["应届生", "在校/应届", "应届毕业生"],
        2: ["1年以内", "一年以内"],
        3: ["1-3年", "一到三年"],
        4: ["3-5年", "三到五年"],
        5: ["5年以上", "五年以上"],
    }
    direction_alias = {
        "后端开发": "后端", "前端开发": "前端", "数据开发": "大数据",
        "人工智能": "AI", "云原生开发": "云计算", "算法工程": "算法",
        "测试开发": "测试", "运维开发": "运维", "移动开发": "移动端",
        "嵌入式开发": "嵌入式", "产品经理": "产品", "UI设计": "UI",
    }
    rows = []
    for job in jobs:
        company = companies[job["company_index"]]
        style = rng.randrange(8)
        low, high, months = job["salary_min"], job["salary_max"], job["salary_months"]
        k_low = low / 1000
        k_high = high / 1000

        def k_text(value: float) -> str:
            rounded = round(value, 1)
            if abs(rounded - int(rounded)) < 0.05:
                return str(int(rounded))
            return f"{rounded:.1f}"

        if job["job_type"] == 2 and style in (0, 1):
            style = 4
        if style == 0:
            salary = f"{k_text(k_low)}-{k_text(k_high)}K·{months}薪"
        elif style == 1:
            salary = f"{k_text(k_low)}-{k_text(k_high)}k"
        elif style == 2:
            salary = f"{low}-{high}元/月"
        elif style == 3:
            salary = f"{k_low:.1f}-{k_high:.1f}万/月"
        elif style == 4:
            salary = f"{max(80, int(low / 21.75))}-{max(100, int(high / 21.75))}元/天"
        elif style == 5:
            salary = f"{max(1, round(low * months / 10000))}-{max(2, round(high * months / 10000))}万/年"
        elif style == 6:
            salary = "面议"
        else:
            salary = f"{k_text(k_low)}-{k_text(k_high)}K"
        city_style = rng.randrange(6)
        city, district, province = job["city"], job["district"], job["province"]
        if city_style == 0:
            city_text = city
        elif city_style == 1:
            city_text = city + "市"
        elif city_style == 2:
            city_text = f"{city} {district}"
        elif city_style == 3:
            city_text = f"{city}市{district}"
        elif city_style == 4:
            city_text = city + "市" if province == city else f"{province}{city}"
        else:
            city_text = f"{city}-{district}"
        education = rng.choice(edu_text[job["education"]])
        experience = rng.choice(exp_text[job["experience_req"]])
        separator = rng.choice([",", "/", "、", ", "])
        tags = separator.join(job["tag_names"])
        published = job["publish_time"]
        date_style = rng.randrange(6)
        if date_style == 0:
            publish_date = published.strftime("%Y-%m-%d")
        elif date_style == 1:
            publish_date = f"{published.year}/{published.month}/{published.day}"
        elif date_style == 2:
            publish_date = f"{published.year}.{published.month}.{published.day}"
        elif date_style == 3:
            publish_date = f"{published.year}年{published.month}月{published.day}日"
        elif date_style == 4:
            publish_date = published.strftime("%Y%m%d")
        else:
            publish_date = published.strftime("%m/%d/%Y")
        direction = job["direction"]
        roll_salary = rng.random()
        roll_city = rng.random()
        roll_edu = rng.random()
        roll_exp = rng.random()
        roll_tags = rng.random()
        roll_date = rng.random()
        roll_direction = rng.random()
        if roll_salary < 0.020:
            salary = ""
        elif roll_salary < 0.030:
            salary = rng.choice(["-5-10K", "999-1K", "0元", "薪资面议??", "1-2元/月"])
        if roll_city < 0.012:
            city_text = ""
        elif roll_city < 0.018:
            city_text = rng.choice(["火星市", "北京/上海", "N/A", "远程/未知"])
        if roll_edu < 0.012:
            education = ""
        elif roll_edu < 0.016:
            education = rng.choice(["小学", "不限学历及以上", "其他"])
        if roll_exp < 0.008:
            experience = ""
        elif roll_exp < 0.012:
            experience = rng.choice(["10-20年", "经验丰富", "在读博士后"])
        if roll_tags < 0.015:
            tags = ""
        if roll_date < 0.008:
            publish_date = rng.choice(["2026-13-40", "昨天", "0000-00-00", ""])
        if roll_direction < 0.030:
            direction = direction_alias[job["direction"]]
        rows.append({
            "title": job["title"],
            "company": company["company_name"],
            "city": city_text,
            "salary_text": salary,
            "education_text": education,
            "experience_text": experience,
            "tags": tags,
            "publish_date": publish_date,
            "direction": direction,
        })
    duplicate_count = round(len(rows) * 0.05)
    duplicates = [dict(rows[index]) for index in rng.sample(range(len(rows)), duplicate_count)]
    return rows + duplicates


# 2025-11 到 2026-10。权重体现温和增长，以及 3 月春招、9–10 月秋招。
PUBLISH_MONTHS = [
    (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4),
    (2026, 5), (2026, 6), (2026, 7), (2026, 8), (2026, 9), (2026, 10),
]
SEASON_WEIGHT = [0.82, 0.74, 0.88, 0.96, 1.48, 1.06, 0.98, 0.92, 0.90, 1.02, 1.52, 1.58]
RISING_DIRECTIONS = {"人工智能", "算法工程"}
FALLING_DIRECTIONS = {"测试开发"}
AI_SWAP_TAGS = ["机器学习", "TensorFlow", "Pandas", "LangChain", "深度学习", "特征工程", "推荐系统", "XGBoost"]


def month_weights_for(direction: str) -> dict[int, float]:
    weights = {}
    last = len(SEASON_WEIGHT) - 1
    for index, base in enumerate(SEASON_WEIGHT):
        progress = index / last
        if direction in RISING_DIRECTIONS:
            bias = 0.42 + 1.40 * progress
        elif direction in FALLING_DIRECTIONS:
            bias = 1.50 - 0.90 * progress
        else:
            bias = 0.90 + 0.20 * progress
        weights[index] = base * bias
    return weights


def shift_publish(job: dict, companies: list[dict], year: int, month: int) -> None:
    old = job["publish_time"]
    gap = old - job["create_time"]
    new_pub = old.replace(year=year, month=month)
    job["publish_time"] = new_pub
    job["create_time"] = new_pub - gap
    company_created = companies[job["company_index"]]["create_time"]
    if job["create_time"] < company_created:
        job["create_time"] = min(company_created + timedelta(hours=2), new_pub)
    if job["create_time"] > job["publish_time"]:
        job["create_time"] = job["publish_time"]


def reshape_calendar(companies, jobs, behaviors, favorites, applications, seed: int):
    """只改发布月份和行为时间。职位属性与行为条数沿用原随机序列。"""
    rng = random.Random(seed + 7919)
    by_dir: dict[str, list] = defaultdict(list)
    for job in jobs:
        by_dir[job["direction"]].append(job)
    for direction, group in by_dir.items():
        slots = expand_quota(len(group), month_weights_for(direction))
        rng.shuffle(slots)
        for job, slot in zip(group, slots):
            year, month = PUBLISH_MONTHS[slot]
            shift_publish(job, companies, year, month)
    side = random.Random(seed + 404)
    new_behaviors = []
    fav_time = {}
    apply_time = {}
    for student_index, behavior_type, job_index, weight, _when in behaviors:
        when = behavior_time(side, jobs[job_index]["publish_time"])
        new_behaviors.append((student_index, behavior_type, job_index, weight, when))
        if behavior_type == 2:
            fav_time[(student_index, job_index)] = when
        elif behavior_type == 3:
            apply_time[(student_index, job_index)] = when
    new_behaviors.sort(key=lambda item: (item[4], item[0], item[1], item[2]))
    new_favorites = [(student, job_index, fav_time[(student, job_index)]) for student, job_index, _when in favorites]
    new_applications = [(student, job_index, apply_time[(student, job_index)]) for student, job_index, _when in applications]
    new_favorites.sort(key=lambda item: (item[2], item[0], item[1]))
    new_applications.sort(key=lambda item: (item[2], item[0], item[1]))
    return new_behaviors, new_favorites, new_applications


def _swap_tag(tags: list[str], direction: str, unwanted: str, replacements: list[str]) -> list[str]:
    if unwanted not in tags:
        return tags
    for name in replacements:
        if name in tags or name not in TAG_DIR or TAG_DIR[name] != direction:
            continue
        return [name if current == unwanted else current for current in tags]
    return tags


def _place_tag(tags: list[str], direction: str, tag: str) -> list[str] | None:
    """用替换保持每个职位的标签数量不变，并满足本方向标签占多数。"""
    if tag in tags:
        return tags
    if tag not in TAG_DIR:
        return None
    candidates = []
    for index, name in enumerate(tags):
        if name in ("PyTorch", "大模型"):
            continue
        trial = tags[:index] + [tag] + tags[index + 1:]
        if len(set(trial)) != len(trial):
            continue
        same = sum(1 for current in trial if TAG_DIR[current] == direction)
        if same * 2 < len(trial):
            continue
        prefer_cross = 1 if TAG_DIR[name] != direction else 0
        candidates.append((prefer_cross, index, trial))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def apply_hot_skill_trend(jobs: list[dict], seed: int) -> None:
    """人工智能/算法岗位上，大模型和 PyTorch 的出现比例随月份上升。"""
    rng = random.Random(seed + 202603)
    for job in jobs:
        direction = job["direction"]
        if direction not in RISING_DIRECTIONS:
            continue
        month_index = PUBLISH_MONTHS.index((job["publish_time"].year, job["publish_time"].month))
        progress = month_index / (len(PUBLISH_MONTHS) - 1)
        tags = list(job["tag_names"])
        if progress < 0.4:
            if rng.random() < 0.9:
                tags = _swap_tag(tags, direction, "PyTorch", AI_SWAP_TAGS)
            if rng.random() < 0.95:
                tags = _swap_tag(tags, direction, "大模型", AI_SWAP_TAGS)
        if rng.random() < 0.05 + 0.93 * progress:
            placed = _place_tag(tags, direction, "PyTorch")
            if placed is not None:
                tags = placed
        if rng.random() < 0.02 + 0.96 * progress:
            placed = _place_tag(tags, direction, "大模型")
            if placed is not None:
                tags = placed
        job["tag_names"] = tags


def generate(seed: int) -> dict:
    rng = random.Random(seed)
    companies = build_companies()
    jobs = build_jobs(rng, companies)
    students = build_students(rng)
    behaviors, favorites, applications = build_behaviors(rng, students, jobs)
    behaviors, favorites, applications = reshape_calendar(
        companies, jobs, behaviors, favorites, applications, seed,
    )
    apply_hot_skill_trend(jobs, seed)
    csv_rows = build_csv_rows(companies, jobs, seed)
    return {
        "companies": companies,
        "jobs": jobs,
        "students": students,
        "behaviors": behaviors,
        "favorites": favorites,
        "applications": applications,
        "csv_rows": csv_rows,
    }


def validate(payload: dict) -> None:
    companies, jobs = payload["companies"], payload["jobs"]
    students, behaviors = payload["students"], payload["behaviors"]
    favorites, applications = payload["favorites"], payload["applications"]
    if len(companies) != N_COMPANIES or len(students) != N_STUDENTS or len(jobs) != N_JOBS:
        raise RuntimeError("企业、学生或职位数量不正确")
    if not (20000 <= len(behaviors) <= 40000):
        raise RuntimeError(f"行为日志 {len(behaviors)} 条，不在 2–4 万")
    if len({job["city"] for job in jobs}) != len(CITIES):
        raise RuntimeError("职位没有覆盖全部城市")
    months = {job["publish_time"].strftime("%Y-%m") for job in jobs}
    if len(months) != 12:
        raise RuntimeError(f"发布月份只有 {len(months)} 个")
    off_shelf = sum(1 for job in jobs if job["shelf_status"] == 0)
    if not (40 <= off_shelf <= 250):
        raise RuntimeError(f"下架职位 {off_shelf} 个，不在预期范围")
    for job in jobs:
        if job["salary_max"] < job["salary_min"] or not (12 <= job["salary_months"] <= 16):
            raise RuntimeError(f"薪资不合法: {job['title']}")
        if not (3 <= len(job["tag_names"]) <= 6):
            raise RuntimeError(f"职位标签数量不在 3–6: {job['title']}")
        same = sum(1 for name in job["tag_names"] if TAG_DIR[name] == job["direction"])
        if same * 2 < len(job["tag_names"]):
            raise RuntimeError(f"职位标签未以本方向为主: {job['title']}")
        if job["create_time"] > job["publish_time"]:
            raise RuntimeError("职位创建时间晚于发布时间")
        if job["shelf_status"] == 0 and (job["view_count"] or job["favorite_count"] or job["apply_count"]):
            raise RuntimeError("下架职位仍有行为计数")
        if job["publish_time"] < datetime(2025, 11, 1) or job["publish_time"] > BEHAVIOR_END:
            raise RuntimeError("发布时间超出最近 12 个月")
    for student in students:
        if not (3 <= len(student["skills"]) <= 8):
            raise RuntimeError(f"学生技能数量不在 3–8: {student['username']}")
        if student["expect_salary_max"] < student["expect_salary_min"]:
            raise RuntimeError("期望薪资区间非法")
    fav_pairs = [(item[0], item[1]) for item in favorites]
    apply_pairs = [(item[0], item[1]) for item in applications]
    if len(fav_pairs) != len(set(fav_pairs)) or len(apply_pairs) != len(set(apply_pairs)):
        raise RuntimeError("收藏或投递出现重复")
    if not set(apply_pairs) <= set(fav_pairs):
        raise RuntimeError("投递没有落在收藏集合内")
    views, favs, applies = Counter(), Counter(), Counter()
    for student_index, behavior_type, job_index, weight, when in behaviors:
        expect_weight = {1: 1, 2: 3, 3: 5}[behavior_type]
        if weight != expect_weight:
            raise RuntimeError("行为权重不正确")
        if when < jobs[job_index]["publish_time"] or when < BEHAVIOR_START or when > BEHAVIOR_END:
            raise RuntimeError("行为时间超出范围")
        if jobs[job_index]["shelf_status"] != 1:
            raise RuntimeError("行为指向了下架职位")
        if behavior_type == 1:
            views[job_index] += 1
        elif behavior_type == 2:
            favs[job_index] += 1
        else:
            applies[job_index] += 1
    for index, job in enumerate(jobs):
        if (job["view_count"], job["favorite_count"], job["apply_count"]) != (views[index], favs[index], applies[index]):
            raise RuntimeError("职位计数与行为日志不一致")
    cohort = [
        job for job in jobs
        if job["direction"] == "后端开发" and job["education"] == 2 and job["experience_req"] == 1
        and job["job_type"] == 3 and job["city"] in TIER1
    ]
    if len(cohort) < 15:
        raise RuntimeError("一线后端应届本科校招样本过少")
    cohort_avg = sum((job["salary_min"] + job["salary_max"]) / 2 for job in cohort) / len(cohort)
    if not (17000 <= cohort_avg <= 24000):
        raise RuntimeError(f"一线后端应届本科校招月薪中点均值 {cohort_avg:.0f} 不合理")

    def direction_avg(direction: str) -> float:
        rows = [job for job in jobs if job["direction"] == direction and job["job_type"] != 2]
        return sum((job["salary_min"] + job["salary_max"]) / 2 for job in rows) / len(rows)

    if direction_avg("算法工程") <= direction_avg("后端开发"):
        raise RuntimeError("算法方向薪资未高于后端")
    if direction_avg("测试开发") >= direction_avg("后端开发"):
        raise RuntimeError("测试方向薪资未低于后端")
    if direction_avg("UI设计") >= direction_avg("后端开发"):
        raise RuntimeError("设计方向薪资未低于后端")
    tier2_cities = {"成都", "武汉", "西安", "长沙", "合肥", "重庆", "郑州", "济南", "青岛", "大连", "沈阳"}
    tier2 = [
        job for job in jobs
        if job["direction"] == "后端开发" and job["education"] == 2 and job["experience_req"] == 1
        and job["job_type"] == 3 and job["city"] in tier2_cities
    ]
    tier2_avg = sum((job["salary_min"] + job["salary_max"]) / 2 for job in tier2) / len(tier2)
    if not (cohort_avg * 0.60 <= tier2_avg <= cohort_avg * 0.85):
        raise RuntimeError(f"二线后端薪资 {tier2_avg:.0f} 相对一线 {cohort_avg:.0f} 不合理")
    if len(payload["csv_rows"]) < N_JOBS:
        raise RuntimeError("CSV 行数不足")
    month_counts = Counter(job["publish_time"].strftime("%Y-%m") for job in jobs)
    if max(month_counts.values()) < min(month_counts.values()) * 1.25:
        raise RuntimeError(f"月度职位过于均匀: {dict(sorted(month_counts.items()))}")
    if not (month_counts["2026-03"] > month_counts["2026-02"] and month_counts["2026-03"] > month_counts["2026-04"]):
        raise RuntimeError(f"春招高峰不明显: {dict(sorted(month_counts.items()))}")
    if not (month_counts["2026-09"] > month_counts["2026-08"] and month_counts["2026-10"] > month_counts["2026-08"]):
        raise RuntimeError(f"秋招高峰不明显: {dict(sorted(month_counts.items()))}")

    def share(months: set[str], directions: set[str]) -> float:
        rows = [job for job in jobs if job["publish_time"].strftime("%Y-%m") in months]
        if not rows:
            return 0.0
        return sum(1 for job in rows if job["direction"] in directions) / len(rows)

    def tag_share(months: set[str], tag: str) -> float:
        rows = [job for job in jobs if job["publish_time"].strftime("%Y-%m") in months]
        if not rows:
            return 0.0
        return sum(1 for job in rows if tag in job["tag_names"]) / len(rows)

    early = {"2025-11", "2025-12", "2026-01"}
    late = {"2026-08", "2026-09", "2026-10"}
    if share(late, RISING_DIRECTIONS) <= share(early, RISING_DIRECTIONS) * 1.3:
        raise RuntimeError("人工智能/算法工程占比上升不够明显")
    if share(late, FALLING_DIRECTIONS) >= share(early, FALLING_DIRECTIONS):
        raise RuntimeError("测试开发占比未下降")
    if tag_share(late, "大模型") <= tag_share(early, "大模型"):
        raise RuntimeError("大模型标签占比未上升")
    if tag_share(late, "PyTorch") <= tag_share(early, "PyTorch"):
        raise RuntimeError("PyTorch标签占比未上升")


def next_id(cur, table: str) -> int:
    allowed = {
        "sys_user", "ent_company", "stu_profile", "stu_skill", "stu_resume",
        "job_position", "job_position_tag", "job_favorite", "job_application",
        "job_application_log", "user_behavior_log",
    }
    if table not in allowed:
        raise RuntimeError(table)
    cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
    return cur.fetchone()[0] + 1


def bulk(cur, table: str, columns: list[str], rows: list[tuple], chunk: int = 400) -> int:
    if not rows:
        return 0
    if len(rows[0]) != len(columns):
        raise RuntimeError(f"{table} 列数 {len(rows[0])} 与字段 {len(columns)} 不一致")
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
    for part in chunks(rows, chunk):
        cur.executemany(sql, part)
    return len(rows)


def fetch_in(cur, sql: str, ids: list[int]) -> list[int]:
    if not ids:
        return []
    found = []
    for part in chunks(ids, 400):
        placeholder = ",".join(["%s"] * len(part))
        cur.execute(sql.format(placeholder), part)
        found.extend(row[0] for row in cur.fetchall())
    return found


def delete_in(cur, table: str, column: str, ids: list[int]) -> int:
    if not ids:
        return 0
    total = 0
    for part in chunks(list(dict.fromkeys(ids)), 400):
        placeholder = ",".join(["%s"] * len(part))
        cur.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholder})", part)
        total += cur.rowcount
    return total


def null_in(cur, table: str, column: str, ids: list[int]) -> int:
    if not ids:
        return 0
    total = 0
    for part in chunks(ids, 400):
        placeholder = ",".join(["%s"] * len(part))
        cur.execute(f"UPDATE {table} SET {column}=NULL WHERE {column} IN ({placeholder})", part)
        total += max(cur.rowcount, 0)
    return total


def clean_demo(cur) -> dict[str, int]:
    """按外键依赖删除演示数据。分类和技能标签保留，种子账号与测试账号保留。"""
    cur.execute(
        "SELECT id FROM sys_user WHERE username REGEXP %s AND username NOT IN (%s, %s, %s)",
        (USER_RE, *SEED_USERNAMES),
    )
    user_ids = [row[0] for row in cur.fetchall()]
    company_ids = fetch_in(cur, "SELECT id FROM ent_company WHERE user_id IN ({})", user_ids)
    cur.execute("SELECT id FROM ent_company WHERE credit_code REGEXP %s", (CREDIT_RE,))
    company_ids = sorted(set(company_ids) | {row[0] for row in cur.fetchall()})
    position_ids = fetch_in(cur, "SELECT id FROM job_position WHERE company_id IN ({})", company_ids)
    application_ids = []
    application_ids += fetch_in(cur, "SELECT id FROM job_application WHERE user_id IN ({})", user_ids)
    application_ids += fetch_in(cur, "SELECT id FROM job_application WHERE company_id IN ({})", company_ids)
    application_ids += fetch_in(cur, "SELECT id FROM job_application WHERE position_id IN ({})", position_ids)
    post_ids = []
    post_ids += fetch_in(cur, "SELECT id FROM com_post WHERE user_id IN ({})", user_ids)
    post_ids += fetch_in(cur, "SELECT id FROM com_post WHERE company_id IN ({})", company_ids)
    post_ids += fetch_in(cur, "SELECT id FROM com_post WHERE position_id IN ({})", position_ids)
    session_ids = fetch_in(cur, "SELECT id FROM ai_session WHERE user_id IN ({})", user_ids)
    article_ids = fetch_in(cur, "SELECT id FROM cms_article WHERE publisher_id IN ({})", user_ids)

    deleted = {}

    def add(name: str, count: int) -> None:
        if count:
            deleted[name] = deleted.get(name, 0) + count

    add("ai_message", delete_in(cur, "ai_message", "session_id", session_ids))
    add("ai_session", delete_in(cur, "ai_session", "id", session_ids))
    add("com_comment", delete_in(cur, "com_comment", "post_id", post_ids))
    add("com_comment", delete_in(cur, "com_comment", "user_id", user_ids))
    add("com_post", delete_in(cur, "com_post", "id", post_ids))
    add("job_interview", delete_in(cur, "job_interview", "application_id", application_ids))
    add("job_interview", delete_in(cur, "job_interview", "user_id", user_ids))
    add("job_interview", delete_in(cur, "job_interview", "company_id", company_ids))
    add("job_interview", delete_in(cur, "job_interview", "position_id", position_ids))
    add("job_application_log", delete_in(cur, "job_application_log", "application_id", application_ids))
    add("job_application_log", delete_in(cur, "job_application_log", "operator_id", user_ids))
    add("job_application", delete_in(cur, "job_application", "id", application_ids))
    add("job_favorite", delete_in(cur, "job_favorite", "user_id", user_ids))
    add("job_favorite", delete_in(cur, "job_favorite", "position_id", position_ids))
    add("job_position_tag", delete_in(cur, "job_position_tag", "position_id", position_ids))
    add("user_behavior_log", delete_in(cur, "user_behavior_log", "user_id", user_ids))
    add("user_behavior_log", delete_in(cur, "user_behavior_log", "target_id", position_ids))
    add("job_position", delete_in(cur, "job_position", "id", position_ids))
    add("stu_resume", delete_in(cur, "stu_resume", "user_id", user_ids))
    add("stu_skill", delete_in(cur, "stu_skill", "user_id", user_ids))
    add("stu_profile", delete_in(cur, "stu_profile", "user_id", user_ids))
    add("cms_article", delete_in(cur, "cms_article", "id", article_ids))
    null_in(cur, "sys_user", "auditor_id", user_ids)
    null_in(cur, "ent_company", "auditor_id", user_ids)
    null_in(cur, "job_position", "auditor_id", user_ids)
    null_in(cur, "com_post", "auditor_id", user_ids)
    null_in(cur, "com_comment", "auditor_id", user_ids)
    add("ent_company", delete_in(cur, "ent_company", "id", company_ids))
    add("sys_user", delete_in(cur, "sys_user", "id", user_ids))
    return deleted


def ensure_category(cur, name: str, parent_id, sort_no: int) -> tuple[int, bool]:
    cur.execute("SELECT id, deleted FROM job_category WHERE name=%s ORDER BY id LIMIT 1", (name,))
    row = cur.fetchone()
    if row:
        if row[1] == 1:
            cur.execute("UPDATE job_category SET deleted=0, status=1, update_time=%s WHERE id=%s", (TAXONOMY_TIME, row[0]))
        return row[0], False
    cur.execute(
        "INSERT INTO job_category (parent_id, name, sort_no, status, create_time, update_time, deleted) VALUES (%s,%s,%s,1,%s,%s,0)",
        (parent_id, name, sort_no, TAXONOMY_TIME, TAXONOMY_TIME),
    )
    return cur.lastrowid, True


def ensure_tag(cur, name: str, direction: str, sort_no: int) -> tuple[int, bool]:
    cur.execute("SELECT id, deleted FROM skill_tag WHERE name=%s", (name,))
    row = cur.fetchone()
    if row:
        if row[1] == 1:
            cur.execute(
                "UPDATE skill_tag SET deleted=0, status=1, update_time=%s WHERE id=%s",
                (TAXONOMY_TIME, row[0]),
            )
        return row[0], False
    cur.execute(
        "INSERT INTO skill_tag (name, direction, sort_no, status, create_time, update_time, deleted) VALUES (%s,%s,%s,1,%s,%s,0)",
        (name, direction, sort_no, TAXONOMY_TIME, TAXONOMY_TIME),
    )
    return cur.lastrowid, True


def ensure_taxonomy(cur) -> tuple[dict, dict, int, int]:
    categories = {}
    inserted_categories = 0
    for name, sort_no in PARENTS:
        category_id, created = ensure_category(cur, name, None, sort_no)
        categories[name] = category_id
        inserted_categories += int(created)
    for name, parent, sort_no in LEAVES:
        category_id, created = ensure_category(cur, name, categories[parent], sort_no)
        categories[name] = category_id
        inserted_categories += int(created)
    tags = {}
    inserted_tags = 0
    for index, (name, direction) in enumerate(list(ALL_TAGS) + list(EXTRA_TAGS)):
        tag_id, created = ensure_tag(cur, name, direction, 30 + index)
        tags[name] = tag_id
        inserted_tags += int(created)
    return categories, tags, inserted_categories, inserted_tags


def admin_id(cur) -> int:
    cur.execute("SELECT id FROM sys_user WHERE username='admin' AND role=3 AND deleted=0")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("未找到 admin 账号，请先执行 db/seed.sql")
    return row[0]


def insert_all(cur, payload: dict, pass_hash: str) -> dict[str, int]:
    started = time.perf_counter()
    categories, tags, category_count, tag_count = ensure_taxonomy(cur)
    auditor = admin_id(cur)
    companies = payload["companies"]
    jobs = payload["jobs"]
    students = payload["students"]
    user_base = next_id(cur, "sys_user")
    company_base = next_id(cur, "ent_company")
    for index, company in enumerate(companies):
        company["user_id"] = user_base + index
        company["id"] = company_base + index
    for index, student in enumerate(students):
        student["user_id"] = user_base + N_COMPANIES + index
    profile_base = next_id(cur, "stu_profile")
    skill_base = next_id(cur, "stu_skill")
    resume_base = next_id(cur, "stu_resume")
    job_base = next_id(cur, "job_position")
    for index, student in enumerate(students):
        student["profile_id"] = profile_base + index
        student["resume_id"] = resume_base + index
    for index, job in enumerate(jobs):
        job["id"] = job_base + index
        job["company_id"] = companies[job["company_index"]]["id"]

    written = {"job_category": category_count, "skill_tag": tag_count}
    user_rows = []
    for company in companies:
        user_rows.append((
            company["user_id"], company["username"], pass_hash, 2, company["nickname"], company["phone"],
            company["email"], None, 1, "账号审核通过", company["audit_time"], auditor, company["audit_time"],
            company["create_time"], company["audit_time"], 0,
        ))
    for student in students:
        user_rows.append((
            student["user_id"], student["username"], pass_hash, 1, student["nickname"], student["phone"],
            student["email"], None, 1, "账号审核通过", student["audit_time"], auditor, student["audit_time"],
            student["create_time"], student["audit_time"], 0,
        ))
    user_columns = [
        "id", "username", "password", "role", "nickname", "phone", "email", "avatar",
        "status", "audit_remark", "audit_time", "auditor_id", "last_login_time",
        "create_time", "update_time", "deleted",
    ]
    written["sys_user"] = bulk(cur, "sys_user", user_columns, user_rows)

    company_rows = []
    for company in companies:
        company_rows.append((
            company["id"], company["user_id"], company["company_name"], company["short_name"], None,
            company["industry"], company["scale"], company["province"], company["city"], company["address"],
            company["website"], company["intro"], company["credit_code"], None,
            company["contact_name"], company["contact_phone"], company["contact_email"],
            1, "资质审核通过", company["audit_time"], auditor,
            company["create_time"], company["audit_time"], 0,
        ))
    company_columns = [
        "id", "user_id", "company_name", "short_name", "logo_url", "industry", "scale",
        "province", "city", "address", "website", "intro", "credit_code", "license_url",
        "contact_name", "contact_phone", "contact_email",
        "audit_status", "audit_remark", "audit_time", "auditor_id",
        "create_time", "update_time", "deleted",
    ]
    written["ent_company"] = bulk(cur, "ent_company", company_columns, company_rows)

    profile_rows = []
    resume_rows = []
    skill_rows = []
    skill_id = skill_base
    for student in students:
        profile_rows.append((
            student["profile_id"], student["user_id"], student["real_name"], student["gender"], student["birthday"],
            student["student_no"], student["school"], student["college"], student["major"], student["education"],
            student["graduation_year"], student["city"], student["expect_salary_min"], student["expect_salary_max"],
            student["direction"], student["self_intro"], student["create_time"], student["audit_time"], 0,
        ))
        skill_names = "、".join(name for name, _level in student["skills"])
        resume_rows.append((
            student["resume_id"], student["user_id"], f"{student['real_name']}-校招简历", 1,
            f"{student['school']}，{student['major']}，{EDU_NAME[student['education']]}，{student['graduation_year']}届。",
            f"参与{rng_project(student['username'])}，使用{skill_names}完成主要功能。",
            "课程实践与校内项目，暂无全职经历。" if student["education"] <= 2 else "有与专业相关的科研或实习训练。",
            skill_names, student["self_intro"], None, student["create_time"], student["audit_time"], 0,
        ))
        for name, level in student["skills"]:
            skill_rows.append((skill_id, student["user_id"], tags[name], level, student["create_time"], student["audit_time"], 0))
            skill_id += 1
    profile_columns = [
        "id", "user_id", "real_name", "gender", "birthday", "student_no", "school", "college", "major",
        "education", "graduation_year", "expect_city", "expect_salary_min", "expect_salary_max",
        "expect_direction", "self_intro", "create_time", "update_time", "deleted",
    ]
    resume_columns = [
        "id", "user_id", "title", "is_default", "education_exp", "project_exp", "internship_exp",
        "skill_desc", "self_evaluation", "attachment_url", "create_time", "update_time", "deleted",
    ]
    skill_columns = ["id", "user_id", "tag_id", "proficiency", "create_time", "update_time", "deleted"]
    written["stu_profile"] = bulk(cur, "stu_profile", profile_columns, profile_rows)
    written["stu_resume"] = bulk(cur, "stu_resume", resume_columns, resume_rows)
    written["stu_skill"] = bulk(cur, "stu_skill", skill_columns, skill_rows)

    position_rows = []
    tag_rows = []
    tag_row_id = next_id(cur, "job_position_tag")
    for job in jobs:
        position_rows.append((
            job["id"], job["company_id"], categories[job["category"]], job["title"], job["direction"],
            job["province"], job["city"], job["district"], job["address"],
            job["salary_min"], job["salary_max"], job["salary_months"], job["education"], job["experience_req"],
            job["job_type"], job["headcount"], job["description"], job["requirement"], job["welfare"],
            job["shelf_status"], 1, "职位信息完整，审核通过", job["publish_time"], auditor, job["publish_time"],
            job["view_count"], job["favorite_count"], job["apply_count"], job["create_time"], job["publish_time"], 0,
        ))
        for name in job["tag_names"]:
            tag_rows.append((tag_row_id, job["id"], tags[name], job["create_time"], job["publish_time"], 0))
            tag_row_id += 1
    position_columns = [
        "id", "company_id", "category_id", "title", "tech_direction", "province", "city", "district", "address",
        "salary_min", "salary_max", "salary_months", "education", "experience_req", "job_type", "headcount",
        "description", "requirement", "welfare", "shelf_status", "audit_status", "audit_remark", "audit_time",
        "auditor_id", "publish_time", "view_count", "favorite_count", "apply_count", "create_time", "update_time", "deleted",
    ]
    written["job_position"] = bulk(cur, "job_position", position_columns, position_rows, chunk=200)
    written["job_position_tag"] = bulk(
        cur, "job_position_tag",
        ["id", "position_id", "tag_id", "create_time", "update_time", "deleted"],
        tag_rows,
    )

    favorite_rows = []
    favorite_base = next_id(cur, "job_favorite")
    for offset, (student_index, job_index, when) in enumerate(payload["favorites"]):
        student = students[student_index]
        job = jobs[job_index]
        favorite_rows.append((favorite_base + offset, student["user_id"], job["id"], when, when, 0))
    written["job_favorite"] = bulk(
        cur, "job_favorite",
        ["id", "user_id", "position_id", "create_time", "update_time", "deleted"],
        favorite_rows,
    )

    application_rows = []
    log_rows = []
    application_base = next_id(cur, "job_application")
    log_base = next_id(cur, "job_application_log")
    for offset, (student_index, job_index, when) in enumerate(payload["applications"]):
        student = students[student_index]
        job = jobs[job_index]
        application_id = application_base + offset
        application_rows.append((
            application_id, student["user_id"], job["id"], job["company_id"], student["resume_id"],
            0, "校园招聘网申", when, when, when, 0,
        ))
        log_rows.append((log_base + offset, application_id, None, 0, student["user_id"], "学生提交投递", when, when, 0))
    written["job_application"] = bulk(
        cur, "job_application",
        ["id", "user_id", "position_id", "company_id", "resume_id", "status", "remark", "apply_time", "create_time", "update_time", "deleted"],
        application_rows,
    )
    written["job_application_log"] = bulk(
        cur, "job_application_log",
        ["id", "application_id", "from_status", "to_status", "operator_id", "remark", "create_time", "update_time", "deleted"],
        log_rows,
    )

    behavior_rows = []
    behavior_base = next_id(cur, "user_behavior_log")
    for offset, (student_index, behavior_type, job_index, weight, when) in enumerate(payload["behaviors"]):
        behavior_rows.append((
            behavior_base + offset, students[student_index]["user_id"], behavior_type, 1,
            jobs[job_index]["id"], weight, when, when, 0,
        ))
    written["user_behavior_log"] = bulk(
        cur, "user_behavior_log",
        ["id", "user_id", "behavior_type", "target_type", "target_id", "weight", "create_time", "update_time", "deleted"],
        behavior_rows, chunk=800,
    )
    print(f"写入耗时 {time.perf_counter() - started:.1f}s")
    return written


def rng_project(username: str) -> str:
    digest = hashlib.md5(username.encode()).hexdigest()
    return PROJECTS[int(digest[:2], 16) % len(PROJECTS)]


def write_csv(rows: list[dict]) -> str:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CSV_PATH.with_suffix(".csv.tmp")
    fields = ["title", "company", "city", "salary_text", "education_text", "experience_text", "tags", "publish_date", "direction"]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(CSV_PATH)
    return hashlib.md5(CSV_PATH.read_bytes()).hexdigest()


def remove_csv() -> None:
    if CSV_PATH.exists():
        CSV_PATH.unlink()


def print_deleted(deleted: dict[str, int]) -> None:
    if not deleted:
        print("删除旧演示数据: 0 行")
        return
    print("删除旧演示数据:")
    for name in sorted(deleted):
        print(f"  {name:<22} {deleted[name]:6d}")


def print_written(written: dict[str, int]) -> None:
    print("本次写入:")
    for name in [
        "job_category", "skill_tag", "sys_user", "ent_company", "stu_profile", "stu_skill", "stu_resume",
        "job_position", "job_position_tag", "job_favorite", "job_application", "job_application_log", "user_behavior_log",
    ]:
        print(f"  {name:<22} {written.get(name, 0):6d}")


def print_stats(cur) -> None:
    print("演示数据现存:")
    queries = [
        ("sys_user", "SELECT COUNT(*) FROM sys_user WHERE username REGEXP %s", (USER_RE,)),
        ("ent_company", "SELECT COUNT(*) FROM ent_company WHERE credit_code REGEXP %s", (CREDIT_RE,)),
        ("stu_profile", """
            SELECT COUNT(*) FROM stu_profile p
            JOIN sys_user u ON u.id=p.user_id WHERE u.username REGEXP %s
        """, (USER_RE,)),
        ("stu_skill", """
            SELECT COUNT(*) FROM stu_skill s
            JOIN sys_user u ON u.id=s.user_id WHERE u.username REGEXP %s
        """, (USER_RE,)),
        ("stu_resume", """
            SELECT COUNT(*) FROM stu_resume r
            JOIN sys_user u ON u.id=r.user_id WHERE u.username REGEXP %s
        """, (USER_RE,)),
        ("job_position", """
            SELECT COUNT(*) FROM job_position p
            JOIN ent_company c ON c.id=p.company_id WHERE c.credit_code REGEXP %s
        """, (CREDIT_RE,)),
        ("job_position_tag", """
            SELECT COUNT(*) FROM job_position_tag t
            JOIN job_position p ON p.id=t.position_id
            JOIN ent_company c ON c.id=p.company_id WHERE c.credit_code REGEXP %s
        """, (CREDIT_RE,)),
        ("job_favorite", """
            SELECT COUNT(*) FROM job_favorite f
            JOIN sys_user u ON u.id=f.user_id WHERE u.username REGEXP %s
        """, (USER_RE,)),
        ("job_application", """
            SELECT COUNT(*) FROM job_application a
            JOIN sys_user u ON u.id=a.user_id WHERE u.username REGEXP %s
        """, (USER_RE,)),
        ("user_behavior_log", """
            SELECT COUNT(*) FROM user_behavior_log b
            JOIN sys_user u ON u.id=b.user_id WHERE u.username REGEXP %s
        """, (USER_RE,)),
        ("skill_tag", "SELECT COUNT(*) FROM skill_tag WHERE deleted=0", ()),
        ("job_category", "SELECT COUNT(*) FROM job_category WHERE deleted=0", ()),
    ]
    for name, sql, args in queries:
        cur.execute(sql, args)
        print(f"  {name:<22} {cur.fetchone()[0]:6d}")
    print("各城市职位数:")
    cur.execute(
        """
        SELECT p.city, COUNT(*) cnt
        FROM job_position p
        JOIN ent_company c ON c.id=p.company_id
        WHERE c.credit_code REGEXP %s
        GROUP BY p.city
        ORDER BY cnt DESC, p.city
        """,
        (CREDIT_RE,),
    )
    for city, count in cur.fetchall():
        print(f"  {city:<8} {count:5d}")
    print("各方向月薪中点均值（元）:")
    cur.execute(
        """
        SELECT p.tech_direction, COUNT(*) jobs, ROUND(AVG((p.salary_min + p.salary_max) / 2)) avg_mid
        FROM job_position p
        JOIN ent_company c ON c.id=p.company_id
        WHERE c.credit_code REGEXP %s
        GROUP BY p.tech_direction
        ORDER BY avg_mid DESC
        """,
        (CREDIT_RE,),
    )
    for direction, jobs, avg_mid in cur.fetchall():
        print(f"  {direction:<12} 职位 {jobs:4d}  均值 {int(avg_mid):6d}")
    cur.execute(
        """
        SELECT DATE_FORMAT(p.publish_time, '%%Y-%%m') mon, COUNT(*)
        FROM job_position p
        JOIN ent_company c ON c.id=p.company_id
        WHERE c.credit_code REGEXP %s
        GROUP BY mon
        ORDER BY mon
        """,
        (CREDIT_RE,),
    )
    print("发布月份:")
    for month, count in cur.fetchall():
        print(f"  {month}  {count:4d}")


def fingerprint(payload: dict) -> str:
    jobs = payload["jobs"]
    behaviors = payload["behaviors"]
    salary_sum = sum(job["salary_min"] + job["salary_max"] for job in jobs)
    weight_sum = sum(item[3] for item in behaviors)
    return f"jobs={len(jobs)} salary_sum={salary_sum} behaviors={len(behaviors)} weight_sum={weight_sum} fav={len(payload['favorites'])} apply={len(payload['applications'])}"


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    if args.clean:
        connection = connect()
        try:
            with connection.cursor() as cur:
                deleted = clean_demo(cur)
            connection.commit()
        except pymysql.MySQLError as exc:
            connection.rollback()
            raise SystemExit(f"清理失败: {exc}") from exc
        finally:
            connection.close()
        remove_csv()
        print_deleted(deleted)
        print(f"完成，耗时 {time.perf_counter() - started:.1f}s")
        return 0

    payload = generate(args.seed)
    validate(payload)
    print("内存数据通过校验:", fingerprint(payload))
    pass_hash = password_hash()
    connection = connect()
    try:
        with connection.cursor() as cur:
            deleted = clean_demo(cur)
            print_deleted(deleted)
            written = insert_all(cur, payload, pass_hash)
        connection.commit()
    except pymysql.MySQLError as exc:
        connection.rollback()
        raise SystemExit(f"写入失败，已回滚: {exc}") from exc
    finally:
        connection.close()

    digest = write_csv(payload["csv_rows"])
    print_written(written)
    blank_rows = sum(
        1 for row in payload["csv_rows"]
        if not row["salary_text"] or not row["city"] or not row["education_text"] or not row["experience_text"] or not row["tags"]
    )
    print(f"CSV {CSV_PATH} 行数 {len(payload['csv_rows'])}（含表头外），其中字段缺失行 {blank_rows}，md5 {digest}")
    connection = connect()
    try:
        with connection.cursor() as cur:
            print_stats(cur)
    finally:
        connection.close()
    print(f"完成，耗时 {time.perf_counter() - started:.1f}s，种子 {args.seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
