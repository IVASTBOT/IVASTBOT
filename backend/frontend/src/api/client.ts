import type { BrainResponse, BrainRoute, HealthResponse, MemberLookupResponse, VisionResponse } from "../types/brain";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

export function chat(message: string, imagePath?: string): Promise<BrainResponse> {
  return requestJson<Partial<BrainResponse>>("/chat", {
    method: "POST",
    body: JSON.stringify({ query: message, mode: "auto", image_path: imagePath || null })
  }).then(normalizeBrainResponse);
}

export function ragQuery(query: string): Promise<BrainResponse> {
  return requestJson<Record<string, unknown>>("/rag/query", {
    method: "POST",
    body: JSON.stringify({ query })
  }).then((payload) =>
    normalizeBrainResponse({
      answer: typeof payload.answer === "string" ? payload.answer : "",
      route: "rag",
      confidence: extractRagConfidence(payload),
      confidence_type: "rag_distance",
      sources: extractRagSources(payload),
      metadata: payload,
      warnings: []
    })
  );
}

export function lookupMember(query: string): Promise<MemberLookupResponse> {
  return requestJson<MemberLookupResponse>("/members/lookup", {
    method: "POST",
    body: JSON.stringify({ query })
  });
}

export function recognizeVision(input: { imagePath?: string; file?: File | null }): Promise<VisionResponse> {
  const imagePath = input.imagePath || input.file?.name || "";
  return requestJson<VisionResponse>("/vision/recognize", {
    method: "POST",
    body: JSON.stringify({ image_path: imagePath })
  });
}

export function enrollVision(memberId: string, input: { imagePath?: string; file?: File | null }): Promise<VisionResponse> {
  const imagePath = input.imagePath || input.file?.name || "";
  return requestJson<VisionResponse>("/vision/enroll", {
    method: "POST",
    body: JSON.stringify({ member_id: memberId, image_path: imagePath })
  });
}

function normalizeBrainResponse(payload: Partial<BrainResponse>): BrainResponse {
  const route = isBrainRoute(payload.route) ? payload.route : "unknown";
  return {
    answer: typeof payload.answer === "string" ? payload.answer : "",
    route,
    confidence: typeof payload.confidence === "number" ? payload.confidence : 0,
    confidence_type: typeof payload.confidence_type === "string" ? payload.confidence_type : "",
    sources: Array.isArray(payload.sources) ? payload.sources : [],
    metadata: isRecord(payload.metadata) ? payload.metadata : {},
    warnings: Array.isArray(payload.warnings) ? payload.warnings.filter((item): item is string => typeof item === "string") : []
  };
}

function isBrainRoute(route: unknown): route is BrainRoute {
  return ["time", "fixed", "member", "vision", "rag", "unknown"].includes(String(route));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function extractRagConfidence(payload: Record<string, unknown>): number {
  const chunks = payload.chunks;
  if (Array.isArray(chunks) && chunks.length > 0 && isRecord(chunks[0]) && typeof chunks[0].confidence === "number") {
    return chunks[0].confidence;
  }
  return 0;
}

function extractRagSources(payload: Record<string, unknown>) {
  const chunks = payload.chunks;
  if (!Array.isArray(chunks)) return [];
  const urls = new Set<string>();
  for (const chunk of chunks) {
    if (!isRecord(chunk)) continue;
    const metadata = chunk.metadata;
    if (isRecord(metadata) && typeof metadata.url === "string") urls.add(metadata.url);
  }
  return Array.from(urls);
}
