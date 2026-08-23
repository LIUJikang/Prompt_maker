from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Subject(BaseModel):
    id: str
    type: str
    appearance: str = ""
    position: str = ""
    pose: str = ""
    gaze: str = ""


class Environment(BaseModel):
    location: str = ""
    foreground: list[str] = Field(default_factory=list)
    background: list[str] = Field(default_factory=list)
    weather: str = ""
    lighting: str = ""


class Composition(BaseModel):
    shot_size: str = ""
    camera_angle: str = ""
    depth_of_field: str = ""
    aspect_ratio_guess: str = ""


class ImageAnalysis(BaseModel):
    subjects: list[Subject] = Field(default_factory=list)
    environment: Environment = Field(default_factory=Environment)
    composition: Composition = Field(default_factory=Composition)
    style: str = ""
    mood: str = ""
    motion_space: str = ""
    constraints: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ImagePromptResult(BaseModel):
    prompt_en: str
    change_summary_zh: str = ""


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    reason: str
    default: str


class ClarificationPlan(BaseModel):
    ready: bool = False
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class TimelineBeat(BaseModel):
    start: float
    end: float
    subject_action: str
    camera: str
    environment: str = ""
    audio: str = ""


class Shot(BaseModel):
    number: int
    duration_seconds: float
    purpose: str
    timeline: list[TimelineBeat]
    prompt_en: str
    transition: str = "none"
    end_frame_intent: str = ""


class GenerationParameters(BaseModel):
    duration_seconds: float
    fps: int = 24
    num_frames: int
    aspect_ratio: str
    shot_mode: Literal["single_take", "multi_shot"]
    motion_intensity: Literal["conservative", "cinematic", "dynamic"]


class DirectorResult(BaseModel):
    title: str
    director_notes_zh: str
    creative_intent: str
    shots: list[Shot]
    final_prompt_en: str
    negative_prompt_en: str
    continuity_constraints: list[str]
    parameters: GenerationParameters
    warnings: list[str] = Field(default_factory=list)
