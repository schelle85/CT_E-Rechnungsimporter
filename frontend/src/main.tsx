import React from "react";
import ReactDOM from "react-dom/client";
import { MantineProvider, createTheme } from "@mantine/core";
import "@mantine/core/styles.css";
import "./styles.css";
import App from "./App";
const theme = createTheme({
  primaryColor: "blue",
  fontFamily: "Inter, Segoe UI, system-ui, sans-serif",
  defaultRadius: "md",
  headings: { fontFamily: "Inter, Segoe UI, system-ui, sans-serif" },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider theme={theme}>
      <App />
    </MantineProvider>
  </React.StrictMode>,
);
