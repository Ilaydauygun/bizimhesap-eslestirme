import { Component } from "react";

/** Arayüzde beklenmeyen bir hata olursa beyaz ekran yerine hatayı gösterir. */
export default class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error("Arayüz hatası:", error, info?.componentStack); }
  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div style={{ maxWidth: 800, margin: "60px auto", padding: 24, background: "#fff", boxShadow: "0 2px 8px rgba(0,0,0,.2)" }}>
        <h4 style={{ color: "#d6524e" }}>Bir hata oluştu</h4>
        <p>Sayfa beklenmedik bir hatayla karşılaştı. Aşağıdaki mesajı geliştiriciye iletebilirsiniz.</p>
        <pre style={{ background: "#f5f5f5", padding: 12, whiteSpace: "pre-wrap" }}>{String(error?.stack || error?.message || error)}</pre>
        <button className="btn btn-dark" onClick={() => (window.location.href = "/")}>Ana sayfaya dön</button>
      </div>
    );
  }
}
