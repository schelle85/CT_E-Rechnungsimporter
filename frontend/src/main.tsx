import ReactDOM from "react-dom/client";
import { MantineProvider, createTheme } from "@mantine/core";
import "@mantine/core/styles.css";
import "./styles.css";
import AuthApp from "./AuthApp";
const theme = createTheme({
  primaryColor: "blue",
  fontFamily: "Inter, Segoe UI, system-ui, sans-serif",
  defaultRadius: "md",
  headings: { fontFamily: "Inter, Segoe UI, system-ui, sans-serif" },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <MantineProvider theme={theme}>
    <AuthApp />
  </MantineProvider>,
);
