import { useEffect, useMemo, useState } from "react";
import { getSettings, updateSettings, type SettingsInfo } from "../api/settingsApi";

function normalizePrompts(settings: SettingsInfo | null) {
  const prompts = settings?.ai_prompts;
  const taskTypes = prompts?.task_types?.length ? prompts.task_types : ["预算平台问答"];
  const taskPrompts = Object.fromEntries(taskTypes.map((taskType) => [taskType, prompts?.task_prompts?.[taskType] || ""]));
  return {
    generalPrompt: prompts?.general_prompt || "",
    taskPrompts,
    defaultGeneralPrompt: prompts?.default_general_prompt || "",
    defaultTaskPrompts: prompts?.default_task_prompts || {},
    taskTypes,
  };
}

export default function AI提示词设置() {
  const [settings, setSettings] = useState<SettingsInfo | null>(null);
  const [selectedType, setSelectedType] = useState("预算平台问答");
  const [generalPrompt, setGeneralPrompt] = useState("");
  const [taskPrompts, setTaskPrompts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    getSettings().then((value) => {
      const normalized = normalizePrompts(value);
      setSettings(value);
      setGeneralPrompt(normalized.generalPrompt);
      setTaskPrompts(normalized.taskPrompts);
      setSelectedType(normalized.taskTypes[0] || "预算平台问答");
    }).catch((error) => setMessage(error.message));
  }, []);

  const promptState = useMemo(() => normalizePrompts(settings), [settings]);
  const currentDefaultPrompt = promptState.defaultTaskPrompts[selectedType] || "";
  const currentPrompt = taskPrompts[selectedType] || "";
  const preview = `系统不可编辑安全规则\nAI 只能问答，不执行上传、删除、入库、导出或清理数据。\n\n通用提示词\n${generalPrompt}\n\n${selectedType}提示词\n${currentPrompt}`;

  async function savePrompts() {
    const payloadTaskPrompts = Object.fromEntries(promptState.taskTypes.map((taskType) => {
      const value = (taskPrompts[taskType] || "").trim();
      const defaultValue = (promptState.defaultTaskPrompts[taskType] || "").trim();
      return [taskType, value === defaultValue ? "" : value];
    }));
    const saved = await updateSettings({
      ai_prompts: {
        general_prompt: generalPrompt.trim() === promptState.defaultGeneralPrompt.trim() ? "" : generalPrompt,
        task_prompts: payloadTaskPrompts,
      },
    });
    const normalized = normalizePrompts(saved);
    setSettings(saved);
    setGeneralPrompt(normalized.generalPrompt);
    setTaskPrompts(normalized.taskPrompts);
    setMessage("AI 提示词已保存到本地配置。");
  }

  function restoreCurrentType() {
    setTaskPrompts((prev) => ({ ...prev, [selectedType]: currentDefaultPrompt }));
    setMessage(`${selectedType}已恢复为默认提示词，点击保存后生效。`);
  }

  function restoreGeneral() {
    setGeneralPrompt(promptState.defaultGeneralPrompt);
    setMessage("通用提示词已恢复为默认内容，点击保存后生效。");
  }

  return (
    <div className="page-stack workbench-page">
      <section className="page-hero settings-hero">
        <div>
          <h2>AI 提示词</h2>
          <p>默认使用系统内置提示词；你可以按自己的经营分析习惯调整回答风格和分析重点。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{promptState.taskTypes.length}</strong>分析类型</span>
          <span><strong>本地保存</strong>不提交 Git</span>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>通用提示词</h2>
            <p className="muted">会应用到所有 AI 分析和问答，适合定义回答口吻、结构和偏好。</p>
          </div>
          <div className="button-row compact-settings-actions">
            <button className="secondary" onClick={restoreGeneral}>恢复默认</button>
          </div>
        </div>
        <textarea
          className="prompt-editor"
          value={generalPrompt}
          onChange={(event) => setGeneralPrompt(event.target.value)}
          placeholder="例如：先说结论，再说依据，最后给行动建议。"
        />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>分析类型提示词</h2>
            <p className="muted">不同分析类型可以有不同要求，例如费用异常更关注超支原因，月度复盘更关注行动建议。</p>
          </div>
          <div className="button-row compact-settings-actions">
            <button className="secondary" onClick={restoreCurrentType}>恢复当前类型默认</button>
            <button onClick={savePrompts}>保存提示词</button>
          </div>
        </div>
        <div className="form-grid dense-form">
          <label>
            分析类型
            <select value={selectedType} onChange={(event) => setSelectedType(event.target.value)}>
              {promptState.taskTypes.map((taskType) => <option value={taskType} key={taskType}>{taskType}</option>)}
            </select>
          </label>
        </div>
        <textarea
          className="prompt-editor large"
          value={currentPrompt}
          onChange={(event) => setTaskPrompts((prev) => ({ ...prev, [selectedType]: event.target.value }))}
        />
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>当前拼接预览</h2>
            <p className="muted">真实调用时还会追加当前预算平台的结构化数据和你的问题。安全规则不可编辑。</p>
          </div>
        </div>
        <pre className="command-preview prompt-preview">{preview}</pre>
        {message && <div className="notice success">{message}</div>}
      </section>
    </div>
  );
}
