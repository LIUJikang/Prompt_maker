# LTX-2.5 电影提示词导演

一个本地运行的 Python Agent：读取首帧图片和基础描述，通过 Ollama 多模态模型分析画面、动态追问，并生成面向 LTX-2.5 图生视频的电影级英文提示词。

## 功能

- 客观分析主体、环境、构图、光线和可运动空间
- 最多提出 3 个真正影响镜头设计的问题
- 支持单一连续镜头和多镜头分镜
- 输出正向提示词、负向提示词、中文导演说明、分镜提示词和完整 JSON
- 自动将时长换算成满足 `8n + 1` 的 LTX 合法帧数
- 保守、电影感、强运镜三档运动强度
- 三步向导式界面，只显示当前需要填写或查看的内容
- 视频导演与 Z-Image Turbo 仙侠首帧工坊使用独立标签页
- 12 个仙侠人物快捷候选，覆盖少年、青年、中年、高贵、贫寒和大众脸男女角色
- 角色候选包含固定五官、发型、服装与配饰身份锚点，并支持锁定 Seed 减少人物漂移
- 支持用中文追加修改要求、保留上一版英文提示词并反复重新生成首帧
- Ollama 推理期间显示全屏进度遮罩并锁定界面，避免重复提交或误操作
- 将原始首帧、正负提示词、FPS 和合法帧数注入 ComfyUI API 工作流
- 一键排队运行 LTX-2.5 工作流，并在结果页回显生成的视频
- 按主体类型生成详细一致性约束：人物面部与服装、动物外形与斑纹、物体结构与材质

## 准备 Ollama

默认模型为 `qwen3.8:27b`，可以通过环境变量更换为其他支持图片的 Ollama 模型。

```powershell
ollama pull qwen3.8:27b
ollama serve
```

如果 Ollama 已经作为后台服务运行，不需要再次执行 `ollama serve`。

## 安装与启动

在项目使用的虚拟环境中安装依赖：

```powershell
pip install -r requirements.txt
python app.py
```

浏览器打开终端中显示的本地地址。也可以设置环境变量：

```powershell
$env:OLLAMA_MODEL = "qwen3.8:27b"
$env:OLLAMA_URL = "http://127.0.0.1:11434"
$env:OLLAMA_TIMEOUT = "900"
$env:OLLAMA_NUM_PREDICT = "16384"
python app.py
```

Ollama 响应采用流式接收，默认关闭结构化任务的长思考模式，并给予 15 分钟无数据超时。
结构化输出默认最多生成 16384 tokens；遇到截断或无效 JSON 时会以较低温度自动重试一次。
如需启用模型思考，可设置 `$env:OLLAMA_THINK = "true"`。应用默认会在 Ollama 与 ComfyUI
阶段之间请求释放对方驻留模型，以降低显存争用；如不希望自动释放，可设置
`$env:RELEASE_MODELS_BETWEEN_STAGES = "false"`。

## 连接 ComfyUI

先启动 ComfyUI。本机 Comfy Desktop 的地址为 `http://127.0.0.1:8000`。项目根目录中的
`video_ltx2_5_i2v.json` 必须是通过 ComfyUI “Export (API Format)” 导出的版本。

可通过环境变量修改连接与等待时间：

```powershell
$env:COMFYUI_URL = "http://127.0.0.1:8000"
$env:COMFYUI_WORKFLOW = "video_ltx2_5_i2v.json"
$env:COMFYUI_IMAGE_WORKFLOW = "image_z_image_turbo.json"
$env:COMFYUI_TIMEOUT = "1800"
python app.py
```

生成提示词后，点击“发送到 ComfyUI 并生成视频”。应用会上传原始首帧，把完整的最终正向提示词
注入正向节点，并将负向提示词注入独立的负向条件节点。
结果页中手动修改后的正向或负向提示词也会以修改后的内容为准。应用随后会
按导演结果设置 FPS 和 `8n + 1` 帧数，并在 ComfyUI 完成后下载视频到
`outputs/comfyui/`。

## 工作流程

1. “仙侠首帧工坊”页输入场景创意，并按需要点击一个或多个角色候选按钮。
2. 保持“锁定 Seed”开启后生成图片。首次使用随机 Seed，成功后会自动回填；继续填写修改要求并
   再次生成时会复用同一 Seed 和角色锚点。纯文生图不能保证绝对同脸，但可显著降低人物变化。
3. 满意后点击“使用此图作为视频首帧”，应用会自动切换到“视频导演”并同步图片与画幅。
4. 也可以直接在“视频导演”上传已有首帧，填写目标动作，然后分析图片。
5. 分析完成后回答导演追问或使用默认值，再生成完整 LTX-2.5 提示词和视频。

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 设计说明

Agent 没有依赖复杂框架，而是使用可检查的三阶段状态机：

1. `ImageAnalysis`：多模态图片分析。
2. `ClarificationPlan`：判断缺失信息并生成问题。
3. `DirectorResult`：生成时间线、提示词和参数。

所有模型阶段均使用 JSON Schema 约束，并由 Pydantic 校验。这比让模型一次输出整段自由文本更容易保持字段完整和结果稳定。
