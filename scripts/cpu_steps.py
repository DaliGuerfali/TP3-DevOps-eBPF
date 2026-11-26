"""Statistiques par palier du tir de saturation CPU -> results/cpu-steps.json"""
import json, sys, requests
from pathlib import Path
PROM = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:19091"
RES = Path(__file__).resolve().parent.parent / "results"
w = json.loads((RES / "cpu-series.json").read_text()); t0 = w["start"]
SRV, CLI = "http_server_request_duration_seconds", "http_client_request_duration_seconds"
A = 'service_name="order-api",http_route="/order"'; B = 'service_name="pricing-engine",http_route="/price"'; C = 'service_name="order-api"'
def q(e, t):
    r = requests.get(f"{PROM}/api/v1/query", params={"query": e, "time": t}).json()["data"]["result"]
    return float(r[0]["value"][1]) if r else float("nan")
rows = []
for i, rps in enumerate([25, 50, 75, 100, 125, 150]):
    t = t0 + 60 * i + 60; W = "45s"      # 45 dernieres secondes de chaque palier
    pod = 'namespace="perf-lab",container="%s"'
    rows.append({
        "offered": rps,
        "rate_a": q(f"sum(rate({SRV}_count{{{A}}}[{W}]))", t),
        "avg_a": 1000 * q(f"sum(increase({SRV}_sum{{{A}}}[{W}]))/sum(increase({SRV}_count{{{A}}}[{W}]))", t),
        "p50_a": 1000 * q(f"histogram_quantile(0.5,sum(increase({SRV}_bucket{{{A}}}[{W}])) by (le))", t),
        "p99_a": 1000 * q(f"histogram_quantile(0.99,sum(increase({SRV}_bucket{{{A}}}[{W}])) by (le))", t),
        "avg_client": 1000 * q(f"sum(increase({CLI}_sum{{{C}}}[{W}]))/sum(increase({CLI}_count{{{C}}}[{W}]))", t),
        "avg_b": 1000 * q(f"sum(increase({SRV}_sum{{{B}}}[{W}]))/sum(increase({SRV}_count{{{B}}}[{W}]))", t),
        "cpu_b": 1000 * q(f"sum(rate(container_cpu_usage_seconds_total{{{pod % 'pricing-engine'}}}[1m]))", t),
        "cpu_a": 1000 * q(f"sum(rate(container_cpu_usage_seconds_total{{{pod % 'order-api'}}}[1m]))", t),
        "throttle_b": 100 * q(f"sum(rate(container_cpu_cfs_throttled_periods_total{{{pod % 'pricing-engine'}}}[1m]))/sum(rate(container_cpu_cfs_periods_total{{{pod % 'pricing-engine'}}}[1m]))", t),
    })
    r = rows[-1]; r["little_L"] = r["rate_a"] * r["avg_a"] / 1000
(RES / "cpu-steps.json").write_text(json.dumps(rows, indent=2))
print(f"{'RPS':>4} {'rateA':>6} {'avgA':>8} {'p50A':>8} {'p99A':>8} {'cliAB':>7} {'avgB':>7} {'cpuB':>5} {'thrB':>5} {'cpuA':>5} {'L=lW':>6}")
for r in rows:
    print(f"{r['offered']:4d} {r['rate_a']:6.1f} {r['avg_a']:8.0f} {r['p50_a']:8.0f} {r['p99_a']:8.0f} {r['avg_client']:7.0f} {r['avg_b']:7.0f} {r['cpu_b']:5.0f} {r['throttle_b']:5.0f} {r['cpu_a']:5.0f} {r['little_L']:6.0f}")
