// Scenario de charge k6 sur POST /order (order-api).
//   MODE=constant : debit constant RPS (defaut 50) pendant DURATION (defaut 3m)
//   MODE=ramp     : paliers de 25 a 150 RPS (1 min par palier) - saturation CPU
import http from 'k6/http';
import { check } from 'k6';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.1.0/index.js';

const TARGET = __ENV.TARGET || 'http://order-api.perf-lab.svc:8000/order';
const MODE = __ENV.MODE || 'constant';
const ITEMS = ['laptop', 'phone', 'screen', 'keyboard', 'mouse'];

const scenarios = {
  constant: {
    executor: 'constant-arrival-rate',
    rate: Number(__ENV.RPS || 50),
    timeUnit: '1s',
    duration: __ENV.DURATION || '3m',
    preAllocatedVUs: 50,
    maxVUs: 500,
  },
  ramp: {
    executor: 'ramping-arrival-rate',
    startRate: 25,
    timeUnit: '1s',
    preAllocatedVUs: 100,
    maxVUs: 1500,
    stages: [25, 50, 75, 100, 125, 150].flatMap((rps) => [
      { target: rps, duration: '5s' },   // transition vers le palier
      { target: rps, duration: '55s' },  // palier stable
    ]),
  },
};

export const options = {
  scenarios: { order: scenarios[MODE] },
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const body = JSON.stringify({
    item: ITEMS[Math.floor(Math.random() * ITEMS.length)],
    quantity: 1 + Math.floor(Math.random() * 5),
  });
  const res = http.post(TARGET, body, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  });
  check(res, { 'status 200': (r) => r.status === 200 });
}

export function handleSummary(data) {
  const d = data.metrics.http_req_duration.values;
  const reqs = data.metrics.http_reqs.values;
  const failed = data.metrics.http_req_failed.values;
  const dropped = data.metrics.dropped_iterations ? data.metrics.dropped_iterations.values.count : 0;
  const compact = {
    mode: MODE, rps: reqs.rate, requests: reqs.count, error_ratio: failed.rate, dropped,
    avg: d.avg, p50: d.med, p90: d['p(90)'], p95: d['p(95)'], p99: d['p(99)'], max: d.max,
  };
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: false }) +
      '\nK6_SUMMARY_JSON ' + JSON.stringify(compact) + '\n',
  };
}
