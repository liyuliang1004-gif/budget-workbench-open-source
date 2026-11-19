interface Props {
  selectedFile?: File | null;
  onSelect: (file: File | null) => void;
  onUpload: () => void;
  loading?: boolean;
  title?: string;
  description?: string;
  actionLabel?: string;
  loadingLabel?: string;
  accept?: string;
}

export default function FileUploadBox({
  selectedFile,
  onSelect,
  onUpload,
  loading,
  title = "选择预算表 .xlsx",
  description = "文件会上传到本地预算表上传区",
  actionLabel = "上传文件",
  loadingLabel = "上传中...",
  accept = ".xlsx"
}: Props) {
  return (
    <div className="upload-box">
      <label>
        <strong>{selectedFile ? selectedFile.name : title}</strong>
        <span>{description}</span>
        <input
          type="file"
          accept={accept}
          disabled={loading}
          onChange={(event) => {
            onSelect(event.target.files?.[0] || null);
            event.currentTarget.value = "";
          }}
        />
      </label>
      <button disabled={loading || !selectedFile} onClick={onUpload}>{loading ? loadingLabel : actionLabel}</button>
    </div>
  );
}
