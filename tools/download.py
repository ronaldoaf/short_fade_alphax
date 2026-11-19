"""Baixa todo o histórico de 15m disponível de todos os perpétuos USDT da AlphaX.

Salva em data/cache/15m/<SYMBOL>.csv (incremental: só busca o que falta).
Uso: python tools/download.py [--workers 8]
"""
import argparse, csv, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "cache" / "15m"


def load(path):
    if not path.exists():
        return {}
    with path.open() as f:
        return {int(r["t"]): r for r in csv.DictReader(f)}


def fetch(symbol):
    path = OUT / f"{symbol}.csv"
    rows = load(path)
    have = max(rows) if rows else 0
    to = None
    for _ in range(10):
        k = alphax.klines(symbol, "15m", 1000, to)
        if not k:
            break
        for r in k:
            rows[r["t"]] = r
        if k[0]["t"] <= have or (to and k[0]["t"] >= to):
            break
        to = k[0]["t"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["t", "o", "h", "l", "c", "v"])
        w.writeheader()
        for t in sorted(rows):
            w.writerow({k: rows[t][k] for k in w.fieldnames})
    return symbol, len(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    syms = sorted({r["s"] for r in alphax.tickers() if r["s"].endswith("-SWAP-USDT")})
    done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for s, n in ex.map(fetch, syms):
            done += 1
            if done % 100 == 0:
                print(done, "/", len(syms), flush=True)
    print("ok", len(syms), "símbolos")


if __name__ == "__main__":
    main()
