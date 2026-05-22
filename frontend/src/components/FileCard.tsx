interface Props {
  name: string;
  content: string;
}

export default function FileCard({ name, content }: Props) {
  const handleDownload = () => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="file-card">
      <div className="file-card-icon">📄</div>
      <div className="file-card-info">
        <span className="file-card-name">{name}</span>
        <span className="file-card-size">
          {content.length > 1024
            ? `${(content.length / 1024).toFixed(1)} KB`
            : `${content.length} 字`}
        </span>
      </div>
      <button className="file-card-download" onClick={handleDownload}>
        ⬇ 下载
      </button>
    </div>
  );
}
