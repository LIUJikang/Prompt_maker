from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gradio as gr

from .config import settings
from .comfy_client import ComfyUIClient, ComfyUIError
from .ollama_client import OllamaError
from .schemas import DirectorResult, ImageAnalysis
from .workflow import PromptDirector, legal_frame_count
from .video_frames import FrameExtractionError, extract_video_frames


director = PromptDirector(settings)
comfy = ComfyUIClient(settings)

IMAGE_SIZES = {
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "1:1": (1024, 1024),
    "2.39:1": (1536, 640),
}

CHARACTER_PRESETS = {
    "清贵仙门少年": """[角色一致性锚点：清贵仙门少年] 一名约17岁的东亚少年，清瘦挺拔，窄椭圆脸，平直浓眉，内双深褐眼，鼻梁笔直，薄唇，冷白肤色；长黑发高束成整齐马尾，以小型白玉冠固定。穿月白色交领窄袖仙门弟子袍，银灰滚边，腰间一枚圆形白玉门派佩，背负细长直剑。神情克制清澈。后续修改保持同一脸型、五官比例、发型、玉冠、服装和玉佩。""",
    "灵秀仙门少女": """[角色一致性锚点：灵秀仙门少女] 一名约17岁的东亚少女，身形轻盈，柔和鹅蛋脸，细弯眉，清亮杏眼，小巧直鼻，自然粉唇，浅暖肤色；乌黑长发半束，左右各留一缕鬓发，以淡青玉簪固定。穿淡青色交领广袖仙裙，白色内衬，窄银腰带，腰侧悬一枚水滴形青玉佩。气质灵动但不幼态。后续修改保持同一脸型、五官比例、发型、玉簪、服装和玉佩。""",
    "冷峻青年剑修": """[角色一致性锚点：冷峻青年剑修] 一名约26岁的东亚男性，肩背挺直，轮廓分明的长方脸，剑眉，狭长深褐眼，直鼻，清晰下颌线，薄唇，健康浅肤色；黑色长发束成高马尾，以暗银发扣固定。穿深靛蓝窄袖剑修长袍、黑色皮革护腕和暗银腰封，背负一柄黑鞘长剑。神情沉静警觉。后续修改保持同一脸部几何、发型、发扣、服装、护腕和剑。""",
    "温雅青年女修": """[角色一致性锚点：温雅青年女修] 一名约25岁的东亚女性，修长匀称，端正椭圆脸，平缓柳眉，深褐凤眼，鼻梁秀直，唇形清晰，象牙暖肤色；浓黑长发低挽成简洁发髻，以一支木兰白玉簪固定。穿象牙白与浅紫相间的交领长裙，细密云纹织边，腰挂小型紫色香囊。神态温和坚定。后续修改保持同一脸型、五官比例、发髻、玉簪、云纹服装和香囊。""",
    "高贵仙门公子": """[角色一致性锚点：高贵仙门公子] 一名约28岁的东亚男性，身材高挑，精致但成熟的窄长脸，整齐剑眉，深褐丹凤眼，高直鼻梁，薄唇，冷白肤色；墨黑长发一丝不乱地半束，以镂空金冠固定。穿层叠的深紫与黑色锦缎长袍，金线山河暗纹，宽黑玉腰带，右手戴一枚深绿色扳指。姿态从容高贵。后续修改保持同一脸部几何、金冠、锦缎纹样、黑玉腰带和扳指。""",
    "高贵仙门圣女": """[角色一致性锚点：高贵仙门圣女] 一名约27岁的东亚女性，身形端庄，精致鹅蛋脸，长直眉，深褐凤眼，直鼻，轮廓清楚的朱色唇，冷白肤色；乌黑长发高挽，以对称金色莲花发冠和两枚细珠链固定。穿白金双色层叠仙裙，金线莲纹，结构挺括的宽腰封，耳戴小型珍珠坠。神情平静威严。后续修改保持同一脸型、五官比例、莲花发冠、珠链、莲纹服装和耳饰。""",
    "贫寒青年散修": """[角色一致性锚点：贫寒青年散修] 一名约24岁的东亚男性，精瘦结实，略方的普通脸型，浓直眉，深褐眼，鼻梁微宽，嘴角有一道短浅旧疤，日晒小麦肤色；粗黑长发用褪色灰布带低束。穿洗旧的灰褐色粗麻短袍，补丁袖口，磨损皮腰带，背负用布缠柄的旧铁剑。神态坚韧谨慎。后续修改保持同一普通脸、嘴角浅疤、肤色、布带、补丁衣物和旧剑。""",
    "贫寒采药女修": """[角色一致性锚点：贫寒采药女修] 一名约23岁的东亚女性，身材纤瘦有力，略圆的普通脸型，平直眉，深褐圆眼，鼻尖微圆，自然唇色，日晒暖肤色，左眉尾有一颗小痣；黑色长发编成单辫，以麻绳固定。穿褪色青灰粗布窄袖衣裙、棕色布腰带，背竹编药篓，腰挂旧葫芦。神情专注朴实。后续修改保持同一普通脸、眉尾小痣、肤色、单辫、粗布衣裙、药篓和葫芦。""",
    "威严中年宗主": """[角色一致性锚点：威严中年宗主] 一名约46岁的东亚男性，宽肩挺拔，棱角清晰的方脸，浓黑剑眉夹少量灰色，深褐眼，直鼻，唇上与下颌留修整整齐的短须，眼角有自然细纹；黑发夹灰，高束于深色玉冠。穿墨青色厚重宗主长袍，暗金回纹宽边，深玉腰佩。神态威严沉着。后续修改保持同一成熟脸型、短须、眼角纹、灰黑发、玉冠、回纹长袍和腰佩。""",
    "端庄中年女长老": """[角色一致性锚点：端庄中年女长老] 一名约43岁的东亚女性，身形端正，成熟椭圆脸，清晰长眉，沉静深褐眼，挺直鼻梁，唇色克制，浅暖肤色，眼角有细微自然纹理；乌黑长发夹少量银丝，低挽成圆髻，以深青玉簪固定。穿深青与灰银色层叠长袍，细密竹叶暗纹，佩一串深色木珠。神态理性从容。后续修改保持同一成熟脸、自然纹理、银丝发髻、玉簪、竹纹长袍和木珠。""",
    "普通大众男修": """[角色一致性锚点：普通大众男修] 一名约31岁的东亚男性，中等身高和普通体型，略宽的椭圆脸，不对称但自然的平眉，普通深褐眼，鼻梁中等，略厚嘴唇，健康暖肤色；黑发简单低束，用棕色木簪固定。穿无门派标志的棕灰色棉麻交领袍，素色布腰带，携普通旧布包。相貌自然可信，不英俊化、不贵族化。后续修改保持同一大众脸、五官比例、木簪、素袍和布包。""",
    "普通大众女修": """[角色一致性锚点：普通大众女修] 一名约30岁的东亚女性，中等身高和普通体型，柔和偏方的脸型，自然平眉，普通深褐眼，鼻梁中等，自然唇形，健康暖肤色，右脸颊靠近耳侧有一颗很小的痣；黑发简单盘成低髻，用无装饰木簪固定。穿无门派标志的灰蓝棉麻交领衣裙和素色布腰带，提一个小布包。相貌自然可信，不网红化、不贵族化。后续修改保持同一大众脸、脸颊小痣、低髻、木簪、素衣和布包。""",
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
        if settings.release_models_between_stages:
            comfy.release_models()
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
    seed_value: float | int | None,
    lock_seed: bool,
):
    instruction = instruction.strip()
    current_prompt = current_prompt.strip()
    if not instruction and not current_prompt:
        raise gr.Error("请先填写图片创意，或直接填写英文生成提示词。")
    try:
        if instruction and settings.release_models_between_stages:
            comfy.release_models()
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
        if settings.release_models_between_stages:
            director.client.unload_model()
        requested_seed = None
        if lock_seed and seed_value is not None and int(seed_value) >= 0:
            requested_seed = int(seed_value)
        prompt_id, image_path, used_seed = comfy.generate_image(
            prompt,
            width=width,
            height=height,
            seed=requested_seed,
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
        used_seed,
        f"生成完成：{summary}  Seed：`{used_seed}`；ComfyUI 任务 ID：`{prompt_id}`",
    )


