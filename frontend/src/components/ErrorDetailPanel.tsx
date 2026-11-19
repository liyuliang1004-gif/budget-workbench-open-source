import type { CheckResult } from "../types/check";
import { translateCheckType, translateSeverity } from "../utils/formatters";

export default function ErrorDetailPanel({ result }: { result?: CheckResult }) {
  if (!result) return <div className="side-panel muted">选择一条错误查看详情</div>;
  return (
    <div className="side-panel">
      <h3>{result.error_message || "检查结果"}</h3>
      <dl>
        <dt>级别</dt><dd>{translateSeverity(result.severity)}</dd>
        <dt>检查类型</dt><dd>{translateCheckType(result.check_type)}</dd>
        <dt>系统码</dt><dd>{result.error_code || "-"}</dd>
        <dt>工作表</dt><dd>{result.sheet_name || "-"}</dd>
        <dt>单元格</dt><dd>{result.cell_address || "-"}</dd>
        <dt>行号</dt><dd>{result.row_number || "-"}</dd>
        <dt>字段</dt><dd>{result.column_name || "-"}</dd>
        <dt>产品</dt><dd>{result.product_name || result.product_code || "-"}</dd>
        <dt>月份</dt><dd>{result.month || "-"}</dd>
        <dt>上传值</dt><dd>{result.uploaded_value || "-"}</dd>
        <dt>系统值</dt><dd>{result.expected_value || "-"}</dd>
        <dt>差异</dt><dd>{result.diff_value || "-"}</dd>
        <dt>建议</dt><dd>{result.suggestion || "-"}</dd>
      </dl>
    </div>
  );
}
