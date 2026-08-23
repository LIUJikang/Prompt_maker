from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def model_available(self) -> tuple[bool, str]:
        try:
            response = httpx.get(
                f"{self.settings.ollama_url}/api/tags",
                timeout=10,
            )
            response.raise_for_status()
            names = [item["name"] for item in response.json().get("models", [])]
            wanted = self.settings.ollama_model
            matched = wanted in names or any(name.split(":")[0] == wanted for name in names)
            if matched:
                return True, f"Ollama 已连接，模型 {wanted} 可用"
            return False, f"Ollama 已连接，但未找到 {wanted}。已有：{', '.join(names) or '无'}"
        except Exception as exc:
            return False, f"无法连接 Ollama：{exc}"

    def unload_model(self) -> tuple[bool, str]:
        """Best-effort release of the Ollama model before a ComfyUI generation."""
        try:
            response = httpx.post(
                f"{self.settings.ollama_url}/api/generate",
                json={
                    "model": self.settings.ollama_model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": 0,
                },
                timeout=60,
            )
            response.raise_for_status()
            return True, f"已释放 Ollama 模型 {self.settings.ollama_model}"
        except Exception as exc:
            return False, f"释放 Ollama 模型失败：{exc}"

    def _stream_chat(self, payload: dict[str, object]) -> tuple[str, str]:
        chunks: list[str] = []
        done_reason = ""
        timeout = httpx.Timeout(self.settings.request_timeout, connect=15)
        with httpx.stream(
            "POST",
            f"{self.settings.ollama_url}/api/chat",
            json=payload,
            timeout=timeout,
        ) as response:
            if response.is_error:
                body = response.read().decode(errors="replace")
                raise OllamaError(
                    f"Ollama HTTP {response.status_code}：{body[:500]}"
                )
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise OllamaError(
                        f"Ollama 返回了无法解析的流式数据：{line[:300]}"
                    ) from exc
                if event.get("error"):
                    raise OllamaError(f"Ollama 生成失败：{event['error']}")
                chunks.append(str(event.get("message", {}).get("content", "")))
                if event.get("done"):
                    done_reason = str(event.get("done_reason", "stop"))
        return "".join(chunks), done_reason

    def structured_chat(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        image_path: str | Path | None = None,
        temperature: float = 0.2,
    ) -> T:
        message: dict[str, object] = {"role": "user", "content": user}
        if image_path:
            image_bytes = Path(image_path).read_bytes()
            message["images"] = [base64.b64encode(image_bytes).decode("ascii")]

        base_messages = [
            {"role": "system", "content": system},
            message,
        ]
        payload: dict[str, object] = {
            "model": self.settings.ollama_model,
            "stream": True,
            "think": self.settings.ollama_think,
            "format": schema.model_json_schema(),
            "options": {
                "temperature": temperature,
                "num_predict": self.settings.ollama_num_predict,
            },
            "messages": base_messages,
        }
        try:
            last_error: Exception | None = None
            last_reason = ""
            attempts = max(1, self.settings.ollama_structured_retries + 1)
            for attempt in range(attempts):
                if attempt:
                    payload["messages"] = base_messages + [
                        {
                            "role": "user",
                            "content": (
                                "上一次输出被截断或不是合法 JSON。请重新从头输出完整、简洁、"
                                "严格符合 Schema 的 JSON；删除重复描述，并确保所有字符串、数组和"
                                "对象正确闭合。不要解释，不要 Markdown。"
                            ),
                        }
                    ]
                    payload["options"] = {
                        "temperature": min(temperature, 0.1),
                        "num_predict": self.settings.ollama_num_predict,
                    }
                content, last_reason = self._stream_chat(payload)
                if not content.strip():
                    last_error = ValueError("没有返回结构化内容")
                elif last_reason == "length":
                    last_error = ValueError(
                        f"输出达到 num_predict={self.settings.ollama_num_predict} 上限"
                    )
                else:
                    try:
                        return schema.model_validate(json.loads(content))
                    except (json.JSONDecodeError, ValueError) as exc:
                        last_error = exc

            reason = f"，结束原因：{last_reason}" if last_reason else ""
            raise OllamaError(
                f"Ollama 连续 {attempts} 次未返回完整有效的结构化 JSON{reason}。"
                f"最后错误：{last_error}。可提高 OLLAMA_NUM_PREDICT，或缩短任务描述。"
            ) from last_error
        except httpx.ConnectError as exc:
            raise OllamaError(
                f"无法连接 Ollama（{self.settings.ollama_url}）。请先启动 Ollama。"
            ) from exc
        except httpx.ReadTimeout as exc:
            minutes = self.settings.request_timeout / 60
            raise OllamaError(
                f"Ollama 连续 {minutes:g} 分钟没有返回新数据，任务已超时。"
                "请检查显存占用，或通过 OLLAMA_TIMEOUT 继续提高等待时间。"
            ) from exc
        except OllamaError:
            raise
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
            raise OllamaError(f"Ollama 返回无效结果：{exc}") from exc
