import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <p className="eyebrow">VERSEVIVA · 声声不息</p>
      <h1>听懂每一句，唱活每一首</h1>
      <p>
        看懂原唱怎样处理声音与 Vocal 层次，分开练主唱、和声和重叠句，再把它们叠成完整演唱。
      </p>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

