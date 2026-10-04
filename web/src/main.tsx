import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <p className="eyebrow">VERSEVIVA · 声声不息</p>
      <h1>听懂每一句，唱活每一首</h1>
      <p>
        不只告诉你歌词怎么读，而是听懂原唱如何把语言放进旋律，并陪你逐句练会。
      </p>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

