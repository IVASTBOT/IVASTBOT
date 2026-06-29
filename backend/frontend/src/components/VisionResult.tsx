import type { VisionResponse } from "../types/brain";
import { MemberCard } from "./MemberCard";

interface VisionResultProps {
  result?: VisionResponse | null;
}

function statusLabel(result: VisionResponse): string {
  if (result.status === "recognized") return "recognized";
  if (result.reason === "no_enrolled_members") return "not_enrolled";
  if (result.reason === "member_not_consented" || result.status === "consent_required") return "no_consent";
  if ((result.confidence ?? 0) > 0 && result.status === "unknown") return "low_confidence";
  return result.status || "unknown";
}

export function VisionResult({ result }: VisionResultProps) {
  if (!result) return <div className="muted">Chưa có kết quả nhận diện.</div>;

  const label = statusLabel(result);
  const safeToShowMember = result.status === "recognized" && (result.confidence ?? 0) >= 0.92;

  return (
    <div className="vision-result">
      <div className={`status-large status-${label}`}>{label}</div>
      <dl>
        <dt>Confidence</dt>
        <dd>{Math.round((result.confidence ?? 0) * 100)}%</dd>
        <dt>Reason</dt>
        <dd>{result.reason || result.warning || "Không có"}</dd>
      </dl>
      {safeToShowMember ? <MemberCard member={result.member} /> : null}
    </div>
  );
}

