export type BrainRoute = "time" | "fixed" | "member" | "vision" | "rag" | "unknown";

export interface BrainSource {
  title?: string;
  section?: string;
  url?: string;
  content_type?: string;
  [key: string]: unknown;
}

export interface MemberRecord {
  member_id?: string;
  full_name?: string;
  display_name?: string;
  aliases?: string[];
  academic_title?: string;
  degree?: string;
  unit?: string;
  roles?: string[];
  email?: string;
  source?: string;
  consent_for_vision?: boolean;
}

export interface MemberCandidate {
  member_id?: string;
  display_name?: string;
  unit?: string;
  roles?: string[];
  confidence?: number;
  confidence_type?: string;
}

export interface BrainResponse {
  answer: string;
  route: BrainRoute;
  confidence: number;
  confidence_type?: string;
  sources: Array<BrainSource | string>;
  metadata: Record<string, unknown>;
  warnings: string[];
}

export interface HealthResponse {
  status?: string;
  embedding_model?: string;
  model_primary?: string;
  model_fallback?: string;
  active_model?: string;
  primary_available?: boolean;
  fallback_available?: boolean;
  warnings?: string[];
  vector_db?: {
    path?: string;
    exists?: boolean;
    collection?: string;
    sqlite_exists?: boolean;
  };
  [key: string]: unknown;
}

export interface MemberLookupResponse {
  status: "found" | "unknown" | "ambiguous" | string;
  confidence: number;
  confidence_type?: string;
  member?: MemberRecord | null;
  candidates?: MemberCandidate[];
  answer?: string;
}

export interface VisionResponse {
  status: "recognized" | "unknown" | "low_confidence" | "no_consent" | "not_enrolled" | string;
  confidence?: number;
  reason?: string;
  member?: MemberRecord | null;
  warning?: string;
}

export interface ChatMessageModel {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: BrainResponse;
  error?: string;
}
