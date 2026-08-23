from __future__ import annotations

import json
from typing import Any

import gradio as gr

from .config import settings
from .comfy_client import ComfyUIClient, ComfyUIError
from .ollama_client import OllamaError
from .schemas import DirectorResult, ImageAnalysis
from .workflow import PromptDirector, legal_frame_count


director = PromptDirector(settings)
comfy = ComfyUIClient(settings)

IMAGE_SIZES = {
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "1:1": (1024, 1024),
    "2.39:1": (1536, 640),
}

BUSY_OVERLAY_HTML = """
<div class="busy-card" role="status" aria-live="assertive">
  <div class="busy-spinner" aria-hidden="true"></div>
  <div class="busy-title">{title}</div>
  <div class="busy-message">{message}</div>
  <div class="busy-hint">本地大模型处理可能需要一些时间，请保持此页面打开。</div>
</div>
"""

APP_CSS = """
#busy-overlay {
  position: fixed !important;
  inset: 0 !important;
  z-index: 100000 !important;
  display: flex !important;
  align-items: center;
  justify-content: center;
  width: 100vw !important;
  height: 100vh !important;
  margin: 0 !important;
  padding: 24px !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: rgba(2, 6, 23, 0.94) !important;
  backdrop-filter: blur(10px);
  color: #ffffff !important;
  cursor: wait;
  pointer-events: all !important;
}
#busy-overlay .busy-card {
  width: min(440px, calc(100vw - 48px));
  padding: 36px 32px;
  border: 2px solid #60a5fa !important;
  border-radius: 20px;
  background: #111827 !important;
  color: #ffffff !important;
  text-align: center;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
}
#busy-overlay .busy-spinner {
  width: 52px;
  height: 52px;
  margin: 0 auto 22px;
  border: 5px solid #475569 !important;
  border-top-color: #60a5fa !important;
  border-radius: 50%;
  animation: busy-spin 0.85s linear infinite;
}
#busy-overlay .busy-title {
  color: #ffffff !important;
  font-size: 24px;
  font-weight: 800;
}
#busy-overlay .busy-message {
  margin-top: 12px;
  color: #e2e8f0 !important;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.6;
}
#busy-overlay .busy-hint {
  margin-top: 20px;
  color: #93c5fd !important;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}
@keyframes busy-spin { to { transform: rotate(360deg); } }
"""


def _known_settings(
    duration: float,
    fps: int,
    aspect_ratio: str,
    shot_mode: str,
    motion_intensity: str,
) -> dict[str, Any]:
    return {
        "duration_seconds": duration,
        "fps": fps,
        "aspect_ratio": aspect_ratio,
        "shot_mode": shot_mode,
        "motion_intensity": motion_intensity,
    }


def analyze_and_question(
    image: str | None,
    description: str,
    duration: float,
    fps: int,
    aspect_ratio: str,
    shot_mode_label: str,
    intensity_label: str,
):
    if not image:
        raise gr.Error("请先上传一张首帧图片。")
    if not description.strip():
        raise gr.Error("请提供人物、事物、环境或动作的基础描述。")

    shot_mode = "single_take" if shot_mode_label == "单一连续镜头" else "multi_shot"
    intensity = {
        "保守（优先一致性）": "conservative",
        "电影感（推荐）": "cinematic",
        "强运镜": "dynamic",
    }[intensity_label]
    try:
        analysis = director.analyze_image(image, description)
        plan = director.plan_questions(
            analysis,
            description,
            _known_settings(duration, fps, aspect_ratio, shot_mode, intensity),
        )
    except OllamaError as exc:
        raise gr.Error(str(exc)) from exc

    if plan.questions:
        questions = "\n\n".join(
            f"{index}. {q.question}\n   默认：{q.default}\n   原因：{q.reason}"
            for index, q in enumerate(plan.questions, 1)
        )
        questions += "\n\n请在下面按序回答；不确定的项目可以写“使用默认值”。"
    else:
        questions = "信息已经足够。可以直接生成；留空将采用导演建议。"

    state = {
        "analysis": analysis.model_dump(),
        "description": description,
        "image_path": image,
        "shot_mode": shot_mode,
        "intensity": intensity,
    }
    return (
        state,
        json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2),
        questions,
        gr.Column(visible=False),
        gr.Column(visible=True),
        gr.Column(visible=False),
    )


