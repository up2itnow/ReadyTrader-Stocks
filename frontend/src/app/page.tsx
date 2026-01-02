"use client";

import { useMarketData } from '@/hooks/useMarketData';
import { usePendingApprovals } from '@/hooks/usePendingApprovals';
import { AreaChart, Area, Tooltip, ResponsiveContainer } from 'recharts';
import { ShieldCheck, Zap } from 'lucide-react';
import { useEffect } from 'react';

// Dummy data for the chart
const dummyChartData = [
  { time: '00:00', value: 45000 },
  { time: '04:00', value: 45200 },
  { time: '08:00', value: 44800 },
  { time: '12:00', value: 46100 },
  { time: '16:00', value: 45900 },
  { time: '20:00', value: 47200 },
  { time: '23:59', value: 48500 },
];

export default function Dashboard() {
  const { tickers, connected } = useMarketData();
  const { approvals } = usePendingApprovals();

  useEffect(() => {
    // Fetch initial portfolio
    const fetchPortfolio = async () => {
      const res = await fetch('http://localhost:8000/api/portfolio');
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    };
    fetchPortfolio();
  }, []);

  return (
    <div className="dashboard-grid">
      {/* Portfolio Overview */}
      <section className="col-span-2 card">
        <div className="card-header">
          <div>
            <h3>Portfolio Performance</h3>
            <p className="muted">Total value across all accounts</p>
          </div>
          <div className="value-pnl">
            <h2>$48,500.00</h2>
            <span className="success">+7.4% Today</span>
          </div>
        </div>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={dummyChartData}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00f2ff" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00f2ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip
                contentStyle={{ background: '#16161a', border: '1px solid #2d2d35', borderRadius: '8px' }}
                itemStyle={{ color: '#00f2ff' }}
              />
              <Area type="monotone" dataKey="value" stroke="#00f2ff" fillOpacity={1} fill="url(#colorValue)" strokeWidth={3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Real-time Ticker */}
      <section className="card">
        <div className="card-header">
          <h3>Live Markets</h3>
          <span className={`connection-dot ${connected ? 'online' : 'offline'}`}></span>
        </div>
        <div className="ticker-list">
          {Object.values(tickers).length === 0 ? (
            <p className="muted">Waiting for stream...</p>
          ) : (
            Object.values(tickers).map((t) => (
              <div key={t.symbol} className="ticker-item">
                <span className="symbol">{t.symbol}</span>
                <span className="price">${t.last.toLocaleString()}</span>
                <span className="source muted">{t.source}</span>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Guard Rail / Pending Approvals */}
      <section className="card">
        <div className="card-header">
          <div className="icon-title">
            <ShieldCheck className="primary" size={20} />
            <h3>Guard Rail</h3>
          </div>
          {approvals.length > 0 && <span className="warning-badge">{approvals.length}</span>}
        </div>
        <div className="approval-list">
          {approvals.length === 0 ? (
            <div className="empty-approval">
              <Zap className="muted" size={32} />
              <p className="muted">No pending approvals</p>
            </div>
          ) : (
            approvals.map((a) => (
              <div key={a.request_id} className="approval-item">
                <div className="approval-info">
                  <span className="kind">{a.kind.replace('_', ' ')}</span>
                  <span className="muted">ID: {a.request_id.slice(0, 8)}...</span>
                </div>
                <button className="btn btn-primary compact">Review</button>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Strategy Performance */}
      <section className="card">
        <h3>Active Strategies</h3>
        <div className="strategy-list">
          <div className="strategy-item">
            <span>Trend Follower / AAPL</span>
            <span className="success">+2.1%</span>
          </div>
          <div className="strategy-item">
            <span>Mean Reversion / TSLA</span>
            <span className="danger">-1.4%</span>
          </div>
        </div>
      </section>
    </div>
  );
}
