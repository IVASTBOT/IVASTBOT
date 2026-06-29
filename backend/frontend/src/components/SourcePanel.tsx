import type { BrainSource } from "../types/brain";

interface SourcePanelProps {
  sources?: Array<BrainSource | string>;
}

export function SourcePanel({ sources = [] }: SourcePanelProps) {
  if (!sources.length) {
    return <div className="muted">Không có nguồn được trả về.</div>;
  }

  return (
    <ul className="source-list">
      {sources.map((source, index) => {
        const url = typeof source === "string" ? source : source.url;
        const label =
          typeof source === "string"
            ? source
            : [source.title, source.section, source.content_type].filter(Boolean).join(" · ") || source.url || `Source ${index + 1}`;
        return (
        <li key={url ?? label}>
          {url ? (
            <a href={url} target="_blank" rel="noreferrer">
              {label}
            </a>
          ) : (
            <span>{label}</span>
          )}
        </li>
        );
      })}
    </ul>
  );
}
