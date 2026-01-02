"use client";

import { useEffect, useState, useCallback, useRef } from 'react';

export type TickerUpdate = {
    symbol: string;
    last: number;
    bid: number | null;
    ask: number | null;
    timestamp_ms: number | null;
    source: string;
};

export function useMarketData() {
    const [tickers, setTickers] = useState<Record<string, TickerUpdate>>({});
    const [connected, setConnected] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const connectRef = useRef<() => void>(() => { });

    const connect = useCallback(() => {
        const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setConnected(true);
            console.log('WS Connected');
        };

        ws.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.type === 'TICKER_UPDATE') {
                    const update = payload.data as TickerUpdate;
                    setTickers(prev => ({
                        ...prev,
                        [update.symbol]: update
                    }));
                }
            } catch (err) {
                console.error('WS Message Error:', err);
            }
        };

        ws.onclose = () => {
            setConnected(false);
            console.log('WS Closed, reconnecting in 3s...');
            setTimeout(() => {
                connectRef.current();
            }, 3000);
        };

        ws.onerror = (err) => {
            console.error('WS Error:', err);
            ws.close();
        };

        socketRef.current = ws;
    }, []);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    useEffect(() => {
        connect();
        return () => {
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [connect]);

    return { tickers, connected };
}
