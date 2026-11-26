"""Genere les figures du rapport a partir de results/*-series.json."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES = Path(__file__).resolve().parent.parent / "results"
FIG = Path(__file__).resolve().parent.parent / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 200})
BLUE, ORANGE, GREEN, RED, GREY, PURPLE = "#2a6fdb", "#e8821a", "#2e9d5b", "#d64545", "#777777", "#7b4fc9"


def load(name):
    return json.loads((RES / f"{name}-series.json").read_text())


def xy(s, key, t0, scale=1.0):
    pts = s.get(key, [])
    return [(t - t0) for t, _ in pts], [v * scale for _, v in pts]


# --- Figure : latence de traine (series temporelles) ---------------------------------
s = load("tail")
t0 = s["start"]
fig, ax = plt.subplots(figsize=(3.6, 2.2))
for key, lab, col, ls in [("p99_a", "p99", RED, "-"), ("p95_a", "p95", ORANGE, "-"),
                          ("avg_a", "moyenne", PURPLE, "--"), ("p50_a", "p50", GREEN, "-")]:
    x, y = xy(s, key, t0, 1000)
    ax.plot(x, y, color=col, ls=ls, lw=1.4, label=lab)
ax.set_xlim(20, s["end"] - t0)
ax.set_ylabel("latence order-api (ms)")
ax.set_xlabel("temps depuis le debut du tir (s)")
ax.set_yscale("log")
ax.set_yticks([10, 20, 50, 100, 200, 600])
ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.legend(ncol=4, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.17), frameon=False)
fig.tight_layout()
fig.savefig(FIG / "tail.png")

# --- Figure : propagation des erreurs ------------------------------------------------
s = load("errors")
t0 = s["start"]
fig, ax = plt.subplots(figsize=(3.6, 2.2))
for key, lab, col, ls in [("err_b", "serveur pricing-engine (B)", RED, "-"),
                          ("err_client", "client A -> B (vu par A)", ORANGE, "--"),
                          ("err_a", "serveur order-api (A)", BLUE, ":")]:
    x, y = xy(s, key, t0)
    ax.plot(x, y, color=col, ls=ls, lw=1.6, label=lab)
ax.set_xlim(20, s["end"] - t0)
ax.set_ylim(0, 16)
ax.set_ylabel("% reponses 5xx")
ax.set_xlabel("temps depuis le debut du tir (s)")
ax.legend(fontsize=6.5, loc="lower center", frameon=False, ncol=2)
fig.tight_layout()
fig.savefig(FIG / "errors.png")

# --- Figure : saturation CPU (debit vs latence) --------------------------------------
s = load("cpu")
t0 = s["start"]
steps = [25, 50, 75, 100, 125, 150]
offered_x, offered_y = [], []
for i, r in enumerate(steps):
    offered_x += [i * 60, i * 60 + 60]
    offered_y += [r, r]
fig, ax = plt.subplots(figsize=(7.4, 2.15))
ax.plot(offered_x, offered_y, color=GREY, ls="--", lw=1.2, label="debit demande par k6")
x, y = xy(s, "rate_a", t0)
ax.plot(x, y, color=BLUE, lw=1.8, label="debit traite (Rate order-api)")
ax.set_ylabel("requetes / s")
ax.set_xlabel("temps depuis le debut du tir (s)  -  paliers de 60 s : 25, 50, 75, 100, 125, 150 RPS")
ax.set_xlim(0, s["end"] - t0 + 20)
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
x, y = xy(s, "p99_a", t0, 1000)
ax2.plot(x, y, color=RED, lw=1.6, label="p99 order-api (ms)")
x, y = xy(s, "p50_a", t0, 1000)
ax2.plot(x, y, color=ORANGE, lw=1.4, label="p50 order-api (ms)")
ax2.set_yscale("log")
ax2.set_ylabel("latence (ms, echelle log)")
ax2.grid(False)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=6.5, loc="upper left", frameon=False)
fig.tight_layout()
fig.savefig(FIG / "cpu.png")

# --- Figure : CPU / throttling --------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.4, 1.65))
x, y = xy(s, "cpu_b", t0, 1000)
ax.plot(x, y, color=GREEN, lw=1.6, label="CPU pricing-engine (B)")
x, y = xy(s, "cpu_a", t0, 1000)
ax.plot(x, y, color=BLUE, lw=1.6, label="CPU order-api (A)")
ax.axhline(100, color=GREY, ls="--", lw=1, label="limite B = 100m")
ax.set_yscale("log")
ax.set_ylim(20, 1500)
ax.set_yticks([25, 50, 100, 250, 500, 1000])
ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.set_ylabel("millicoeurs")
ax.set_xlim(0, s["end"] - t0 + 20)
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
x, y = xy(s, "throttle_b", t0, 100)
ax2.plot(x, y, color=RED, lw=1.2, ls=":", label="% periodes CFS throttlees")
ax2.set_ylabel("% throttle")
ax2.set_ylim(0, 105)
ax2.grid(False)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=6.5, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, ncol=4)
ax.set_xlabel("temps depuis le debut du tir (s)")
fig.tight_layout()
fig.savefig(FIG / "cpu-throttle.png")
print("figures ->", FIG)
