import { useEffect, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { deleteAITask, exportAIReport, getAITasks, renameAITask, runAIAnalysis, type AITask } from "../api/ai";
import { translateModel } from "../utils/formatters";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  time: string;
}

function nowLabel() {
  return new Date().toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function taskTitle(task: AITask) {
  return task.question || task.task_type || "预算平台问答";
}

export default function AI经营分析() {
  const [taskType, setTaskType] = useState("预算平台问答");
  const [scopeType, setScopeType] = useState("platform");
  const [scopeValue, setScopeValue] = useState("整个预算平台");
  const [question, setQuestion] = useState("请说明当前预算平台可能存在的问题和我下一步应该检查什么");
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<AITask[]>([]);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: "我可以回答预算平台、上传检查、入库、汇总、导出和设置相关问题。AI 只做问答，不执行操作。", time: nowLabel() }
  ]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = () => getAITasks().then(setTasks).catch((error) => setMessage(error.message));
  useEffect(() => { refresh(); }, []);

  async function analyze(customQuestion = question) {
    const trimmed = customQuestion.trim();
    if (!trimmed) return;
    const askedAt = nowLabel();
    setLoading(true);
    setMessage("");
    setQuestion(trimmed);
    setMessages((prev) => [...prev, { role: "user", content: trimmed, time: askedAt }]);
    try {
      const response = await runAIAnalysis({ task_type: taskType, scope_type: scopeType, scope_value: scopeValue, question: trimmed });
      setCurrentTaskId(response.task_id);
      setMessages((prev) => [...prev, { role: "assistant", content: response.result, time: nowLabel() }]);
      await refresh();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "AI 分析失败";
      setMessage(errorMessage);
      setMessages((prev) => [...prev, { role: "assistant", content: errorMessage, time: nowLabel() }]);
    } finally {
      setLoading(false);
    }
  }

  async function exportReport(taskId: number) {
    const response = await exportAIReport(taskId);
    setMessage(`已导出：${response.report_path}`);
  }

  async function deleteTask(taskId: number) {
    if (!window.confirm("确认删除这条 AI 对话记录？")) return;
    await deleteAITask(taskId);
    if (currentTaskId === taskId) {
      clearDialog();
    }
    await refresh();
  }

  async function renameTask(task: AITask) {
    const nextTitle = window.prompt("请输入新的对话记录名称", taskTitle(task));
    if (!nextTitle || !nextTitle.trim()) return;
    const updated = await renameAITask(task.id, nextTitle.trim());
    if (currentTaskId === task.id) {
      setQuestion(updated.question || "");
    }
    await refresh();
  }

  function startResize(event: ReactMouseEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = sidebarWidth;
    const onMove = (moveEvent: MouseEvent) => {
      const nextWidth = Math.min(Math.max(startWidth + moveEvent.clientX - startX, 220), 460);
      setSidebarWidth(nextWidth);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function openTask(task: AITask) {
    setCurrentTaskId(task.id);
    setTaskType(task.task_type || "预算平台问答");
    setScopeType(task.scope_type || "platform");
    setScopeValue(task.scope_value || "整个预算平台");
    setQuestion(task.question || "");
    setMessages([
      { role: "user", content: task.question || taskTitle(task), time: task.created_at?.slice(5, 16).replace("T", " ") || nowLabel() },
      { role: "assistant", content: task.ai_result || "该记录暂无回复内容。", time: task.finished_at?.slice(5, 16).replace("T", " ") || nowLabel() }
    ]);
  }

  function clearDialog() {
    setCurrentTaskId(null);
    setQuestion("");
    setMessages([{ role: "assistant", content: "已清空当前对话。历史记录仍保留在左侧，可随时打开查看。", time: nowLabel() }]);
  }

  function copyLastReply() {
    const lastReply = [...messages].reverse().find((item) => item.role === "assistant");
    if (!lastReply) return;
    navigator.clipboard.writeText(lastReply.content).then(() => setMessage("已复制最后回复")).catch(() => setMessage("复制失败"));
  }

  return (
    <div className="ai-chat-shell" style={{ gridTemplateColumns: `${sidebarWidth}px 10px minmax(0, 1fr)` }}>
      <aside className="ai-chat-sidebar">
        <div className="ai-chat-sidebar-title">
          <h3>对话记录</h3>
          <button onClick={clearDialog}>新建</button>
        </div>
        <div className="ai-session-list">
          {tasks.length ? tasks.slice(0, 8).map((task) => (
            <button key={task.id} className={task.id === currentTaskId ? "active" : ""} onClick={() => openTask(task)}>
              <span className="ai-session-copy">
                <strong>{taskTitle(task)}</strong>
                <span>{task.created_at?.slice(5, 16).replace("T", " ") || "刚刚"}</span>
                <small>{translateModel(String(task.model_name || ""))}</small>
              </span>
              <span
                className="ai-session-delete"
                role="button"
                tabIndex={0}
                aria-label="重命名对话记录"
                onClick={(event) => {
                  event.stopPropagation();
                  renameTask(task).catch((error) => setMessage(error instanceof Error ? error.message : "改名失败"));
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.stopPropagation();
                    renameTask(task).catch((error) => setMessage(error instanceof Error ? error.message : "改名失败"));
                  }
                }}
              >改</span>
              <span
                className="ai-session-delete"
                role="button"
                tabIndex={0}
                aria-label="删除对话记录"
                onClick={(event) => {
                  event.stopPropagation();
                  deleteTask(task.id).catch((error) => setMessage(error instanceof Error ? error.message : "删除失败"));
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.stopPropagation();
                    deleteTask(task.id).catch((error) => setMessage(error instanceof Error ? error.message : "删除失败"));
                  }
                }}
              >×</span>
            </button>
          )) : <p className="muted">暂无历史对话</p>}
        </div>
      </aside>

      <div className="ai-chat-resizer" onMouseDown={startResize} role="separator" aria-label="调整对话记录宽度" />

      <section className="ai-chat-main">
        <div className="ai-message-board">
          {messages.map((item, index) => (
            <article key={index} className={`ai-bubble ${item.role === "user" ? "user" : "assistant"}`}>
              <strong>{item.role === "user" ? "我" : "AI分析"} · {item.time}</strong>
              <pre>{item.content}</pre>
            </article>
          ))}
        </div>

        <div className="ai-input-panel">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                analyze();
              }
            }}
            placeholder="给“预算系统”发送消息"
          />
          <div className="ai-action-row">
            <button className="icon-action" title="复制最后回复" aria-label="复制最后回复" onClick={copyLastReply}>⧉</button>
            <button className="icon-action" title="清空对话" aria-label="清空对话" onClick={clearDialog}>⌫</button>
            <button className="icon-action" title="导出 MD" aria-label="导出 MD" disabled={!currentTaskId} onClick={() => currentTaskId && exportReport(currentTaskId)}>⇩</button>
            <button className="send-action" title="发送" aria-label="发送" disabled={loading} onClick={() => analyze()}>{loading ? "…" : "↑"}</button>
          </div>
          {message && <p className="muted">{message}</p>}
        </div>
      </section>
    </div>
  );
}
