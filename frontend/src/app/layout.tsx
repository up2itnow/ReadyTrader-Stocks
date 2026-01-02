import type { Metadata } from "next";
import Link from "next/link";
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
              <Link href="/" className="nav-item active">Dashboard</Link>
              <Link href="/strategy" className="nav-item">Strategy</Link>
              <Link href="/history" className="nav-item">History</Link>
              <Link href="/settings" className="nav-item">Settings</Link>
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