def add_character_anchor(current: str, anchor: str) -> str:
    current = current.strip()
    if anchor in current:
        gr.Info("这个角色锚点已经添加。")
        return current
    return f"{current}\n\n{anchor}".strip()


def use_generated_as_video_frame(
    generated_image: str | None, image_aspect_ratio: str
):
    if not generated_image:
        raise gr.Error("请先生成一张图片。")
    gr.Info("已设为视频首帧，并切换到视频导演页面。")
    return (
        generated_image,
        image_aspect_ratio,
        gr.Tabs(selected="video_director"),
    )


def reset_image_workshop():
    return None, None, "", "", "16:9", True, -1, ""


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
        if settings.release_models_between_stages:
            comfy.release_models()
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
        if settings.release_models_between_stages:
            director.client.unload_model()
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
        str(video_path),
        f"生成完成。已使用正向提示词、负向提示词和 {len(result.shots)} 个分镜提示词。"
        f"ComfyUI 任务 ID：`{prompt_id}`",
    )


def capture_video_frames(video_path: str | None, count: int, tail_seconds: float):
    if not video_path:
        return empty_frame_candidates("请先生成视频。")
    try:
        paths = [str(path) for path in extract_video_frames(video_path, int(count), tail_seconds)]
    except FrameExtractionError as exc:
        # Extraction failure must not hide a successfully generated video.
        return empty_frame_candidates(f"视频已保留，截帧未完成：{exc}")
    return (
        [(path, Path(path).name) for path in paths],
        paths,
        gr.Dropdown(choices=[(Path(path).name, path) for path in paths], value=paths[-1]),
        f"已保存 {len(paths)} 张原尺寸 PNG：`{Path(paths[0]).parent}`。默认选择最后一帧。",
        paths,
    )


