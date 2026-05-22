import { useEffect, useRef, useState } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import { toPng } from "html-to-image";

const transformer = new Transformer();

interface Props {
  code: string;
}

const isMermaid = (code: string) =>
  /^(mindmap|graph\s|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|gitGraph)\b/m.test(code.trim());

export default function MindMapView({ code }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mmRef = useRef<Markmap | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mermaid rendering path
  useEffect(() => {
    if (!isMermaid(code)) return;

    let cancelled = false;
    const renderMermaid = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "default" });
        const { svg } = await mermaid.render("mermaid-svg", code.trim());
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setReady(true);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Mermaid render error");
      }
    };
    renderMermaid();
    return () => { cancelled = true; };
  }, [code]);

  // Markmap rendering path
  useEffect(() => {
    if (isMermaid(code) || !containerRef.current) return;

    try {
      const { root } = transformer.transform(code);

      let svg = containerRef.current.querySelector("svg") as SVGSVGElement | null;
      if (!svg) {
        svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.style.width = "100%";
        svg.style.height = "100%";
        containerRef.current.innerHTML = "";
        containerRef.current.appendChild(svg);
        mmRef.current = Markmap.create(svg, {
          autoFit: true,
          duration: 0,
          maxWidth: 300,
          paddingX: 16,
        });
      }

      mmRef.current!.setData(root);
      mmRef.current!.fit();
      setReady(true);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Markmap render error");
    }
  }, [code]);

  const handleDownloadPng = async () => {
    const svgEl = containerRef.current?.querySelector("svg");
    if (!svgEl) return;

    try {
      const dataUrl = await toPng(svgEl as HTMLElement, {
        backgroundColor: "#ffffff",
        pixelRatio: 2,
      });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = "思维导图.png";
      a.click();
    } catch {
      // fallback silently
    }
  };

  if (error) {
    return (
      <div className="mindmap-error">
        <p className="mindmap-error-msg">思维导图渲染失败</p>
        <pre>{code}</pre>
      </div>
    );
  }

  return (
    <div className="mindmap-container">
      <div ref={containerRef} className="mindmap-svg" />
      {ready && (
        <button className="mindmap-download-btn" onClick={handleDownloadPng}>
          ⬇ 下载思维导图（PNG）
        </button>
      )}
    </div>
  );
}
