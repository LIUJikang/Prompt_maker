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

        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "format": schema.model_json_schema(),
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                message,
            ],
        }
        try:
            response = httpx.post(
                f"{self.settings.ollama_url}/api/chat",
                json=payload,
                timeout=self.settings.request_timeout,
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            return schema.model_validate(json.loads(content))
        except httpx.ConnectError as exc:
            raise OllamaError(
                f"无法连接 Ollama（{self.settings.ollama_url}）。请先启动 Ollama。"
            ) from exc
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValueError) as exc:
            detail = getattr(response, "text", "") if "response" in locals() else ""
            raise OllamaError(f"Ollama 返回无效结果：{exc}\n{detail[:500]}") from exc
