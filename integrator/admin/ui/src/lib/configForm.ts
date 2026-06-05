import type { AppState } from "@/types";

export interface WhatsAppConfigForm {
  auto_transcribe: boolean;
  transcribe_private_only: boolean;
  transcribe_only_incoming: boolean;
  transcribe_model: string;
  transcribe_language: string;
  transcribe_prefix: string;
  max_message_chars: string;
  max_cached_per_chat: string;
  ignore_numbers_text: string;
  persist_env: boolean;
}

export interface ToolsConfigForm {
  allowlist: string;
  denylist: string;
  confirm_required_tools: string;
  persist_env: boolean;
}

export interface LoggingConfigForm {
  log_level: string;
  audit_log_enabled: boolean;
  audit_log_success: boolean;
  log_tool_success: boolean;
  persist_env: boolean;
}

export function whatsappFormFromState(state: AppState): WhatsAppConfigForm {
  const w = state.effective?.whatsapp || {};
  return {
    auto_transcribe: !!w.auto_transcribe,
    transcribe_private_only: !!w.transcribe_private_only,
    transcribe_only_incoming: !!w.transcribe_only_incoming,
    transcribe_model: String(w.transcribe_model || ""),
    transcribe_language: String(w.transcribe_language || ""),
    transcribe_prefix: String(w.transcribe_prefix || ""),
    max_message_chars: String(w.max_message_chars || 800),
    max_cached_per_chat: String(w.max_cached_messages_per_chat || 5000),
    ignore_numbers_text: state.ignore_numbers_text || "",
    persist_env: true,
  };
}

export function toolsFormFromState(state: AppState): ToolsConfigForm {
  const t = state.effective?.tools || {};
  return {
    allowlist: String(t.allowlist || ""),
    denylist: String(t.denylist || ""),
    confirm_required_tools: String(t.confirm_required_tools || ""),
    persist_env: true,
  };
}

export function loggingFormFromState(state: AppState): LoggingConfigForm {
  const l = state.effective?.logging || {};
  return {
    log_level: String(l.level || "INFO").toUpperCase(),
    audit_log_enabled: !!l.audit_log_enabled,
    audit_log_success: !!l.audit_log_success,
    log_tool_success: !!l.log_tool_success,
    persist_env: true,
  };
}

export function whatsappConfigPayload(form: WhatsAppConfigForm): Record<string, unknown> {
  return {
    persist_env: form.persist_env,
    ignore_numbers_text: form.ignore_numbers_text,
    whatsapp: {
      auto_transcribe: form.auto_transcribe,
      transcribe_private_only: form.transcribe_private_only,
      transcribe_only_incoming: form.transcribe_only_incoming,
      transcribe_model: form.transcribe_model.trim(),
      transcribe_language: form.transcribe_language.trim() || null,
      transcribe_prefix: form.transcribe_prefix,
      max_message_chars: parseInt(form.max_message_chars, 10) || 800,
      max_cached_messages_per_chat: parseInt(form.max_cached_per_chat, 10) || 5000,
    },
  };
}

export function toolsConfigPayload(form: ToolsConfigForm): Record<string, unknown> {
  return {
    persist_env: form.persist_env,
    tools: {
      allowlist: form.allowlist.trim() || null,
      denylist: form.denylist.trim() || null,
      confirm_required_tools: form.confirm_required_tools.trim() || null,
    },
  };
}

export function loggingConfigPayload(form: LoggingConfigForm): Record<string, unknown> {
  return {
    persist_env: form.persist_env,
    logging: {
      level: form.log_level,
      audit_log_enabled: form.audit_log_enabled,
      audit_log_success: form.audit_log_success,
      log_tool_success: form.log_tool_success,
    },
  };
}
