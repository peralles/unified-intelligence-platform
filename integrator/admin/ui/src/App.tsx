import { Sidebar, ToastHost, TopBar } from "@/components/layout/Shell";
import { useApp } from "@/context/AppContext";
import { FerramentasView } from "@/views/FerramentasView";
import { GoogleView } from "@/views/GoogleView";
import { GuiaView } from "@/views/GuiaView";
import { LogsView } from "@/views/LogsView";
import { PainelView } from "@/views/PainelView";
import { WhatsAppView } from "@/views/WhatsAppView";
import type { ViewId } from "@/types";

const VIEWS: Record<ViewId, React.ComponentType> = {
  painel: PainelView,
  google: GoogleView,
  whatsapp: WhatsAppView,
  ferramentas: FerramentasView,
  logs: LogsView,
  guia: GuiaView,
};

function ActiveView() {
  const { activeView } = useApp();
  const View = VIEWS[activeView];
  return <View />;
}

export function App() {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">
          <ActiveView />
        </main>
      </div>
      <ToastHost />
    </div>
  );
}
