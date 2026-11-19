"""Scanner ao vivo: aplica a regra atual aos piores de 24h agora.

Uso: python tools/scan.py [--top 20] [--vol 50000]
"""
import argparse, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax
from backtest import features


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--vol", type=float, default=50_000)
    a = p.parse_args()
    worst = alphax.worst_24h(a.top)
    now = time.time() * 1000

    def one(row):
        s, m, qv = row
        df = pd.DataFrame(alphax.klines(s, "15m", 1000))
        df = df[df["t"] + 15 * 60 * 1000 <= now].reset_index(drop=True)  # só candles fechados
        f = features(df, 4).iloc[-1]
        return s, m, qv, bool(f.ok4), bool(f.ok15), f.c

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, worst))
    print(f"{'#':>2} {'ativo':22} {'24h':>7} {'vol24h':>12}  4h   15m  sinal")
    for i, (s, m, qv, o4, o15, c) in enumerate(res, 1):
        sig = "SHORT" if (o4 and o15 and qv >= a.vol) else ("(vol baixo)" if o4 and o15 else "")
        print(f"{i:2d} {s.replace('-SWAP-USDT',''):22} {m*100:6.2f}% {qv:12,.0f}  {'ok' if o4 else '--':4} {'ok' if o15 else '--':4} {sig}")


if __name__ == "__main__":
    main()
