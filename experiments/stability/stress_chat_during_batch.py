"""压测：推荐批次运行期间，三类角色经后端 SSE 接口向助手提问，记录首字与总耗时。

用法（服务需已启动）：
  .venv/bin/python experiments/stability/stress_chat_during_batch.py --label before --rounds 2
  .venv/bin/python experiments/stability/stress_chat_during_batch.py --label idle --no-batch --rounds 1

每题记录：发出时刻（相对批次触发）、首个 delta 到达耗时 first_token_s、[DONE] 到达耗时 total_s、
是否收到 done、meta.mode、回答是否为降级摘录，以及 ai-service /health 探针的最大延迟（判断事件循环是否被卡住）。
结果写 experiments/results/stability_<label>.json。只做测量，不改业务数据（会话在结束时删除）。
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8080/api"
AI = "http://127.0.0.1:8000"
QUESTIONS = [
    ("student", "student123", "/student/ai", "三方协议怎么签？"),
    ("company", "company123", "/company/ai", "列出我发布的职位"),
    ("admin", "admin123", "/admin/ai", "哪个城市岗位最多"),
]
ROOT = Path(__file__).resolve().parents[2]


def login(client: httpx.Client, user: str, pwd: str) -> str:
    resp = client.post(f"{BASE}/public/auth/login", json={"username": user, "password": pwd})
    return resp.json()["data"]["token"]


def ask(token: str, prefix: str, question: str, t0: float, timeout: float) -> dict:
    started = time.perf_counter()
    rec = {"question": question, "start_offset_s": round(started - t0, 2)}
    first_byte = first_token = None
    done = end = False
    mode = answer = None
    sid = None
    error = None
    try:
        with httpx.stream(
            "POST",
            f"{BASE}{prefix}/chat/stream",
            json={"question": question},
            headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
            timeout=httpx.Timeout(timeout, connect=5),
        ) as resp:
            for line in resp.iter_lines():
                now = time.perf_counter() - started
                if first_byte is None:
                    first_byte = now
                if time.perf_counter() - started > timeout:
                    error = "client-timeout"
                    break
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    end = True
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                kind = event.get("type")
                if kind == "session":
                    sid = event.get("session_id")
                elif kind == "meta":
                    mode = event.get("mode")
                elif kind == "delta" and first_token is None:
                    first_token = now
                elif kind == "done":
                    done = True
                    answer = event.get("answer") or ""
                    rec["server_first_token_ms"] = event.get("first_token_ms")
                    rec["server_latency_ms"] = event.get("latency_ms")
                    rec["degraded"] = event.get("degraded")
    except httpx.TimeoutException:
        error = "client-timeout"
    except Exception as exc:  # noqa: BLE001
        error = repr(exc)
    total = time.perf_counter() - started
    rec.update(
        {
            "first_byte_s": round(first_byte, 2) if first_byte is not None else None,
            "first_token_s": round(first_token, 2) if first_token is not None else None,
            "total_s": round(total, 2),
            "done": done,
            "done_line": end,
            "mode": mode,
            "answer_chars": len(answer or ""),
            "offline_excerpt": bool(answer and ("离线" in answer or "降级" in answer or "超时" in answer)),
            "error": error,
            "session_id": sid,
            "end_offset_s": round(time.perf_counter() - t0, 2),
        }
    )
    return rec


class HealthProbe(threading.Thread):
    """每 0.5s GET ai-service /health，记录延迟，用来判断事件循环是否被卡住。"""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.samples: list[float] = []
        self.stop = threading.Event()

    def run(self) -> None:
        with httpx.Client(timeout=30) as client:
            while not self.stop.is_set():
                t = time.perf_counter()
                try:
                    client.get(f"{AI}/health")
                    self.samples.append(time.perf_counter() - t)
                except Exception:  # noqa: BLE001
                    self.samples.append(30.0)
                self.stop.wait(0.5)


def batch_state(client: httpx.Client, batch_no: str) -> dict | None:
    try:
        resp = client.get(f"{AI}/spark/tasks/{batch_no}")
        if resp.status_code != 200 or resp.json().get("code") != 200:
            return None
        return resp.json()["data"]
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--no-batch", action="store_true")
    parser.add_argument("--warmup", type=float, default=8.0, help="触发批次后等待秒数再提问")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    client = httpx.Client(timeout=30)
    tokens = {role: login(client, role, pwd) for role, pwd, _, _ in QUESTIONS}
    probe = HealthProbe()
    probe.start()
    t0 = time.perf_counter()
    batch_no = None
    if not args.no_batch:
        resp = client.post(
            f"{BASE}/admin/recommend/run", json={}, headers={"Authorization": f"Bearer {tokens['admin']}"}
        ).json()
        print("trigger:", json.dumps(resp, ensure_ascii=False))
        batch_no = (resp.get("data") or {}).get("batchNo")
        time.sleep(args.warmup)

    results = []
    for rnd in range(args.rounds):
        for role, _, prefix, question in QUESTIONS:
            rec = ask(tokens[role], prefix, question, t0, args.timeout)
            rec.update({"role": role, "round": rnd + 1})
            if batch_no:
                state = batch_state(client, batch_no)
                tasks = (state or {}).get("tasks") or []
                rec["batch_running_at_end"] = any(int(t.get("status", 0)) == 0 for t in tasks) or not tasks
            print(json.dumps(rec, ensure_ascii=False))
            results.append(rec)

    batch = None
    if batch_no:
        deadline = time.perf_counter() + 900
        while time.perf_counter() < deadline:
            state = batch_state(client, batch_no)
            tasks = (state or {}).get("tasks") or []
            if tasks and all(int(t.get("status", 0)) != 0 for t in tasks):
                batch = {"batchNo": batch_no, "tasks": tasks, "finished_offset_s": round(time.perf_counter() - t0, 1)}
                break
            time.sleep(3)
    probe.stop.set()
    probe.join(timeout=5)

    for rec in results:
        sid = rec.get("session_id")
        prefix = dict((r, p) for r, _, p, _ in QUESTIONS)[rec["role"]]
        if sid:
            client.delete(f"{BASE}{prefix}/sessions/{sid}", headers={"Authorization": f"Bearer {tokens[rec['role']]}"})

    ft = [r["first_token_s"] for r in results if r["first_token_s"] is not None]
    tt = [r["total_s"] for r in results]
    hs = sorted(probe.samples)
    summary = {
        "label": args.label,
        "asked": len(results),
        "done": sum(1 for r in results if r["done"] and r["done_line"]),
        "client_timeouts": sum(1 for r in results if r["error"] == "client-timeout"),
        "first_token_s": {"median": statistics.median(ft) if ft else None, "max": max(ft) if ft else None},
        "total_s": {"median": statistics.median(tt), "max": max(tt)},
        "health_probe_ms": {
            "n": len(hs),
            "p50": round(hs[len(hs) // 2] * 1000, 1) if hs else None,
            "p99": round(hs[int(len(hs) * 0.99) - 1] * 1000, 1) if hs else None,
            "max": round(hs[-1] * 1000, 1) if hs else None,
        },
    }
    out = {"summary": summary, "batch": batch, "results": results, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    path = ROOT / "experiments" / "results" / f"stability_{args.label}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if batch:
        for t in batch["tasks"]:
            print("batch task", t.get("taskCode"), t.get("status"), t.get("startTime"), t.get("endTime"))
        print("batch finished at", batch["finished_offset_s"], "s")
    print("wrote", path)


if __name__ == "__main__":
    main()
