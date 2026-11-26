# TP DevOps — Indicateurs RED d'une chaîne de microservices avec eBPF

**Équipe :** Mohamed Ali Guerfali, Alaeddine Zaouali, Rami Gharbi, Adem Saidi
**Stack :** kind · kube-prometheus-stack · Grafana Beyla 3.43 (eBPF) · k6

```
Client (k6 Job) ──▶ order-api (FastAPI, POST /order) ──▶ pricing-engine (Go, GET /price)
                         ▲                                    ▲
                         └──────── sondes eBPF (Beyla DaemonSet) ┘  ──▶ :9090/metrics ──▶ Prometheus ──▶ Grafana
```

Aucun des deux services n'importe de bibliothèque d'observabilité : toute la télémétrie vient de Beyla.

## Arborescence

| Chemin | Contenu |
|---|---|
| `services/order-api/` | Service A (Python FastAPI + httpx) et Dockerfile |
| `services/pricing-engine/` | Service B (Go `net/http`) avec injection de fautes par variables d'environnement |
| `kind-config.yaml` | Cluster kind mono-nœud `perf-lab` |
| `helm/kube-prometheus-stack-values.yaml` | Prometheus + Grafana en configuration minimale |
| `k8s/00..20-*.yaml` | Namespace `perf-lab`, Deployments et Services ClusterIP |
| `k8s/30-beyla.yaml` | Beyla : RBAC, ConfigMap, DaemonSet (BPF, SYS_PTRACE, NET_ADMIN…), Service, ServiceMonitor |
| `k8s/40-k6-job.yaml` | Job k6 exécuté dans le cluster |
| `k6/order-load.js` | Scénarios k6 : 50 RPS constant / paliers 25→150 RPS |
| `grafana/dashboard-red.json` | Export JSON du tableau de bord RED (généré par `scripts/build_dashboard.py`) |
| `scripts/` | Pilotage des régimes, collecte Prometheus, figures, captures Grafana |
| `results/` | Sorties k6, métriques mesurées (`metrics.json`), captures Grafana |
| `report/` | Rapport d'analyse (HTML → PDF) |

## Reproduire

```bash
# 1. Cluster + stack métrique
kind create cluster --config kind-config.yaml
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kps prometheus-community/kube-prometheus-stack -n monitoring --create-namespace \
     -f helm/kube-prometheus-stack-values.yaml

# 2. Images et services
docker build -t order-api:1.1 services/order-api
docker build -t pricing-engine:1.0 services/pricing-engine
kind load docker-image order-api:1.1 pricing-engine:1.0 --name perf-lab
kubectl apply -f k8s/00-namespace.yaml -f k8s/10-pricing-engine.yaml -f k8s/20-order-api.yaml

# 3. Beyla (eBPF) + dashboard
kubectl apply -f k8s/30-beyla.yaml
python scripts/build_dashboard.py
kubectl -n monitoring create configmap perf-lab-dashboard --from-file=dashboard-red.json=grafana/dashboard-red.json
kubectl -n monitoring label configmap perf-lab-dashboard grafana_dashboard=1

# 4. Tirs de charge (chaque régime reconfigure pricing-engine puis lance k6 dans le cluster)
kubectl -n perf-lab create configmap k6-script --from-file=k6/order-load.js
scripts/set-scenario.sh nominal && scripts/run-scenario.sh nominal constant 50
scripts/set-scenario.sh errors  && scripts/run-scenario.sh errors  constant 50
scripts/set-scenario.sh tail    && scripts/run-scenario.sh tail    constant 50
scripts/set-scenario.sh cpu     && scripts/run-scenario.sh cpu     ramp     150

# 5. Analyse (Prometheus port-forwardé sur :19091, Grafana sur :13000)
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 19091:9090 &
kubectl -n monitoring port-forward svc/kps-grafana 13000:80 &
python scripts/collect.py && python scripts/charts.py
```

Grafana : http://localhost:13000 (admin / perf-lab), tableau de bord « TP eBPF - RED order-api -> pricing-engine ».

## Points d'attention rencontrés

- **Beyla 3.x : les sélecteurs `discovery.instrument` sont des motifs glob, pas des regex.** Avec `^(order-api|pricing-engine)$`, rien n'était instrumenté.
- Les sondes de santé (`/health`) sont aussi mesurées par Beyla : les requêtes PromQL filtrent `http_route`.
- Le panneau d'erreurs utilise `1 - non_5xx / total` pour afficher 0 % au lieu de « No data » quand il n'y a aucune erreur.
- k6 tourne dans le cluster : un `kubectl port-forward` ajouterait sa propre latence et fausserait les mesures.
