#!/usr/bin/env bash
# Configure l'injection de fautes de pricing-engine pour chaque regime.
# Usage : scripts/set-scenario.sh <nominal|errors|tail|cpu>
set -euo pipefail
D=deploy/pricing-engine
case "$1" in
  nominal) kubectl -n perf-lab set env $D ERROR_RATE=0 SLOW_RATIO=0
           kubectl -n perf-lab patch $D --type=json \
             -p='[{"op":"remove","path":"/spec/template/spec/containers/0/resources"}]' 2>/dev/null || true ;;
  errors)  kubectl -n perf-lab set env $D ERROR_RATE=0.10 SLOW_RATIO=0 ;;          # 10 % de HTTP 500
  tail)    kubectl -n perf-lab set env $D ERROR_RATE=0 SLOW_RATIO=0.05 SLOW_LATENCY_MS=600 ;;  # 5 % a 600 ms
  cpu)     kubectl -n perf-lab set env $D ERROR_RATE=0 SLOW_RATIO=0
           kubectl -n perf-lab set resources $D --limits=cpu=100m --requests=cpu=100m ;;
esac
kubectl -n perf-lab rollout status $D --timeout=120s
sleep 20   # laisser Beyla detecter et instrumenter le nouveau processus
