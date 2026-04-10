---
name: videoflow-mcp
description: 用于通过 VideoFlow MCP 完成视频编辑与产品替换工作流；支持先搜索并下载抖音视频，再基于本地视频启动工作流；当用户提到抖音搜索视频、MCP 名称 videoflow/VideoFlow、视频编辑或产品替换时触发。
---

# VideoFlow Agent-MCP 协作技能

## 触发条件
仅当用户请求命中以下任一条件时，才触发本技能：
- 提到从抖音搜索、抓取、爬取相关视频（如“从抖音找素材”“抖音搜视频”）
- 提到 MCP 名称 `videoflow` 或 `VideoFlow`
- 明确要使用 MCP 的视频编辑能力（如“视频编辑”“替换视频内容”）
- 提到产品替换相关诉求（如“产品替换”“商品替换”“把视频里的物体换掉”）

## 执行原则
- 只把 VideoFlow 当作 MCP 能力提供方，不让 MCP 直接与用户交互
- 所有用户沟通、参数补全、选择确认都由我负责
- 视频编辑工作流只接受本地视频文件，不接受在线链接
- 搜索、选择、下载素材与最终启动工作流是两段式协作
- 所有异常、完成结果都按结构化返回处理
- MCP 内部已包含错误重试与恢复机制，Agent 不做工作流重启、人工补偿重试等运维操作
- Agent 仅负责：参数补全、状态查询、预览确认与结果回传

## 标准执行流程
1. **参数检查与补全**
   先检查请求参数是否完整（至少包含图片输入、视频关键词，以及可用的本地视频输入方案）。参数缺失时，主动向用户追问，直到参数齐全。
2. **启动后获取会话 ID**
   调用 `tool_run_video_workflow` 后，返回值会包含 `status=started` 和 `session_id`。
   Agent **必须立即告知用户** session_id，方便用户后续查询进度。
3. **判断视频来源路径**
   如果用户要从抖音找素材，先走"搜索/选择/下载"路径；如果用户已经提供本地视频，直接走"启动工作流"路径。
4. **路径 A：搜索并下载抖音视频**
   先调用 `tool_search_video` 获取候选列表，展示给用户选择；用户确认后，再调用 `tool_download_video` 把选中的分享链接下载到本地。
5. **路径 B：直接使用本地视频**
   如果用户已经提供本地视频文件名或本地路径，跳过搜索和下载。
6. **启动视频编辑工作流**
   拿到本地 `video_input` 后，调用 `tool_run_video_workflow`。
   若返回 `status=started`，Agent 立刻把返回的 `session_id` 告知用户。
7. **首片预览确认（视频 > 5 秒时）**
   当视频超过 5 秒时，后台工作流会先处理第一个分片并进入 `waiting_approval`。
   Agent 调用 `tool_get_workflow_progress` 获取 `interrupt_payload` 中的预览信息，展示给用户确认。
   用户确认满意后调用 `tool_resume_video_workflow` 继续处理剩余分片。
8. **返回结果**
   收到完成结果后，向用户反馈最终产物或错误信息。
9. **用户查询进度**
   当用户通过 session_id 询问进度时，调用 `tool_get_workflow_progress` 返回当前阶段和完成百分比。

## session_id 管理
- Agent 在调用 `tool_run_video_workflow` 后，会收到 `session_id`。
- 获取后**必须立即告知用户** session_id，方便用户后续询问进度。
- 如需复用历史会话，可将已有 `session_id` 传入 `tool_run_video_workflow` 的 `session_id` 参数。
- 用户随时可以通过 session_id 询问进度，Agent 调用 `tool_get_workflow_progress` 查询。

## 工作流边界
- `tool_run_video_workflow` 不负责抖音搜索、候选选择或视频下载。
- 抖音素材获取必须先通过 `tool_search_video` 和 `tool_download_video` 完成。
- 传给工作流的 `video_input` 必须是本地视频文件名或本地路径。
- 如果拿到的是 HTTP 视频链接，先下载，再启动工作流。

## 参数最小清单（启动前）
- `prompt`：视频编辑提示词，描述对视频的修改意图（见下方提示词构造规则）
- `image_input`：参考图片输入（HTTP URL 或已存在文件名）；不使用参考图片时传空字符串
- `video_keyword`：视频关键词，用于抖音检索或视频分析
- `video_input`：本地视频文件名或本地路径

启动前检查规则：
- 缺 `prompt`：根据用户意图按照下方规则推导，无法推导时追问
- 缺 `image_input` 且用户意图涉及参考图片替换：先向用户追问图片输入
- 缺 `video_keyword`：先向用户追问关键词
- 缺本地 `video_input` 且用户要搜索素材：先调用搜索与下载工具补齐本地视频
- 四者满足条件后才允许调用 `tool_run_video_workflow`

## 提示词（prompt）构造规则
提示词分两种模式，Agent 应根据用户是否提供参考图片来选择：

