import {
  LayoutDashboard,
  Mail,
  MessageCircle,
  Wrench,
  ScrollText,
  BookOpen,
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
  { id: "ferramentas", label: "Ferramentas", icon: Wrench },
  { id: "logs", label: "Logs", icon: ScrollText },
  { id: "guia", label: "Guia", icon: BookOpen },
];
