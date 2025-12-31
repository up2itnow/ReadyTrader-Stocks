import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReadyTrader | Institutional AI Stock Trading",
  description: "High-performance AI agent stock trading dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="layout-root">
          <aside className="sidebar">
            <div className="logo-container">
              <span className="logo-text">REAL<span>TRADER</span></span>
            </div>
            <nav className="main-nav">
              <a href="/" className="nav-item active">Dashboard</a>
              <a href="/strategy" className="nav-item">Strategy</a>
              <a href="/history" className="nav-item">History</a>
              <a href="/settings" className="nav-item">Settings</a>
            </nav>
          </aside>
          <main className="content">
            <header className="top-bar">
              <div className="status-indicators">
                <span className="status-pill paper">Paper Mode</span>
              </div>
              <div className="user-profile">
                <span>Agent Zero</span>
              </div>
            </header>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
