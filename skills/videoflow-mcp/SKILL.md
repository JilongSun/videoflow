---
name: videoflow-mcp
description: 用于通过 VideoFlow MCP 完成视频编辑与产品替换工作流，并在流程中断时进行恢复；当用户提到抖音搜索视频、MCP 名称 videoflow/VideoFlow、视频编辑或产品替换时触发。
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
- 所有中断、异常、完成结果都按结构化返回处理

## 标准执行流程
1. **参数检查与补全**
   先检查请求参数是否完整（至少包含图片输入、视频关键词等）。参数缺失时，主动向用户追问，直到参数齐全。
2. **启动工作流**
   参数齐全后调用 `tool_run_video_workflow`。
3. **处理中断**
   如果返回 `status = pending_selection`，说明流程需要人工决策。将 `candidates` 呈现给用户并收集选择。
4. **恢复工作流**
   收到用户选择后，调用 `tool_resume_video_workflow` 继续执行。
5. **返回结果**
   收到完成结果后，向用户反馈最终产物或错误信息。

## thread_id / session_id 管理
- 将 thread_id（即 session_id）视为核心参数。
- 启动新任务后，立即在当前会话的短期记忆中保存 thread_id。
- 后续 resume、状态查询等调用自动携带同一个 thread_id。
- 不同任务之间必须隔离 thread_id，禁止复用或串用。
- 任务完成或会话关闭后，及时清理该 thread_id。

## 处理中断与状态查询
- `pending_selection` 只代表流程暂停，不代表失败。
- 只要 thread_id 未失效，就可以基于该 thread_id 继续 resume 或查询状态。
- 如果出现 thread_id 不存在或已过期，提示用户重新发起任务。

## 参数最小清单（启动前）
- `image_input`：用户提供的图片输入（HTTP URL 或已存在文件名）
- `video_keyword`：视频检索关键词
- `video_input`：可选；如果提供则可跳过候选选择环节

启动前检查规则：
- 缺 `image_input`：先向用户追问图片输入
- 缺 `video_keyword`：先向用户追问关键词
- 两者齐全后才允许调用 `tool_run_video_workflow`

## MCP 调用模板

### 启动调用
```json
{
   "tool": "tool_run_video_workflow",
   "args": {
      "image_input": "<image_input>",
      "video_keyword": "<video_keyword>",
      "video_input": "<optional_video_input_or_file>",
      "session_id": "<optional_session_id>"
   }
}
```

### 启动返回处理
- 若 `status = pending_selection`：
   - 保存 `session_id`
   - 将 `candidates` 展示给用户
   - 等待用户选择后进入 resume
- 若 `status = completed`：
   - 直接返回结果并结束会话
- 若 `status = error`：
   - 返回错误信息并按重试策略处理

### 恢复调用
```json
{
   "tool": "tool_resume_video_workflow",
   "args": {
      "session_id": "<saved_session_id>",
      "video_input": "<http_url_or_local_filename>"
   }
}
```

> `video_input` 可以是候选列表中的 HTTP URL，也可以是已下载到本地的文件名，两者均可接受。

## 用户沟通模板（建议）

### 参数追问模板
- 缺图片时：
   - 请提供用于替换的视频目标图片（URL 或文件）。
- 缺关键词时：
   - 请提供要搜索的视频关键词。

### 中断提示模板
- 已找到多个候选视频，请从以下候选中选择一个继续处理：
   - 候选 1: ...
   - 候选 2: ...
   - 候选 3: ...

### 完成反馈模板
- 视频编辑已完成，输出结果为：`<result_file_or_url>`

## 异常与重试策略
- `status = error` 且可重试错误（网络抖动、下载失败等）：
   - 最多重试 2 次
   - 每次重试前给出简短提示
- `session_id` 不存在或已过期：
   - 不做 resume 重试
   - 直接提示用户重新发起新任务
- 参数缺失或格式错误：
   - 不调用 MCP
   - 先在对话层补齐参数