def empty_frame_candidates(message: str = ""):
    return [], [], gr.Dropdown(choices=[], value=None), message, []


def use_captured_frame(
    selected: str | None, paths: list[str] | None,
    duration: float, fps: int, aspect_ratio: str, shot_mode: str, intensity: str,
):
    if not selected or selected not in (paths or []) or not Path(selected).is_file():
        raise gr.Error("请先截取并选择一张有效图片。")
    values = list(reset_to_initial())
    values[1] = selected
    values[3:9] = [
        duration, fps, aspect_ratio, shot_mode, intensity, frame_preview(duration, fps)
    ]
    gr.Info("已设为下一段视频首帧，请填写新动作并重新分析图片。")
    return tuple(values)


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


def hide_busy_after_failure():
    gr.Warning("任务未完成。全屏等待界面已解除，请查看页面提示和启动终端中的错误信息。")
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
        None, None, "", 6, 24, "16:9", "单一连续镜头", "电影感（推荐）",
        frame_preview(6, 24), "", "", "", "", "", "", "", "", None, "",
        gr.Column(visible=True), gr.Column(visible=False), gr.Column(visible=False),
        None, *empty_frame_candidates(),
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="LTX-2.5 电影提示词导演") as demo:
        busy_overlay = gr.HTML(visible=False, elem_id="busy-overlay")
        gr.Markdown(
            "# 仙侠图片与 LTX-2.5 电影工作台\n"
            "先在图片工坊创作首帧，或直接进入视频导演上传已有图片。"
        )
        state = gr.State()
        image_state = gr.State()
        source_video = gr.State()
        captured_paths = gr.State([])

        with gr.Tabs(selected="video_director") as main_tabs:
            with gr.Tab("视频导演", id="video_director"):
                with gr.Row():
                    gr.Markdown("**① 提供创意**　→　**② 补充细节**　→　**③ 获取结果**")

                with gr.Column(visible=True) as setup_panel:
                    gr.Markdown("## 第一步：首帧与视频创意")
                    with gr.Row():
                        with gr.Column(scale=1):
                            image = gr.Image(type="filepath", label="首帧图片")
                        with gr.Column(scale=1):
                            description = gr.Textbox(
                                label="你希望画面如何运动？",
                                lines=8,
                                placeholder="例如：雪山之巅的剑修缓慢拔剑，最后看向镜头……",
                            )
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
                            value="电影感（推荐）", label="运动强度",
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
                        label="你的回答", lines=7,
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
                    gr.Markdown("### 截帧与接续视频\n生成后自动截取；可调整范围再次截取。")
                    with gr.Row():
                        capture_count = gr.Slider(1, 12, value=4, step=1, label="截取张数")
                        capture_tail = gr.Slider(
                            0, 20, value=1, step=0.1,
                            label="截取末尾多少秒（0 = 整段均匀截取）",
                        )
                    capture_button = gr.Button("重新截取并保存图片")
                    frame_gallery = gr.Gallery(
                        label="候选首帧（按时间排列）", columns=4, interactive=False,
                    )
                    frame_files = gr.File(label="已保存的 PNG 图片", file_count="multiple")
                    selected_frame = gr.Dropdown(label="选择下一段首帧", choices=[])
                    capture_status = gr.Markdown()
                    use_frame_button = gr.Button("使用选中图片作为下一段首帧", variant="primary")
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

            with gr.Tab("仙侠首帧工坊", id="image_workshop"):
                gr.Markdown(
                    "## Z-Image Turbo 仙侠首帧工坊\n"
                    "输入简单场景，再点击角色候选加入稳定身份锚点。可以加入多名角色；"
                    "请在创意中补充他们的左右位置、关系和动作。"
                )
                with gr.Row():
                    with gr.Column(scale=1):
                        generated_image = gr.Image(type="filepath", label="生成图片")
                        with gr.Row():
                            use_image_button = gr.Button("使用此图作为视频首帧", variant="primary")
                            reset_image_button = gr.Button("清空图片工坊")
                    with gr.Column(scale=1):
                        image_instruction = gr.Textbox(
                            label="图片创意 / 本轮修改要求",
                            lines=8,
                            placeholder="例如：云海之上的仙门石桥，黄昏逆光。先点击下方人物按钮，"
                            "再补充：少年站在左侧，女长老站在右侧，两人隔着三步对视。",
                        )
                        image_generation_prompt = gr.Textbox(
                            label="Ollama 完善后的英文提示词（可编辑）", lines=10,
                        )

                gr.Markdown("### 添加仙侠人物")
                gr.Markdown(
                    "每个按钮会加入一段固定的年龄、脸型、五官、发型、服装和配饰锚点。"
                    "再次修改图片时保留锚点并锁定 Seed，可减少人物漂移。"
                )
                preset_buttons: list[tuple[gr.Button, str]] = []
                preset_items = list(CHARACTER_PRESETS.items())
                for start in range(0, len(preset_items), 4):
                    with gr.Row():
                        for label, anchor in preset_items[start : start + 4]:
                            button = gr.Button(label, size="sm")
                            preset_buttons.append((button, anchor))

                with gr.Row():
                    image_aspect_ratio = gr.Dropdown(
                        ["16:9", "9:16", "1:1", "2.39:1"], value="16:9", label="图片画幅"
                    )
                    lock_seed = gr.Checkbox(
                        value=True, label="锁定 Seed（再次生成时保持人物更稳定）"
                    )
                    image_seed = gr.Number(value=-1, precision=0, label="Seed（-1 表示首次随机）")
                generate_image_button = gr.Button(
                    "完善提示词并生成 / 按本轮要求再次生成", variant="primary"
                )
                image_generation_status = gr.Markdown()

        duration.change(frame_preview, [duration, fps], frame_info)
        fps.change(frame_preview, [duration, fps], frame_info)
        status_button.click(check_ollama, outputs=status)
        comfy_status_button.click(check_comfy, outputs=comfy_connection)
        for preset_button, anchor in preset_buttons:
            preset_button.click(
                lambda current, preset=anchor: add_character_anchor(current, preset),
                inputs=image_instruction,
                outputs=image_instruction,
                show_progress="hidden",
            )
        image_started = generate_image_button.click(
            show_image_busy,
            outputs=busy_overlay,
            show_progress="hidden",
        )
        image_finished = image_started.then(
            generate_first_frame,
            [
                image_state, image_instruction, image_generation_prompt,
                image_aspect_ratio, image_seed, lock_seed,
            ],
            [
                image_state, generated_image, image_generation_prompt,
                image_instruction, image_seed, image_generation_status,
            ],
            show_progress="hidden",
        )
        image_finished.success(hide_busy, outputs=busy_overlay, show_progress="hidden")
        image_finished.failure(
            hide_busy_after_failure, outputs=busy_overlay, show_progress="hidden"
        )
        use_image_button.click(
            use_generated_as_video_frame,
            [generated_image, image_aspect_ratio],
            [image, aspect_ratio, main_tabs],
        )
        reset_image_button.click(
            reset_image_workshop,
            outputs=[
                image_state, generated_image, image_instruction,
                image_generation_prompt, image_aspect_ratio, lock_seed,
                image_seed, image_generation_status,
            ],
        )
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
        analysis_finished.success(hide_busy, outputs=busy_overlay, show_progress="hidden")
        analysis_finished.failure(
            hide_busy_after_failure, outputs=busy_overlay, show_progress="hidden"
        )

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
        generation_finished.success(hide_busy, outputs=busy_overlay, show_progress="hidden")
        generation_finished.failure(
            hide_busy_after_failure, outputs=busy_overlay, show_progress="hidden"
        )
        comfy_started = generate_video_button.click(
            show_comfy_busy,
            outputs=busy_overlay,
            show_progress="hidden",
        )
        comfy_finished = comfy_started.then(
            generate_video,
            inputs=[state, final_prompt, negative_prompt],
            outputs=[comfy_video, source_video, comfy_status],
            show_progress="hidden",
        )
        frame_outputs = [
            frame_gallery, frame_files, selected_frame, capture_status, captured_paths,
        ]
        captured = comfy_finished.success(
            capture_video_frames,
            inputs=[source_video, capture_count, capture_tail],
            outputs=frame_outputs,
        )
        captured.success(hide_busy, outputs=busy_overlay, show_progress="hidden")
        captured.failure(hide_busy_after_failure, outputs=busy_overlay, show_progress="hidden")
        capture_button.click(
            capture_video_frames,
            inputs=[source_video, capture_count, capture_tail],
            outputs=frame_outputs,
        )
        comfy_finished.failure(
            hide_busy_after_failure, outputs=busy_overlay, show_progress="hidden"
        )
        back_to_setup.click(
            show_setup,
            outputs=[setup_panel, question_panel, result_panel],
        )
        back_to_questions.click(
            show_questions,
            outputs=[question_panel, result_panel],
        )
        reset_outputs = [
                state,
                image,
                description,
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
                shot_prompts,
                director_notes,
                result_json,
                comfy_video,
                comfy_status,
                setup_panel,
                question_panel,
                result_panel,
                source_video,
                *frame_outputs,
            ]
        start_over.click(reset_to_initial, outputs=reset_outputs)
        use_frame_button.click(
            use_captured_frame,
            inputs=[selected_frame, captured_paths, duration, fps, aspect_ratio, shot_mode, intensity],
            outputs=reset_outputs,
        )
    return demo.queue()
