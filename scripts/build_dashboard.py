"""Genere grafana/dashboard-red.json (tableau de bord RED du TP)."""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}
SRV = 'http_server_request_duration_seconds'
CLI = 'http_client_request_duration_seconds'
SEL = 'namespace="perf-lab",http_route=~"/order|/price"'
A = 'namespace="perf-lab",service_name="order-api",http_route="/order"'
B = 'namespace="perf-lab",service_name="pricing-engine",http_route="/price"'
AC = 'namespace="perf-lab",service_name="order-api"'


def q(expr, legend, ref):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}


def pct(sel, p, name, ref):
    return q(f'histogram_quantile({p}, sum(rate({name}_bucket{{{sel}}}[1m])) by (le))',
             f"p{int(p * 100)}", ref)


def avg(sel, name, legend, ref):
    return q(f'sum(rate({name}_sum{{{sel}}}[1m])) / sum(rate({name}_count{{{sel}}}[1m]))', legend, ref)


def panel(pid, title, targets, x, y, w=12, h=9, unit="s", desc=""):
    return {
        "id": pid, "type": "timeseries", "title": title, "description": desc,
        "datasource": DS, "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 5}},
                        "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom",
                               "calcs": ["mean", "max", "lastNotNull"]},
                    "tooltip": {"mode": "multi"}},
        "targets": targets,
    }


panels = [
    panel(1, "RATE - debit par service (req/s)", [
        q(f'sum(rate({SRV}_count{{{SEL}}}[1m])) by (service_name)', "serveur {{service_name}}", "A"),
        q(f'sum(rate({CLI}_count{{{AC}}}[1m]))', "client order-api -> pricing-engine", "B"),
    ], 0, 0, unit="reqps"),
    panel(2, "ERRORS - % reponses 5xx (vue serveur et vue client)", [
        # 1 - (non-5xx / total) : renvoie 0 % (et non "No data") quand aucune erreur n'existe
        q(f'100 * (1 - sum(rate({SRV}_count{{{SEL},http_response_status_code!~"5.."}}[1m])) by (service_name)'
          f' / sum(rate({SRV}_count{{{SEL}}}[1m])) by (service_name))', "serveur {{service_name}}", "A"),
        q(f'100 * (1 - sum(rate({CLI}_count{{{AC},http_response_status_code!~"5.."}}[1m]))'
          f' / sum(rate({CLI}_count{{{AC}}}[1m])))', "client order-api -> pricing-engine", "B"),
    ], 12, 0, unit="percent",
        desc="Si le % client A->B egale le % serveur de B, la faute vient de B et A ne fait que la propager."),
    panel(3, "DURATION - order-api (POST /order)", [
        pct(A, 0.50, SRV, "A"), pct(A, 0.95, SRV, "B"), pct(A, 0.99, SRV, "C"),
        avg(A, SRV, "moyenne", "D"),
    ], 0, 9),
    panel(4, "DURATION - pricing-engine (GET /price)", [
        pct(B, 0.50, SRV, "A"), pct(B, 0.95, SRV, "B"), pct(B, 0.99, SRV, "C"),
        avg(B, SRV, "moyenne", "D"),
    ], 12, 9),
    panel(5, "DECOMPOSITION - T_interne(A) = T_serveur(A) - T_client(A->B) (moyennes)", [
        avg(A, SRV, "T_serveur(A)", "A"),
        avg(AC, CLI, "T_client(A->B)", "B"),
        q(f'(sum(rate({SRV}_sum{{{A}}}[1m])) / sum(rate({SRV}_count{{{A}}}[1m])))'
          f' - (sum(rate({CLI}_sum{{{AC}}}[1m])) / sum(rate({CLI}_count{{{AC}}}[1m])))',
          "T_interne(A)", "C"),
    ], 0, 18),
    panel(6, "SATURATION - CPU pricing-engine (coeurs) et % periodes throttlees", [
        q('sum(rate(container_cpu_usage_seconds_total{namespace="perf-lab",container="pricing-engine"}[1m]))',
          "CPU utilise (coeurs)", "A"),
        q('sum(rate(container_cpu_cfs_throttled_periods_total{namespace="perf-lab",container="pricing-engine"}[1m]))'
          ' / sum(rate(container_cpu_cfs_periods_total{namespace="perf-lab",container="pricing-engine"}[1m]))',
          "ratio periodes throttlees", "B"),
    ], 12, 18, unit="short"),
]

dashboard = {
    "uid": "perf-lab-red", "title": "TP eBPF - RED order-api -> pricing-engine",
    "tags": ["ebpf", "beyla", "red"], "timezone": "browser", "schemaVersion": 39,
    "refresh": "10s", "time": {"from": "now-30m", "to": "now"}, "panels": panels,
}

out = Path(__file__).resolve().parent.parent / "grafana" / "dashboard-red.json"
out.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
print("written", out)
