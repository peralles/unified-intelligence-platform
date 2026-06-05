export type ViewId =
  | "painel"
  | "google"
  | "whatsapp"
  | "servico"
  | "mcp"
  | "config"
  | "ferramentas"
  | "logs";

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
    error?: string;
  };
  effective?: {
    whatsapp?: Record<string, unknown>;
    tools?: Record<string, unknown>;
    logging?: Record<string, unknown>;
  };
  ignore_numbers_text?: string;
  mac_service?: Record<string, unknown> & { available?: boolean; running?: boolean };
  deployment?: { docker?: boolean };
  persistence?: PersistenceState;
}

export interface CheckItem {
  label: string;
  status: string;
  detail?: string;
  hint?: string;
}

export interface ToolMeta {
  name: string;
  description?: string;
}
