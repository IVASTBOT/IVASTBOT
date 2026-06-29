import type { MemberCandidate, MemberRecord } from "../types/brain";

interface MemberCardProps {
  member?: MemberRecord | null;
  candidates?: MemberCandidate[];
}

export function MemberCard({ member, candidates = [] }: MemberCardProps) {
  if (!member && candidates.length) {
    return (
      <div className="info-block">
        <h3>Candidates</h3>
        <div className="candidate-list">
          {candidates.map((candidate) => (
            <div className="candidate-row" key={candidate.member_id ?? candidate.display_name}>
              <strong>{candidate.display_name}</strong>
              <span>{candidate.unit}</span>
              <span>{candidate.roles?.join(", ")}</span>
              <small>{Math.round((candidate.confidence ?? 0) * 100)}%</small>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!member) {
    return <div className="muted">Không có thông tin thành viên phù hợp.</div>;
  }

  return (
    <div className="member-card">
      <div>
        <h3>{member.display_name || member.full_name}</h3>
        <p>{member.unit}</p>
      </div>
      <dl>
        <dt>Vai trò</dt>
        <dd>{member.roles?.join(", ") || "Không có dữ liệu"}</dd>
        <dt>Email</dt>
        <dd>{member.email || "Không có dữ liệu"}</dd>
        <dt>Vision consent</dt>
        <dd>{member.consent_for_vision ? "Đã consent" : "Chưa consent"}</dd>
      </dl>
      {member.source && (
        <a href={member.source} target="_blank" rel="noreferrer">
          Nguồn hồ sơ
        </a>
      )}
    </div>
  );
}