def generate_first_frame(
    state: dict[str, Any] | None,
    instruction: str,
    current_prompt: str,
    aspect_ratio: str,
):
    instruction = instruction.strip()
    current_prompt = current_prompt.strip()
    if not instruction and not current_prompt:
        raise gr.Error("请先填写图片创意，或直接填写英文生成提示词。")
    try:
        summary = "使用手动编辑后的提示词。"
        prompt = current_prompt
        if instruction:
            designed = director.design_image_prompt(
                instruction,
                previous_prompt=current_prompt,
                aspect_ratio=aspect_ratio,
            )
            prompt = designed.prompt_en.strip()
            summary = designed.change_summary_zh
        width, height = IMAGE_SIZES[aspect_ratio]
        prompt_id, image_path = comfy.generate_image(
            prompt,
            width=width,
            height=height,
        )
    except OllamaError as exc:
        raise gr.Error(str(exc)) from exc
    except ComfyUIError as exc:
        raise gr.Error(str(exc)) from exc

    next_state = dict(state or {})
    next_state["generated_image_prompt"] = prompt
    next_state["generated_image_path"] = str(image_path)
    return (
        next_state,
        str(image_path),
        prompt,
        "",
        f"生成完成：{summary}  ComfyUI 任务 ID：`{prompt_id}`",
    )


def generate_prompt(
    state: dict[str, Any] | None,
    answers: str,
    duration: float,
    fps: int,
    aspect_ratio: str,
):
    if not state:
        raise gr.Error("请先点击“分析图片并生成追问”。")
    try:
        result = director.direct(
            ImageAnalysis.model_validate(state["analysis"]),
            state["description"],
            answers,
            duration=duration,
            fps=fps,
            aspect_ratio=aspect_ratio,
            shot_mode=state["shot_mode"],
            motion_intensity=state["intensity"],
        )
    except OllamaError as exc:
        raise gr.Error(str(exc)) from exc

    shot_prompts = "\n\n".join(
        f"### Shot {shot.number} · {shot.duration_seconds:g}s\n\n{shot.prompt_en}"
        for shot in result.shots
    )
    notes = (
        f"## {result.title}\n\n{result.director_notes_zh}\n\n"
        f"创作意图：{result.creative_intent}\n\n"
        f"实际帧数：{result.parameters.num_frames} @ {result.parameters.fps} fps\n\n"
        + "连续性约束：\n"
        + "\n".join(f"- {item}" for item in result.continuity_constraints)
    )
    next_state = dict(state)
    next_state["result"] = result.model_dump()
    return (
        next_state,
        result.final_prompt_en,
        result.negative_prompt_en,
        shot_prompts,
        notes,
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        gr.Column(visible=False),
        gr.Column(visible=True),
    )


def generate_video(
    state: dict[str, Any] | None,
    final_prompt: str,
    negative_prompt: str,
):
    if not state or not state.get("result") or not state.get("image_path"):
        raise gr.Error("请先生成电影级提示词。")
    try:
        result = DirectorResult.model_validate(state["result"]).model_copy(
            update={
                "final_prompt_en": final_prompt.strip(),
                "negative_prompt_en": negative_prompt.strip(),
            }
        )
        prompt_id, video_path = comfy.generate(
            state["image_path"],
            result,
        )
    except ComfyUIError as exc:
        raise gr.Error(str(exc)) from exc
    return (
        str(video_path),
        f"生成完成。已使用正向提示词、负向提示词和 {len(result.shots)} 个分镜提示词。"
        f"ComfyUI 任务 ID：`{prompt_id}`",
    )


def frame_preview(duration: float, fps: int) -> str:
    frames = legal_frame_count(duration, fps)
    return f"LTX 合法帧数：{frames} 帧；实际时长约 {frames / fps:.2f} 秒"


def check_ollama() -> str:
    ok, message = director.client.model_available()
    return ("[正常] " if ok else "[注意] ") + message


def check_comfy() -> str:
    ok, message = comfy.available()
    return ("[正常] " if ok else "[注意] ") + message


def show_analysis_busy():
    return gr.HTML(
        value=BUSY_OVERLAY_HTML.format(
            title="正在分析画面",
            message="Ollama 正在识别人物、环境、构图和可运动空间……",
        ),
        visible=True,
    )


def show_generation_busy():
    return gr.HTML(
        value=BUSY_OVERLAY_HTML.format(
            title="正在设计电影镜头",
            message="导演 Agent 正在规划动作、时间线与摄影机运动……",
        ),
        visible=True,
    )


