import { Stack, Tabs } from "@mantine/core";
import AdminPanel from "./AdminPanel";
import ProcessingControls from "./ProcessingControls";
import ReportsPanel from "./ReportsPanel";

export default function Administration({ readOnly, csrfToken, onActivated, onSaved }: { readOnly: boolean; csrfToken: string; onActivated: () => Promise<void>; onSaved: () => void }) {
  return <Tabs defaultValue="reports" keepMounted={false}>
    <Tabs.List mb="lg"><Tabs.Tab value="reports">Berichte</Tabs.Tab><Tabs.Tab value="settings">Verbindungen & Verarbeitung</Tabs.Tab></Tabs.List>
    <Tabs.Panel value="reports"><ReportsPanel /></Tabs.Panel>
    <Tabs.Panel value="settings"><Stack><ProcessingControls csrfToken={csrfToken} onSaved={onSaved} /><AdminPanel readOnly={readOnly} csrfToken={csrfToken} onActivated={onActivated} /></Stack></Tabs.Panel>
  </Tabs>;
}
