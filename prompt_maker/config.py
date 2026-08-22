from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3.8:27b")
    request_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "300"))
    max_questions: int = int(os.getenv("MAX_CLARIFYING_QUESTIONS", "3"))
    comfy_url: str = os.getenv("COMFYUI_URL", "http://127.0.0.1:8000")
    comfy_workflow: str = os.getenv("COMFYUI_WORKFLOW", "video_ltx2_5_i2v.json")
    comfy_timeout: float = float(os.getenv("COMFYUI_TIMEOUT", "1800"))


settings = Settings()
