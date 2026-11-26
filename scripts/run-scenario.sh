#!/usr/bin/env bash
# Lance un tir k6 dans le cluster et enregistre sa fenetre temporelle.
# Usage : scripts/run-scenario.sh <nom> <constant|ramp> [rps]
set -euo pipefail
cd "$(dirname "$0")/.."
NAME=$1; MODE=$2; RPS=${3:-50}
mkdir -p results

kubectl -n perf-lab delete job "k6-$NAME" --ignore-not-found >/dev/null
START=$(date +%s)
sed -e "s/__NAME__/$NAME/" -e "s/__MODE__/$MODE/" -e "s/__RPS__/$RPS/" k8s/40-k6-job.yaml | kubectl apply -f - >/dev/null
kubectl -n perf-lab wait --for=condition=complete "job/k6-$NAME" --timeout=15m >/dev/null \
  || kubectl -n perf-lab wait --for=condition=failed "job/k6-$NAME" --timeout=10s >/dev/null || true
END=$(date +%s)
kubectl -n perf-lab logs "job/k6-$NAME" > "results/$NAME-k6.txt"
# Debut reel du tir = demarrage du conteneur k6 (le pull d'image ne compte pas)
POD_START=$(kubectl -n perf-lab get pod -l job-name="k6-$NAME" -o jsonpath='{.items[0].status.containerStatuses[0].state.terminated.startedAt}')
POD_END=$(kubectl -n perf-lab get pod -l job-name="k6-$NAME" -o jsonpath='{.items[0].status.containerStatuses[0].state.terminated.finishedAt}')
echo "{\"name\":\"$NAME\",\"mode\":\"$MODE\",\"rps\":$RPS,\"start\":\"$POD_START\",\"end\":\"$POD_END\"}" > "results/$NAME-window.json"
grep K6_SUMMARY_JSON "results/$NAME-k6.txt" || tail -20 "results/$NAME-k6.txt"
