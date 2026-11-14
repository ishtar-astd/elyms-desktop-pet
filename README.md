# 曳尔沐桌宠 · 通讯终端

《异环》非官方同人桌宠。曳尔沐在桌面上轻轻浮动，单击触发来电，双击打开聊天。右键菜单也可以打开聊天、调整大小或退出。

## 启动

先解压。推荐使用 [Python 3.12 或 3.13](https://www.python.org/downloads/)。首次运行会联网安装 PyQt5，依赖放在项目目录下的 `.venv`。

| 系统 | 启动方式 |
| --- | --- |
| Windows 10/11（x64） | 双击 `Start-Windows.cmd`。 |
| macOS（Apple 芯片或 Intel） | 双击 `Start-Mac.command`。也可以在终端输入 `bash `，把脚本拖进去，再按回车。 |

## 模型聊天

双击桌宠，打开「模型设置」。聊天模型 ID 留空时可使用离线演示。接入 AI 时填写服务商的 Base URL、你有权限使用的模型 ID 和 API Key。

| 服务 | 聊天 Base URL | 模型 ID |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | 填写账户可用的文本聊天模型。 |
| DeepSeek | `https://api.deepseek.com` | 填写 DeepSeek 控制台显示的模型 ID。 |
| Ollama | `http://localhost:11434/v1` | 填写已下载的模型名。聊天 Key 可留空。 |

Base URL 填到服务根路径，程序会加上 `/chat/completions`。远程连接使用 HTTPS，本机服务可使用 HTTP。

## 记忆

- **接着聊**。桌宠按服务地址和模型在本机保存最近八轮成功的 AI 对话。重启后会恢复，并将这些对话带入下一次请求。点「清空对话」可删除当前模型的对话记录。
- **记住偏好**。直接发送 `记住：以后叫我小星`，或点顶部「记忆」填写常用称呼、偏好等信息。长期记忆最多 2000 字，跨模型使用。打开「记忆」即可查看、修改或删掉内容，也可以清空后保存。
- **存储位置**。Windows 默认保存在 `%LOCALAPPDATA%\ElymsDesktopPet\memory.sqlite3`，macOS 默认保存在 `~/Library/Application Support/ElymsDesktopPet/memory.sqlite3`。启用 AI 聊天时，相关对话和已保存的长期记忆随请求发给所选聊天服务。离线演示中也可以编辑长期记忆。

## 语音

- **录音转文字**。在「模型设置」填写转写 Base URL、模型 ID 和 API Key。OpenAI 可用 `https://api.openai.com/v1` 与 `gpt-4o-mini-transcribe`。也可使用提供 `/audio/transcriptions` 的兼容服务。转写服务可与聊天服务分开配置。
- **开始录音**。点「录音」，说完再点「停止录音」。每段最长 30 秒。识别结果会放进输入框，确认后按回车发送。系统弹出麦克风权限请求时，请允许从终端或 Python 录音。
- **朗读回复**。点「朗读回复」，也可以勾选「自动朗读」。语音使用操作系统自带的合成引擎。安装中文系统语音后，桌宠会优先选用中文语音。

API Key 仅在当前运行中保留，也可通过 `ELYMS_API_KEY` 和 `ELYMS_STT_API_KEY` 环境变量传入。聊天记录和录音不写入项目目录。配置了远程服务后，聊天文本或主动录制的音频会发送给对应服务。
