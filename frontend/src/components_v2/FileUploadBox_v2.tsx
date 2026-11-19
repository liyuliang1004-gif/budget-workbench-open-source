export default function FileUploadBox_v2({
  selectedFile,
  onSelect,
  onUpload,
  loading,
  title,
  description,
  actionLabel,
  accept = ".xlsx,.xls,.csv",
}: {
  selectedFile: File | null;
  onSelect: (file: File | null) => void;
  onUpload: () => void;
  loading?: boolean;
  title: string;
  description?: string;
  actionLabel: string;
  accept?: string;
}) {
  function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    onSelect(file);
  }

  return (
    <div className="v2-form-grid">
      <label
        className="v2-upload-drop"
        style={{ cursor: "pointer" }}
        onClick={() => document.getElementById(`v2-up-${title}`)?.click()}
      >
        <div className="v2-upload-drop-icon">📁</div>
        <div className="v2-upload-drop-title">
          {selectedFile ? (
            <span style={{ color: "var(--v2-primary)" }}>
              {selectedFile.name}
            </span>
          ) : (
            <>点击或拖拽文件到此处上传</>
          )}
        </div>
        <div className="v2-upload-drop-desc">
          {description || `支持 ${accept} 格式`}
        </div>
        <input
          id={`v2-up-${title}`}
          type="file"
          accept={accept}
          style={{ display: "none" }}
          onChange={onFileInput}
        />
      </label>

      <div className="v2-button-row" style={{ justifyContent: "flex-end" }}>
        <button
          type="button"
          className="secondary"
          onClick={() => onSelect(null)}
          disabled={!selectedFile || loading}
        >
          清除
        </button>
        <button
          type="button"
          className="primary"
          onClick={onUpload}
          disabled={!selectedFile || loading}
        >
          {loading ? "上传中…" : actionLabel}
        </button>
      </div>
    </div>
  );
}
