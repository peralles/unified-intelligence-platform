export type ViewId =
  | "painel"
  | "google"
  | "whatsapp"
  | "linkedin"
  | "ferramentas"
  | "logs"
  | "guia";

export type Tone = "ok" | "warn" | "err" | "info" | "";

export interface PersistenceState {
  status: "ok" | "warn" | "error";
  data_path: string;
  writable: boolean;
  mounted: boolean;
  docker_mode: boolean;
  volume_id: string | null;
  message: string;
  hint: string | null;
}

export interface GoogleAccount {
  id: string;
  email?: string;
  has_token?: boolean;
  is_default?: boolean;
}

export interface TranscriptionStatus {
  auto_transcribe?: boolean;
  model?: string;
  language?: string;
  transcriber_ready?: boolean;
  ignore_count?: number;
}

export interface AppState {
  service?: {
    url_admin?: string;
    url_sse?: string;
    url_health?: string;
    host?: string;
    port?: number;
  };
  setup?: {
    configured?: boolean;
    credentials_ready?: boolean;
    deps_ok?: boolean;
    critical_failures?: number;
    next_step?: string;
  };
  accounts?: { accounts?: GoogleAccount[] };
  whatsapp_live?: {
    live?: { logged_in?: boolean; state?: string; push_name?: string };
    status?: { logged_in?: boolean; state?: string; push_name?: string };
    transcription?: TranscriptionStatus;
    error?: string;
  };
  effective?: {
    whatsapp?: Record<string, unknown>;
    tools?: Record<string, unknown>;
    logging?: Record<string, unknown>;
  };
  ignore_numbers_text?: string;
  deployment?: {
    container?: boolean;
    oauth_public_base_url?: string | null;
    oauth_redirect?: string;
  };
  linkedin?: {
    enabled?: boolean;
    client_id_set?: boolean;
    client_secret_set?: boolean;
    accounts?: LinkedInAccount[];
    default_account?: string | null;
  };
  persistence?: PersistenceState;
}

export interface LinkedInAccount {
  id: string;
  name?: string;
  email?: string;
  picture?: string;
  sub?: string;
  has_token?: boolean;
  token_valid?: boolean;
  refresh_valid?: boolean | null;
  expires_at?: number | null;
}

export interface ToolMeta {
  name: string;
  description?: string;
}
