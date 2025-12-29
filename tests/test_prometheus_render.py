from observability.metrics import Metrics
from observability.prometheus import render_prometheus


def test_render_prometheus_contains_expected_lines():
    m = Metrics()
    m.inc("a_total", 2)
    m.set_gauge("ws_last_message_age_sec", 1.25)
    m.observe_ms("tool_x_latency_ms", 10.0)
    out = render_prometheus(m.snapshot(), namespace="readytrader")
    assert "readytrader_uptime_sec" in out
    assert "readytrader_counter_a_total 2" in out
    assert "readytrader_gauge_ws_last_message_age_sec 1.25" in out
    assert "readytrader_timer_tool_x_latency_ms_count" in out

