import { useEffect, useState } from "react";
import { getHealth } from "./api/client";
import { Header } from "./components/Header";
import { Sidebar, type AppPage } from "./components/Sidebar";
import { ChatPage } from "./pages/ChatPage";
import { DevPage } from "./pages/DevPage";
import { MembersPage } from "./pages/MembersPage";
import { VisionPage } from "./pages/VisionPage";
import type { BrainResponse, HealthResponse } from "./types/brain";

export default function App() {
  const [activePage, setActivePage] = useState<AppPage>("chat");
  const [debugMode, setDebugMode] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [, setLastResponse] = useState<BrainResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      setHealthLoading(true);
      try {
        const payload = await getHealth();
        if (!cancelled) setHealth(payload);
      } catch {
        if (!cancelled) setHealth(null);
      } finally {
        if (!cancelled) setHealthLoading(false);
      }
    }

    void loadHealth();
    const timer = window.setInterval(loadHealth, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="app-shell">
      <Header health={health} loading={healthLoading} />
      <div className="app-body">
        <Sidebar
          activePage={activePage}
          onNavigate={setActivePage}
          debugMode={debugMode}
          onToggleDebug={() => setDebugMode((value) => !value)}
        />
        <div className="content">
          {activePage === "chat" && <ChatPage debugMode={debugMode} onLastResponse={setLastResponse} />}
          {activePage === "members" && <MembersPage debugMode={debugMode} />}
          {activePage === "vision" && <VisionPage debugMode={debugMode} />}
          {activePage === "dev" && <DevPage />}
        </div>
      </div>
    </div>
  );
}

