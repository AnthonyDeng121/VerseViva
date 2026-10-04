import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <p className="eyebrow">VERSEVIVA · 声声不息</p>
      <h1>听懂每一句，唱活每一首</h1>
      <p>
        看见原唱省掉、合并或改变了哪些声音，再把同一句真正唱出来。
      </p>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

