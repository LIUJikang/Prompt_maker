from __future__ import annotations

import json
import math
from pathlib import Path

from .config import Settings
from .ollama_client import OllamaClient
from .prompts import CLARIFICATION, DIRECTOR, IMAGE_ANALYSIS
from .schemas import ClarificationPlan, DirectorResult, ImageAnalysis


def legal_frame_count(duration_seconds: float, fps: int) -> int:
    """Return the closest positive LTX frame count satisfying frames = 8n + 1."""
    raw = max(9, round(duration_seconds * fps))
    lower = max(9, ((raw - 1) // 8) * 8 + 1)
    upper = lower + 8
    return min((lower, upper), key=lambda value: abs(value - raw))


class PromptDirector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OllamaClient(settings)

    def analyze_image(self, image_path: str | Path, description: str) -> ImageAnalysis:
        return self.client.structured_chat(
            system=IMAGE_ANALYSIS,
            user=f"用户对目标视频的基础描述：\n{description or '用户尚未描述。'}",
            schema=ImageAnalysis,
            image_path=image_path,
            temperature=0.1,
        )

    def plan_questions(
        self,
        analysis: ImageAnalysis,
        description: str,
        known_settings: dict[str, object],
    ) -> ClarificationPlan:
        user = json.dumps(
            {
                "image_analysis": analysis.model_dump(),
                "user_description": description,
                "known_settings": known_settings,
            },
            ensure_ascii=False,
        )
        return self.client.structured_chat(
            system=CLARIFICATION.format(max_questions=self.settings.max_questions),
            user=user,
            schema=ClarificationPlan,
            temperature=0.25,
        )

    def direct(
        self,
        analysis: ImageAnalysis,
        description: str,
        answers: str,
        *,
        duration: float,
        fps: int,
        aspect_ratio: str,
        shot_mode: str,
        motion_intensity: str,
    ) -> DirectorResult:
        frames = legal_frame_count(duration, fps)
        actual_duration = frames / fps
        context = {
            "image_analysis": analysis.model_dump(),
            "user_description": description,
            "clarification_answers": answers or "使用合理默认值",
            "generation_settings": {
                "requested_duration_seconds": duration,
                "actual_duration_seconds": round(actual_duration, 3),
                "fps": fps,
                "num_frames": frames,
                "aspect_ratio": aspect_ratio,
                "shot_mode": shot_mode,
                "motion_intensity": motion_intensity,
            },
        }
        return self.client.structured_chat(
            system=DIRECTOR,
            user=json.dumps(context, ensure_ascii=False),
            schema=DirectorResult,
            temperature=0.45,
        )
