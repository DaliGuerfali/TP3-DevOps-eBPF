"""Interroge Prometheus sur la fenetre de chaque tir k6 et produit :
  results/metrics.json  - tableau comparatif RED (A serveur, B serveur, A client)
  results/<nom>-series.json - series temporelles (pour les graphiques)
Usage : python scripts/collect.py [http://localhost:19091]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

PROM = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:19091"
RES = Path(__file__).resolve().parent.parent / "results"

SRV, CLI = "http_server_request_duration_seconds", "http_client_request_duration_seconds"
SELS = {
    "order-api (serveur)": (SRV, 'namespace="perf-lab",service_name="order-api",http_route="/order"'),
    "pricing-engine (serveur)": (SRV, 'namespace="perf-lab",service_name="pricing-engine",http_route="/price"'),
    "order-api -> pricing-engine (client)": (CLI, 'namespace="perf-lab",service_name="order-api"'),
}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def instant(expr, t):
    r = requests.get(f"{PROM}/api/v1/query", params={"query": expr, "time": t}).json()
    res = r["data"]["result"]
    return float(res[0]["value"][1]) if res else 0.0


def red(name, sel, w, t):
    """Metriques RED agregees sur toute la fenetre [w] se terminant a t."""
    cnt = f"sum(increase({name}_count{{{sel}}}[{w}s]))"
    out = {
        "requests": instant(cnt, t),
        "rps": instant(f"sum(rate({name}_count{{{sel}}}[{w}s]))", t),
        "avg_ms": 1000 * instant(f"sum(increase({name}_sum{{{sel}}}[{w}s])) / {cnt}", t),
        "err_pct": 100 * instant(
            f'sum(increase({name}_count{{{sel},http_response_status_code=~"5.."}}[{w}s])) / {cnt}', t),
    }
    for p in (0.50, 0.95, 0.99):
        out[f"p{int(p * 100)}_ms"] = 1000 * instant(
            f"histogram_quantile({p}, sum(increase({name}_bucket{{{sel}}}[{w}s])) by (le))", t)
    return out


def series(expr, start, end, step=10):
    r = requests.get(f"{PROM}/api/v1/query_range",
                     params={"query": expr, "start": start, "end": end, "step": step}).json()
    res = r["data"]["result"]
    return [[float(t), float(v)] for t, v in res[0]["values"]] if res else []


def main():
    table = {}
    for win in sorted(RES.glob("*-window.json")):
        w = json.loads(win.read_text())
        start, end = ts(w["start"]), ts(w["end"])
        # On ecarte les 10 premieres secondes (montee en charge) ; fin = fin du tir
        window = int(end - start - 10)
        k6 = next((json.loads(line.split(" ", 1)[1])
                   for line in (RES / f"{w['name']}-k6.txt").read_text().splitlines()
                   if line.startswith("K6_SUMMARY_JSON")), None)
        table[w["name"]] = {"window": w, "k6": k6,
                            "beyla": {k: red(n, s, window, end) for k, (n, s) in SELS.items()}}

        a = SELS["order-api (serveur)"][1]
        b = SELS["pricing-engine (serveur)"][1]
        c = SELS["order-api -> pricing-engine (client)"][1]
        pad = 60
        s = {
            "rate_a": series(f"sum(rate({SRV}_count{{{a}}}[30s]))", start - pad, end + pad),
            "rate_b": series(f"sum(rate({SRV}_count{{{b}}}[30s]))", start - pad, end + pad),
            "p50_a": series(f"histogram_quantile(0.5, sum(rate({SRV}_bucket{{{a}}}[30s])) by (le))", start - pad, end + pad),
            "p95_a": series(f"histogram_quantile(0.95, sum(rate({SRV}_bucket{{{a}}}[30s])) by (le))", start - pad, end + pad),
            "p99_a": series(f"histogram_quantile(0.99, sum(rate({SRV}_bucket{{{a}}}[30s])) by (le))", start - pad, end + pad),
            "avg_a": series(f"sum(rate({SRV}_sum{{{a}}}[30s])) / sum(rate({SRV}_count{{{a}}}[30s]))", start - pad, end + pad),
            "p99_b": series(f"histogram_quantile(0.99, sum(rate({SRV}_bucket{{{b}}}[30s])) by (le))", start - pad, end + pad),
            "avg_b": series(f"sum(rate({SRV}_sum{{{b}}}[30s])) / sum(rate({SRV}_count{{{b}}}[30s]))", start - pad, end + pad),
            "avg_client": series(f"sum(rate({CLI}_sum{{{c}}}[30s])) / sum(rate({CLI}_count{{{c}}}[30s]))", start - pad, end + pad),
            "err_a": series(f'100*sum(rate({SRV}_count{{{a},http_response_status_code=~"5.."}}[30s])) / sum(rate({SRV}_count{{{a}}}[30s]))', start - pad, end + pad),
            "err_b": series(f'100*sum(rate({SRV}_count{{{b},http_response_status_code=~"5.."}}[30s])) / sum(rate({SRV}_count{{{b}}}[30s]))', start - pad, end + pad),
            "err_client": series(f'100*sum(rate({CLI}_count{{{c},http_response_status_code=~"5.."}}[30s])) / sum(rate({CLI}_count{{{c}}}[30s]))', start - pad, end + pad),
            # cAdvisor est scrape toutes les 30 s : fenetre d'1 min pour eviter les trous
            "cpu_a": series('sum(rate(container_cpu_usage_seconds_total{namespace="perf-lab",container="order-api"}[1m]))', start - pad, end + pad),
            "cpu_b": series('sum(rate(container_cpu_usage_seconds_total{namespace="perf-lab",container="pricing-engine"}[1m]))', start - pad, end + pad),
            "throttle_b": series('sum(rate(container_cpu_cfs_throttled_periods_total{namespace="perf-lab",container="pricing-engine"}[1m])) / sum(rate(container_cpu_cfs_periods_total{namespace="perf-lab",container="pricing-engine"}[1m]))', start - pad, end + pad),
            "start": start, "end": end,
        }
        (RES / f"{w['name']}-series.json").write_text(json.dumps(s))

    (RES / "metrics.json").write_text(json.dumps(table, indent=2))
    for name, row in table.items():
        print(f"\n== {name}  (k6: {row['k6']})")
        for svc, m in row["beyla"].items():
            print(f"  {svc:40s} req={m['requests']:7.0f} rps={m['rps']:6.1f} avg={m['avg_ms']:7.1f} "
                  f"p50={m['p50_ms']:7.1f} p95={m['p95_ms']:7.1f} p99={m['p99_ms']:7.1f} err={m['err_pct']:5.2f}%")


if __name__ == "__main__":
    main()
