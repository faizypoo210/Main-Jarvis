import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ControlPlaneLiveProvider } from "./contexts/ControlPlaneLiveContext";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ControlPlaneLiveProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ControlPlaneLiveProvider>
  </StrictMode>
);
