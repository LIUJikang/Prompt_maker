from __future__ import annotations

import copy
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .schemas import DirectorResult


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _url(self, path: str) -> str:
        return f"{self.settings.comfy_url.rstrip('/')}/{path.lstrip('/')}"

    def available(self) -> tuple[bool, str]:
        try:
            response = httpx.get(self._url("system_stats"), timeout=10)
            response.raise_for_status()
            return True, f"ComfyUI 已连接：{self.settings.comfy_url}"
        except Exception as exc:
            return False, f"无法连接 ComfyUI：{exc}"

    def load_workflow(self) -> dict[str, Any]:
        path = Path(self.settings.comfy_workflow)
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            workflow = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ComfyUIError(f"无法读取 ComfyUI API 工作流 {path}：{exc}") from exc
        if not isinstance(workflow, dict) or "395" not in workflow:
            raise ComfyUIError("工作流不是预期的 API 格式，或缺少 LoadImage 节点 395。")
        return workflow

    def upload_image(self, image_path: str | Path) -> str:
        path = Path(image_path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as image_file:
                response = httpx.post(
                    self._url("upload/image"),
                    files={"image": (path.name, image_file, mime)},
                    data={"type": "input", "overwrite": "true"},
                    timeout=120,
                )
            response.raise_for_status()
            uploaded = response.json()
        except (OSError, httpx.HTTPError, ValueError) as exc:
            raise ComfyUIError(f"向 ComfyUI 上传首帧失败：{exc}") from exc
        name = uploaded.get("name")
        if not name:
            raise ComfyUIError(f"ComfyUI 上传响应缺少文件名：{uploaded}")
        subfolder = uploaded.get("subfolder", "")
        return f"{subfolder}/{name}" if subfolder else name

    def prepare_workflow(
        self,
        *,
        image_name: str,
        result: DirectorResult,
    ) -> dict[str, Any]:
        workflow = copy.deepcopy(self.load_workflow())
        required = ("395", "398:376", "398:373", "398:378", "398:361", "398:339")
        missing = [node_id for node_id in required if node_id not in workflow]
        if missing:
            raise ComfyUIError(f"工作流缺少必要节点：{', '.join(missing)}")

        workflow["395"]["inputs"]["image"] = image_name
        workflow["398:376"]["inputs"]["value"] = self.compose_positive_prompt(result)
        workflow["398:373"]["inputs"]["text"] = result.negative_prompt_en
        workflow["398:361"]["inputs"]["value"] = result.parameters.fps
        # 直接写入导演计算出的 8n+1 帧数，避免工作流的整数秒换算造成时长偏差。
        workflow["398:378"]["inputs"]["expression"] = str(result.parameters.num_frames)
        workflow["398:339"]["inputs"]["noise_seed"] = int.from_bytes(
            uuid.uuid4().bytes[:8], "big"
        ) & ((1 << 63) - 1)
        return workflow

    @staticmethod
    def compose_positive_prompt(result: DirectorResult) -> str:
        """Combine the overall direction with every shot's temporal instructions."""
        final_prompt = result.final_prompt_en.strip()
        constraints = [item.strip() for item in result.continuity_constraints if item.strip()]
        shot_sections: list[str] = []
        for shot in result.shots:
            shot_prompt = shot.prompt_en.strip()
            if not shot_prompt or shot_prompt in final_prompt:
                continue
            shot_sections.append(
                f"Shot {shot.number} ({shot.duration_seconds:g} seconds): {shot_prompt}"
            )
        sections = [final_prompt]
        if constraints:
            sections.append(
                "Strict visual identity and continuity constraints:\n- "
                + "\n- ".join(constraints)
            )
        if shot_sections:
            sections.append(
                "Temporal shot plan. Preserve every identity, appearance, anatomy, "
                "material, marking, costume, prop, environment, lighting, and spatial "
                "continuity constraint throughout:\n"
                + "\n".join(shot_sections)
            )
        return "\n\n".join(sections)

    def queue(self, workflow: dict[str, Any]) -> str:
        try:
            response = httpx.post(
                self._url("prompt"),
                json={"prompt": workflow, "client_id": uuid.uuid4().hex},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            detail = getattr(response, "text", "") if "response" in locals() else ""
            raise ComfyUIError(f"ComfyUI 拒绝工作流：{exc}\n{detail[:1000]}") from exc
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI 未返回任务 ID：{payload}")
        return prompt_id

    def wait_for_output(self, prompt_id: str) -> dict[str, str]:
        deadline = time.monotonic() + self.settings.comfy_timeout
        while time.monotonic() < deadline:
            try:
                response = httpx.get(self._url(f"history/{prompt_id}"), timeout=30)
                response.raise_for_status()
                history = response.json().get(prompt_id)
            except (httpx.HTTPError, ValueError) as exc:
                raise ComfyUIError(f"读取 ComfyUI 任务状态失败：{exc}") from exc
            if history:
                status = history.get("status", {})
                if status.get("status_str") == "error" or status.get("completed") is False:
                    messages = status.get("messages", [])
                    raise ComfyUIError(f"ComfyUI 生成失败：{messages}")
                outputs = history.get("outputs", {})
                # 优先读取工作流的 SaveVideo 节点，避免误取预览图等中间产物。
                output = self._find_file(outputs.get("75", outputs))
                if output:
                    return output
            time.sleep(2)
        raise ComfyUIError(f"等待 ComfyUI 超时（任务 {prompt_id}）。")

    def _find_file(self, value: Any) -> dict[str, str] | None:
        if isinstance(value, dict):
            if value.get("filename"):
                return {
                    "filename": str(value["filename"]),
                    "subfolder": str(value.get("subfolder", "")),
                    "type": str(value.get("type", "output")),
                }
            for child in value.values():
                found = self._find_file(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = self._find_file(child)
                if found:
                    return found
        return None

    def download_output(self, output: dict[str, str], prompt_id: str) -> Path:
        try:
            response = httpx.get(self._url("view"), params=output, timeout=300)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ComfyUIError(f"下载 ComfyUI 视频失败：{exc}") from exc
        suffix = Path(output["filename"]).suffix or ".mp4"
        destination = Path.cwd() / "outputs" / "comfyui" / f"{prompt_id}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return destination

    def generate(self, image_path: str | Path, result: DirectorResult) -> tuple[str, Path]:
        image_name = self.upload_image(image_path)
        prompt_id = self.queue(
            self.prepare_workflow(image_name=image_name, result=result)
        )
        output = self.wait_for_output(prompt_id)
        return prompt_id, self.download_output(output, prompt_id)