### 模式一：不使用参考图片（直接描述替换效果）
由 Agent 根据用户描述的修改意图，用英文自然语言描述对视频的改动，其余保持不变。

示例：
> "Turn the wheels of the taxi to blocks of ice. Keep everything else the same."

### 模式二：使用参考图片（将图片中的物体替换到视频中）
当用户提供了参考图片时，提示词固定为以下结构：
> "Replace the `<视频中的目标物体>` in the video with the `<图片中的物体>` in the picture"

示例：
> "Replace the cat in the video with the cat in the picture"

## MCP 调用模板

### 查询进度
```json
{
   "tool": "tool_get_workflow_progress",
   "args": {
      "session_id": "<session_id>"
   }
}
```
返回值：
- `phase`：当前阶段（preparing/splitting/preview/waiting_approval/batch_processing/concatenating/completed/failed/cancelled）
- `percent`：总体完成百分比（0-100）
- `total_slices`：总分片数
- `completed`：已完成分片数
- `processing`：正在处理的分片数
- `failed`：失败的分片数
- `slices`：每个分片的详细状态

### 独立搜索调用
```json
{
   "tool": "tool_search_video",
   "args": {
      "keyword": "<video_keyword>",
      "publish_time": 7
   }
}
```

返回值：视频候选链接列表（最多 10 条），供用户选择后再下载到本地。

### 独立下载调用
```json
{
   "tool": "tool_download_video",
   "args": {
      "video_url": "<selected_video_url>",
      "file_name": "<optional_local_filename>",
      "download_path": "<optional_local_directory>"
   }
}
```

返回值：
- `success`：是否下载成功
- `video_id`：下载后生成的本地视频标识

### 启动调用
```json
{
   "tool": "tool_run_video_workflow",
   "args": {
      "prompt": "<编辑提示词（见提示词构造规则）>",
      "image_input": "<参考图片URL或文件名，不使用参考图片时传空字符串>",
      "video_keyword": "<video_keyword>",
         "video_input": "<local_video_file>",
         "session_id": "<optional_session_id，用于复用历史会话>"
   }
}
```

### 启动返回处理
- 返回 `status=started` 后，Agent 必须立即告知用户 `session_id`。
- 视频 ≤ 5 秒：后台会直接完成，Agent 可通过 `tool_get_workflow_progress` 轮询完成状态与结果。
- 视频 > 5 秒：后台会进入 `waiting_approval`，并在进度中返回 `interrupt_payload`（首片预览信息）。
   Agent 应展示预览给用户确认，然后调用 `tool_resume_video_workflow`。

### 恢复调用（视频 > 5 秒时必须）
```json
{
   "tool": "tool_resume_video_workflow",
   "args": {
      "session_id": "<第一阶段返回的session_id>",
      "approved": true
   }
}
```
- `approved: true`：继续处理剩余分片并拼接
- `approved: false`：中止工作流

## 两种启动方式示例

### 方式 1：先搜索抖音视频，再启动工作流
1. 调用 `tool_search_video`
2. 将候选列表展示给用户
3. 用户选定候选后，调用 `tool_download_video`
4. 下载成功后，拿到本地 `video_input`
5. 调用 `tool_run_video_workflow`
6. 返回 `started` 后，立即把 `session_id` 告知用户
7. 若进度为 `waiting_approval`，展示首片预览给用户
8. 用户确认后调用 `tool_resume_video_workflow`
9. 用户随时可查询进度：调用 `tool_get_workflow_progress`

### 方式 2：用户直接提供本地视频，再启动工作流
1. 确认用户提供的是本地视频文件名或本地路径
2. 收集 `image_input` 和 `video_keyword`
3. 调用 `tool_run_video_workflow`
4. 返回 `started` 后，立即把 `session_id` 告知用户
5. 若进度为 `waiting_approval`，展示首片预览给用户
6. 用户确认后调用 `tool_resume_video_workflow`
7. 用户随时可查询进度：调用 `tool_get_workflow_progress`

## 用户沟通模板（建议）

### 参数追问模板
- 缺图片时：
   - 请提供用于替换的视频目标图片（URL 或文件）。
- 缺关键词时：
   - 请提供要搜索的视频关键词。
- 缺本地视频且用户需要搜索素材时：
   - 请提供要搜索的视频关键词，我会先帮你找候选视频，确认后再下载到本地。

### 候选选择模板
- 已找到多个候选视频，请从以下候选中选择一个继续处理：
   - 候选 1: ...
   - 候选 2: ...
   - 候选 3: ...

### 完成反馈模板
- 视频编辑已完成，输出结果为：`<result_file_or_url>`

## 异常与重试策略
- `status = error`：
   - 不在 Agent 侧执行自动重试、重启工作流或手动补偿逻辑
   - 直接向用户反馈 MCP 返回的错误信息，并引导用户按需调整输入参数后重新发起业务请求
- 搜索结果为空或下载失败：
   - 先提示用户更换关键词，或重新选择候选后重试
- 参数缺失或格式错误：
   - 不调用 MCP
   - 先在对话层补齐参数
