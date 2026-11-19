# AI配置说明

## 配置项

- `DEEPSEEK_API_KEY`：DeepSeek API Key，不得提交到 Git。
- `DEEPSEEK_API_BASE`：DeepSeek API 地址，默认 `https://api.deepseek.com`。
- `DEEPSEEK_MODEL`：模型名称，默认 `deepseek-chat`。
- `AI_ANALYSIS_MODE`：`mock` 或 `deepseek`。未配置 API Key 时自动进入 mock。

## 权限边界

AI 只读取结构化汇总数据和错误摘要，不读取原始 Excel，不修改数据库正式业务数据，不覆盖报表和看板。

## 输出结构

AI 输出必须包含：分析结论摘要、关键数据依据、主要异常点、可能原因分析、建议动作、需要人工确认的问题、不确定性说明。