def show_comfy_busy():
    return gr.HTML(
        value=BUSY_OVERLAY_HTML.format(
            title="正在生成 LTX-2.5 视频",
            message="正在上传首帧并等待 ComfyUI 完成工作流……",
        ),
        visible=True,
    )


def show_image_busy():
    return gr.HTML(
        value=BUSY_OVERLAY_HTML.format(
            title="正在生成首帧图片",
            message="正在整理本轮修改要求，并等待 Z-Image Turbo 完成图片……",
        ),
        visible=True,
    )


def hide_busy():
    return gr.HTML(visible=False)


def show_setup():
    return (
        gr.Column(visible=True),
        gr.Column(visible=False),
        gr.Column(visible=False),
    )


def show_questions():
    return gr.Column(visible=True), gr.Column(visible=False)


def reset_to_initial():
    return (
        None,
        None,
        "",
        "",
        "",
        6,
        24,
        "16:9",
        "单一连续镜头",
        "电影感（推荐）",
        frame_preview(6, 24),
        "",
        "",
        "",
        "",
        "",
        "",
        None,
        "",
        "",
        gr.Column(visible=True),
        gr.Column(visible=False),
        gr.Column(visible=False),
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="LTX-2.5 电影提示词导演") as demo:
        busy_overlay = gr.HTML(visible=False, elem_id="busy-overlay")
        gr.Markdown(
            "# LTX-2.5 电影提示词导演\n"
            "按照三个步骤完成：提供创意 → 回答导演问题 → 获取提示词。"
        )
        state = gr.State()

        with gr.Row():
            gr.Markdown("**① 提供创意**　→　**② 补充细节**　→　**③ 获取结果**")

        with gr.Column(visible=True) as setup_panel:
            gr.Markdown("## 第一步：图片与创意")
            with gr.Row():
                with gr.Column(scale=1):
                    image = gr.Image(type="filepath", label="首帧图片")
                with gr.Column(scale=1):
                    description = gr.Textbox(
                        label="你希望画面如何运动？",
                        lines=8,
                        placeholder="例如：雨夜街道中的女人向前走，最后回头看向镜头……",
                    )
            with gr.Accordion("没有首帧？用 Z-Image Turbo 生成", open=False):
                gr.Markdown(
                    "描述你想要的首帧并生成。之后可继续填写修改要求反复生成；"
                    "也可以直接编辑英文提示词后再次生成。当前结果会自动填入上方首帧图片。"
                )
                image_instruction = gr.Textbox(
                    label="图片创意 / 本轮修改要求",
                    lines=4,
                    placeholder="首次示例：雨夜东京街头，一位穿红色风衣的女人……\n"
                    "修改示例：保留人物和场景，把镜头改成更低的机位。",
                )
                image_generation_prompt = gr.Textbox(
                    label="实际发送给图片模型的英文提示词（可编辑）",
                    lines=7,
                )
                generate_image_button = gr.Button("生成首帧 / 按要求再次生成")
                image_generation_status = gr.Markdown()
            with gr.Accordion("高级生成设置（可选）", open=False):
                gr.Markdown("不确定时保留默认值即可，导演 Agent 会据此规划镜头。")
                with gr.Row():
                    duration = gr.Slider(2, 20, value=6, step=0.5, label="时长（秒）")
                    fps = gr.Dropdown([24, 25, 30], value=24, label="FPS")
                frame_info = gr.Markdown(frame_preview(6, 24))
                aspect_ratio = gr.Dropdown(
                    ["16:9", "9:16", "1:1", "2.39:1"], value="16:9", label="画幅"
                )
                shot_mode = gr.Radio(
                    ["单一连续镜头", "多镜头分镜"], value="单一连续镜头", label="镜头模式"
                )
                intensity = gr.Radio(
                    ["保守（优先一致性）", "电影感（推荐）", "强运镜"],
                    value="电影感（推荐）",
                    label="运动强度",
                )
            with gr.Row():
                analyze_button = gr.Button("继续：分析图片", variant="primary")
                status_button = gr.Button("检查 Ollama", scale=0)
                comfy_status_button = gr.Button("检查 ComfyUI", scale=0)
            with gr.Accordion("连接状态", open=False):
                status = gr.Markdown()
                comfy_connection = gr.Markdown()

        with gr.Column(visible=False) as question_panel:
            gr.Markdown("## 第二步：补充导演需要的细节")
            questions = gr.Markdown()
            answers = gr.Textbox(
                label="你的回答",
                lines=7,
                placeholder="按问题顺序回答；也可以写“全部使用默认值”。",
            )
            with gr.Row():
                back_to_setup = gr.Button("返回修改图片或设置")
                generate_button = gr.Button("生成电影级提示词", variant="primary")
            with gr.Accordion("查看图片分析", open=False):
                analysis_json = gr.Code(language="json", label="Image analysis")

        with gr.Column(visible=False) as result_panel:
            gr.Markdown("## 第三步：电影级提示词")
            final_prompt = gr.Textbox(lines=12, label="LTX-2.5 正向提示词")
            generate_video_button = gr.Button("发送到 ComfyUI 并生成视频", variant="primary")
            comfy_status = gr.Markdown()
            comfy_video = gr.Video(label="ComfyUI 生成结果")
            with gr.Row():
                back_to_questions = gr.Button("返回修改回答")
                start_over = gr.Button("返回初始界面")
            with gr.Accordion("负向提示词", open=False):
                negative_prompt = gr.Textbox(lines=6)
            with gr.Accordion("分镜提示词", open=False):
                shot_prompts = gr.Markdown()
            with gr.Accordion("中文导演说明", open=False):
                director_notes = gr.Markdown()
            with gr.Accordion("完整结构化 JSON（高级）", open=False):
                result_json = gr.Code(language="json")

        duration.change(frame_preview, [duration, fps], frame_info)
        fps.change(frame_preview, [duration, fps], frame_info)
        status_button.click(check_ollama, outputs=status)
        comfy_status_button.click(check_comfy, outputs=comfy_connection)
        image_started = generate_image_button.click(
            show_image_busy,
            outputs=busy_overlay,
            show_progress="hidden",
        )
        image_finished = image_started.then(
            generate_first_frame,
            [state, image_instruction, image_generation_prompt, aspect_ratio],
            [
                state,
                image,
                image_generation_prompt,
                image_instruction,
                image_generation_status,
            ],
            show_progress="hidden",
        )
        image_finished.then(hide_busy, outputs=busy_overlay, show_progress="hidden")
        analysis_started = analyze_button.click(
            show_analysis_busy,
            outputs=busy_overlay,
            show_progress="hidden",
        )
        analysis_finished = analysis_started.then(
            analyze_and_question,
            [image, description, duration, fps, aspect_ratio, shot_mode, intensity],
            [state, analysis_json, questions, setup_panel, question_panel, result_panel],
            show_progress="hidden",
        )
        analysis_finished.then(hide_busy, outputs=busy_overlay, show_progress="hidden")

        generation_started = generate_button.click(
            show_generation_busy,
            outputs=busy_overlay,
            show_progress="hidden",
        )
        generation_finished = generation_started.then(
            generate_prompt,
            [state, answers, duration, fps, aspect_ratio],
            [
                state,
                final_prompt,
                negative_prompt,
                shot_prompts,
                director_notes,
                result_json,
                question_panel,
                result_panel,
            ],
            show_progress="hidden",
        )
        generation_finished.then(hide_busy, outputs=busy_overlay, show_progress="hidden")
        comfy_started = generate_video_button.click(
            show_comfy_busy,
            outputs=busy_overlay,
            show_progress="hidden",
        )
        comfy_finished = comfy_started.then(
            generate_video,
            inputs=[state, final_prompt, negative_prompt],
            outputs=[comfy_video, comfy_status],
            show_progress="hidden",
        )
        comfy_finished.then(hide_busy, outputs=busy_overlay, show_progress="hidden")
        back_to_setup.click(
            show_setup,
            outputs=[setup_panel, question_panel, result_panel],
        )
        back_to_questions.click(
            show_questions,
            outputs=[question_panel, result_panel],
        )
        start_over.click(
            reset_to_initial,
            outputs=[
                state,
                image,
                description,
                image_instruction,
                image_generation_prompt,
                duration,
                fps,
                aspect_ratio,
                shot_mode,
                intensity,
                frame_info,
                answers,
                analysis_json,
                questions,
                final_prompt,
                negative_prompt,
                result_json,
                comfy_video,
                comfy_status,
                image_generation_status,
                setup_panel,
                question_panel,
                result_panel,
            ],
        )
    return demo.queue()
