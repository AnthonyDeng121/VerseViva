import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main>
      <p className="eyebrow">VOCALCOMPASS</p>
      <h1>让每一遍练唱都有方向</h1>
      <p>项目框架已就绪。下一步接入歌曲上传、分析进度和 Song Profile。</p>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

