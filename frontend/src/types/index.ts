/** Shared TypeScript types matching the FastAPI backend schemas. */

// ── Auth ────────────────────────────────────────────────────────────────────

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
}

// ── LoRA Models ──────────────────────────────────────────────────────────────

export interface LoraModelInfo {
  key: string;
  filename: string;
  size_bytes: number;
  last_modified: string;
  download_url: string;
}

export interface LoraModelListResponse {
  user_id: string;
  models: LoraModelInfo[];
}

export interface LoraUploadResponse {
  key: string;
  filename: string;
  message: string;
}

// ── Snapshots ────────────────────────────────────────────────────────────────

export interface SnapshotCreate {
  name: string;
  parameters: Record<string, unknown>;
}

export interface SnapshotUpdate {
  name?: string;
  parameters?: Record<string, unknown>;
}

export interface SnapshotResponse {
  id: string;
  user_id: string;
  name: string;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
