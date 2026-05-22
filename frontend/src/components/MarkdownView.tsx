import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import FileCard from "./FileCard";
import MindMapView from "./MindMapView";

const FILE_RE = /<!--FILE:(.+?)-->\n?([\s\S]*?)<!--ENDFILE-->/g;
const MINDMAP_RE = /<!--MINDMAP-->([\s\S]*?)<!--ENDMINDMAP-->/g;

type Segment =
  | { type: "markdown"; content: string }
  | { type: "file"; name: string; content: string }
  | { type: "mindmap"; content: string };

function splitContent(raw: string): Segment[] {
  // Combine both markers into one pass using a unified regex
  const combined = new RegExp(
    `(${FILE_RE.source}|${MINDMAP_RE.source})`,
    "g"
  );
  const segments: Segment[] = [];
  let last = 0;
  let m;

  while ((m = combined.exec(raw)) !== null) {
    if (m.index > last) {
      segments.push({ type: "markdown", content: raw.slice(last, m.index) });
    }
    const full = m[0];
    // Check which marker matched
    if (full.startsWith("<!--FILE:")) {
      const nameMatch = full.match(/<!--FILE:(.+?)-->/);
      const inner = full.replace(/<!--FILE:.+?-->\n?/, "").replace(/<!--ENDFILE-->$/, "");
      segments.push({ type: "file", name: nameMatch?.[1] || "", content: inner.trim() });
    } else if (full.startsWith("<!--MINDMAP-->")) {
      const inner = full.replace(/<!--MINDMAP-->/, "").replace(/<!--ENDMINDMAP-->/, "");
      segments.push({ type: "mindmap", content: inner.trim() });
    }
    last = combined.lastIndex;
  }

  if (last < raw.length) {
    segments.push({ type: "markdown", content: raw.slice(last) });
  }

  return segments.length > 0 ? segments : [{ type: "markdown", content: raw }];
}

export default function MarkdownView({ content }: { content: string }) {
  const segments = splitContent(content);

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === "file") {
          return (
            <FileCard key={i} name={seg.name} content={seg.content} />
          );
        }
        if (seg.type === "mindmap") {
          return <MindMapView key={i} code={seg.content} />;
        }
        return (
          <ReactMarkdown
            key={i}
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const codeStr = String(children).replace(/\n$/, "");
                if (match) {
                  return (
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                    >
                      {codeStr}
                    </SyntaxHighlighter>
                  );
                }
                return (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {seg.content}
          </ReactMarkdown>
        );
      })}
    </>
  );
}
