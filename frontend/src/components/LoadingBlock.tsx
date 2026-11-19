export default function LoadingBlock({ text = "加载中" }: { text?: string }) {
  return <div className="loading-block">{text}...</div>;
}
