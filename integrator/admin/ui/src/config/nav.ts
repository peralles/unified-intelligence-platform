import {
  LayoutDashboard,
  Mail,
  MessageCircle,
  Zap,
  Link2,
  Settings,
  Wrench,
  ScrollText,
  type LucideIcon,
} from "lucide-react";
import type { ViewId } from "@/types";

export interface NavItem {
  id: ViewId;
  label: string;
  icon: LucideIcon;
}

export const NAV: NavItem[] = [
  { id: "painel", label: "Painel", icon: LayoutDashboard },
  { id: "google", label: "Google", icon: Mail },
  { id: "whatsapp", label: "WhatsApp", icon: MessageCircle },
  { id: "servico", label: "Serviço", icon: Zap },
  { id: "mcp", label: "MCP / Hermes", icon: Link2 },
  { id: "config", label: "Configuração", icon: Settings },
  { id: "ferramentas", label: "Ferramentas", icon: Wrench },
  { id: "logs", label: "Logs", icon: ScrollText },
];
