"""order-api (Service A) - point d'entree POST /order.

Aucune bibliotheque d'observabilite n'est importee : toute la telemetrie
(metriques RED serveur ET client) est extraite par Grafana Beyla via eBPF.
"""
import hashlib
import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

PRICING_URL = os.getenv("PRICING_URL", "http://pricing-engine:8080/price")
# Petit travail CPU interne (validation / consolidation) pour rendre
# visible le "temps interne" de A dans la decomposition de latence.
VALIDATION_ROUNDS = int(os.getenv("VALIDATION_ROUNDS", "2000"))

app = FastAPI(title="order-api")
client = httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=200))


class Order(BaseModel):
    item: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0, le=1000)


def validate(order: Order) -> str:
    # Simule une validation metier (signature / controle d'integrite).
    digest = order.item.encode()
    for _ in range(VALIDATION_ROUNDS):
        digest = hashlib.sha256(digest).digest()
    return digest.hex()[:16]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/order")
async def create_order(order: Order):
    t0 = time.perf_counter()
    order_id = validate(order)
    resp = await client.get(PRICING_URL, params={"item": order.item, "qty": order.quantity})
    if resp.status_code >= 500:
        # L'erreur de B se propage : A renvoie a son tour une erreur 5xx.
        return JSONResponse(status_code=502, content={"error": "pricing-engine failure",
                                                       "upstream_status": resp.status_code})
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    price = resp.json()
    return {
        "order_id": order_id,
        "item": order.item,
        "quantity": order.quantity,
        "unit_price": price["unit_price"],
        "total": round(price["unit_price"] * order.quantity, 2),
        "handler_ms": round((time.perf_counter() - t0) * 1000, 2),
    }
