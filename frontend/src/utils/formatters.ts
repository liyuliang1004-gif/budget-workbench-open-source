export function formatAmountWan(value?: number | string | null) {
  const numberValue = Number(value || 0) / 10000;
  return `${numberValue.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 万元`;
}

export function formatPriceYuan(value?: number | string | null) {
  const numberValue = Number(value || 0);
  return `${numberValue.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 元`;
}

export function formatPercent(value?: number | string | null) {
  if (value === null || value === undefined || value === "") return "-";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

export function translateSeverity(value?: string | null) {
  if (value === "error") return "错误";
  if (value === "warning") return "警告";
  if (value === "info") return "提示";
  return value || "未知";
}

export function translateCheckType(value?: string | null) {
  if (value === "format") return "格式检查";
  if (value === "formula") return "公式检查";
  if (value === "calculation") return "计算校验";
  return value || "未知";
}

export function translateModel(value?: string | null) {
  if (value === "mock") return "mock（模拟模式）";
  if (value === "deepseek-chat") return "DeepSeek Chat（深度求索对话模型）";
  return value || "未知模型";
}
