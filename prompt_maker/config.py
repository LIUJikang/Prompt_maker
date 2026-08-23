from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3.8:27b")
    request_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "900"))
    ollama_num_predict: int = int(os.getenv("OLLAMA_NUM_PREDICT", "16384"))
    ollama_structured_retries: int = int(
        os.getenv("OLLAMA_STRUCTURED_RETRIES", "1")
    )
    ollama_think: bool = _env_bool("OLLAMA_THINK", False)
    release_models_between_stages: bool = _env_bool(
        "RELEASE_MODELS_BETWEEN_STAGES", True
    )
    max_questions: int = int(os.getenv("MAX_CLARIFYING_QUESTIONS", "3"))
    comfy_url: str = os.getenv("COMFYUI_URL", "http://127.0.0.1:8000")
    comfy_workflow: str = os.getenv("COMFYUI_WORKFLOW", "video_ltx2_5_i2v.json")
    comfy_image_workflow: str = os.getenv(
        "COMFYUI_IMAGE_WORKFLOW", "image_z_image_turbo.json"
    )
    comfy_timeout: float = float(os.getenv("COMFYUI_TIMEOUT", "1800"))


settings = Settings()
