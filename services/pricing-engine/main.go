// pricing-engine (Service B) - moteur de calcul tarifaire GET /price.
//
// Aucune bibliotheque d'observabilite : Beyla instrumente ce binaire Go
// via des uprobes sur net/http, sans modification du code.
//
// Variables d'environnement d'injection de fautes :
//   LATENCY_MS        latence "normale" (defaut 15)
//   JITTER_MS         variation aleatoire +/- autour de LATENCY_MS (defaut 2)
//   SLOW_RATIO        fraction de requetes lentes, ex 0.05 (defaut 0)
//   SLOW_LATENCY_MS   latence des requetes lentes, ex 600
//   ERROR_RATE        fraction de reponses HTTP 500, ex 0.10 (defaut 0)
//   CPU_ITERATIONS    travail CPU reel par requete (hachages SHA-256)
package main

import (
	"crypto/sha256"
	"encoding/json"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"time"
)

func envFloat(k string, def float64) float64 {
	if v, err := strconv.ParseFloat(os.Getenv(k), 64); err == nil {
		return v
	}
	return def
}

var (
	latencyMs     = envFloat("LATENCY_MS", 15)
	jitterMs      = envFloat("JITTER_MS", 2)
	slowRatio     = envFloat("SLOW_RATIO", 0)
	slowLatencyMs = envFloat("SLOW_LATENCY_MS", 600)
	errorRate     = envFloat("ERROR_RATE", 0)
	cpuIterations = int(envFloat("CPU_ITERATIONS", 3000))
)

// burnCPU effectue un vrai calcul (et non une attente) : sous une limite
// CPU Kubernetes, ce travail est soumis au throttling CFS.
func burnCPU(seed string) [32]byte {
	sum := sha256.Sum256([]byte(seed))
	for i := 0; i < cpuIterations; i++ {
		sum = sha256.Sum256(sum[:])
	}
	return sum
}

func price(w http.ResponseWriter, r *http.Request) {
	item := r.URL.Query().Get("item")
	h := burnCPU(item)

	delay := latencyMs + (rand.Float64()*2-1)*jitterMs
	if rand.Float64() < slowRatio {
		delay = slowLatencyMs // pause GC / verrou I/O simule
	}
	time.Sleep(time.Duration(delay * float64(time.Millisecond)))

	if rand.Float64() < errorRate {
		http.Error(w, `{"error":"internal pricing error"}`, http.StatusInternalServerError)
		return
	}
	unit := 10 + float64(h[0])/10
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"item": item, "unit_price": unit})
}

func main() {
	start := time.Now()
	burnCPU("calibration")
	log.Printf("pricing-engine: latency=%.0fms jitter=%.0fms slow=%.2f@%.0fms errors=%.2f cpu_iter=%d (%.2fms CPU/req)",
		latencyMs, jitterMs, slowRatio, slowLatencyMs, errorRate, cpuIterations,
		float64(time.Since(start).Microseconds())/1000)
	http.HandleFunc("/price", price)
	http.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte("ok")) })
	log.Fatal(http.ListenAndServe(":8080", nil))
}
