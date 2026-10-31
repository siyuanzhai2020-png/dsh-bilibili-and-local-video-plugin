# -*- coding: utf-8 -*-
"""后台任务表：给 MCP 工具用（提交→task_id→轮询）。M0 CLI 同步调用，不依赖本模块。"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Any, Callable


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, label: str, fn: Callable[[Callable], Any]) -> str:
        """fn(progress) -> result；progress(stage, pct, msg)。"""
        task_id = f"{kind[:6]}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task = {
            "task_id": task_id, "kind": kind, "label": label,
            "status": "running", "stage": "start", "pct": 0.0,
            "message": "", "started_at": time.time(), "finished_at": None,
            "result": None, "error": None, "log": [],
        }

        def progress(stage: str, pct: float, msg: str = "") -> None:
            with self._lock:
                task["stage"] = stage
                task["pct"] = round(max(0.0, min(1.0, float(pct))), 4)
                if msg:
                    task["message"] = str(msg)[:200]
                    task["log"] = (task["log"] + [str(msg)[:200]])[-40:]

        def runner() -> None:
            try:
                result = fn(progress)
                with self._lock:
                    task["status"] = "completed"
                    task["pct"] = 1.0
                    task["result"] = result
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    task["status"] = "failed"
                    task["error"] = f"{type(exc).__name__}: {exc}"[:800]
                    task["log"] = (task["log"] + [traceback.format_exc()[-1200:]])[-40:]
            finally:
                with self._lock:
                    task["finished_at"] = time.time()

        with self._lock:
            self._tasks[task_id] = task
        threading.Thread(target=runner, name=f"task-{task_id}", daemon=True).start()
        return task_id

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            t = self._tasks.get(task_id)
            return dict(t) if t else None

    def list(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = sorted(self._tasks.values(), key=lambda t: t["started_at"], reverse=True)
        return [{k: t[k] for k in ("task_id", "kind", "label", "status", "stage",
                                   "pct", "message", "started_at", "finished_at", "error")}
                for t in rows[:limit]]

    def wait(self, task_id: str, timeout_s: float = 60.0) -> dict | None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            t = self.get(task_id)
            if t is None:
                return None
            if t["status"] in ("completed", "failed"):
                return t
            time.sleep(0.25)
        return self.get(task_id)


TASKS = TaskManager()
