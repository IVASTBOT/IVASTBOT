interface DebugPanelProps {
  data: unknown;
  title?: string;
}

export function DebugPanel({ data, title = "Raw JSON" }: DebugPanelProps) {
  return (
    <section className="debug-panel">
      <h3>{title}</h3>
      <pre>{JSON.stringify(data ?? {}, null, 2)}</pre>
    </section>
  );
}

