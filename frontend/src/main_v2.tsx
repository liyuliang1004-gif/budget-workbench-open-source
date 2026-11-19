import React from "react";
import ReactDOM from "react-dom/client";
import App_v2 from "./App_v2";
import "./styles/global.css";
import "./styles/theme.css";
import "./styles/layout.css";
import "./styles_v2/主题变量_v2.css";
import "./styles_v2/全局样式_v2.css";
import "./styles_v2/布局样式_v2.css";
import "./styles_v2/老类名覆盖_v2.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App_v2 />
  </React.StrictMode>,
);
