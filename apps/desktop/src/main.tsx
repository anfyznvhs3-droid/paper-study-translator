import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app/App";
import "./styles/global.css";
import "./styles/dashboard.css";
import "./styles/glossary.css";
import "./styles/buttons.css";
import "./styles/controls.css";
import "./styles/entry.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
