"""就业推荐服务。

离线混合推荐由 Spark 任务写入 spark_recommend；这里提供状态、单用户实时推荐、
相似职位和离线评估查询。实时计算不启动 Spark。
"""

from __future__ import annotations

import logging
from typing import Any

from app.spark.recommend_online import latest_evaluation, recommend_for_user, similar_jobs, skill_radar
from app.spark.runner import is_running

logger = logging.getLogger(__name__)


class RecommendService:
    """推荐算法查询与实时计算。"""

    def __init__(self) -> None:
        self.algorithm_version = "v1.0.0-hybrid"

    def get_status(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "module": "recommend",
            "status": "READY",
            "algorithm_version": self.algorithm_version,
            "strategies": ["user_cf", "content_based", "hybrid_ranking"],
            "description": "融合协同过滤与学生-岗位技能画像的混合推荐引擎",
            "running": is_running(),
        }
        try:
            latest = latest_evaluation()
            if latest.get("batchNo"):
                data["batchNo"] = latest.get("batchNo")
                data["cfMethod"] = latest.get("cfMethod")
                data["alpha"] = latest.get("alpha")
        except Exception:
            logger.warning("读取推荐批次失败", exc_info=True)
        return data

    def recommend_user(self, user_id: int, top_k: int = 10) -> dict[str, Any]:
        return recommend_for_user(user_id, top_k)

    def similar(self, job_id: int, top_k: int = 6) -> dict[str, Any]:
        return similar_jobs(job_id, top_k)

    def evaluation(self) -> dict[str, Any]:
        return latest_evaluation()

    def calculate_skill_radar(self, student_id: int) -> dict[str, Any]:
        return skill_radar(student_id)


recommend_service = RecommendService()
