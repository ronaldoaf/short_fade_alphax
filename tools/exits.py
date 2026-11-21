"""Testa variantes de saída para a regra atual (short), com as mesmas entradas do backtest.

Variantes: alvo fixo, alvo em múltiplos de ATR (4h), stop em ATR, trailing stop em ATR.
Sempre valem: liquidação em +9.5% e saída por tempo em 24h.
Conservador: dentro do mesmo candle de 15m, eventos adversos (liq/stop) são checados antes do alvo,
e o trailing usa a mínima dos candles ANTERIORES.

Uso: python tools/exits.py [--top 10]
"""
import argparse, glob, pathlib, sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from backtest import features, load_funding, funding_pnl, ROOT, DAY

LEV, LIQ = 10, 0.095


def sim(d, i, tp=None, sl=None, trail=None, act=0.0, hold=DAY):
    """Short aberto no fechamento de i. tp/sl/trail/act em fração do preço. Retorna (pnl, saída, j)."""
    e = d["c"].iat[i]
    hi, lo, cl = (d[k].to_numpy()[i + 1:i + 1 + hold] for k in ("h", "l", "c"))
    if len(hi) < hold:
        return None, "aberta", None
    best = e
    for k in range(hold):
        stop = None
        if sl is not None:
            stop = e * (1 + sl)
        if trail is not None and best <= e * (1 - act):
            ts = best * (1 + trail)
            stop = ts if stop is None else min(stop, ts)
        if hi[k] >= e * (1 + LIQ) and (stop is None or stop >= e * (1 + LIQ)):
            return -1.0, "liq", i + 1 + k
        if stop is not None and hi[k] >= stop:
            px = max(stop, lo[k]) if k else stop
            return max(-1.0, -(px / e - 1) * LEV), "stop", i + 1 + k
        if tp is not None and lo[k] <= e * (1 - tp):
            return tp * LEV, "tp", i + 1 + k
        best = min(best, lo[k])
    return max(-1.0, -(cl[-1] / e - 1) * LEV), "tempo", i + hold


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--vol", type=float, default=50_000)
    a = p.parse_args()

    data = {}
    for f in glob.glob(str(ROOT / "data/cache/15m/*.csv")):
        df = pd.read_csv(f)
        if len(df) >= 1000:
            data[pathlib.Path(f).stem] = features(df.reset_index(drop=True), 4)
    panel = pd.concat([d[["t", "ret24", "vol24"]].assign(s=s) for s, d in data.items()]).dropna()
    panel["rank"] = panel.groupby("t")["ret24"].rank(method="first")
    panel = panel[(panel["rank"] <= a.top) & (panel["vol24"] >= a.vol)]
    cand = panel.set_index(["s", "t"])["rank"]
    sig = {}
    for s, d in data.items():
        if s not in cand.index.get_level_values(0):
            continue
        pos = pd.Index(d["t"]).get_indexer(cand.loc[s].index)
        ok = d["ok4"].to_numpy() & d["ok15"].to_numpy() & (d["bigup15"].to_numpy() <= 4)
        sig[s] = [i for i in pos if ok[i] and np.isfinite(d["atr4"].iat[i])]
    funds = {s: load_funding(s) for s in sig}
    atr_med = np.nanmedian([data[s]["atr4"].iat[i] for s in sig for i in sig[s]])
    print(f"ATR(14) 4h mediano nas entradas: {atr_med:.1%} do preço\n")

    def run(name, fn):
        rows = []
        for s, idx in sig.items():
            d, free = data[s], -1
            for i in idx:
                if i <= free:
                    continue
                atr = d["atr4"].iat[i]
                pnl, how, j = sim(d, i, **fn(atr))
                if pnl is None:
                    continue
                fp = funding_pnl(funds[s], d["t"].iat[i], d["t"].iat[j])
                rows.append((max(-1.0, pnl + fp), how))
                free = j
        t = pd.DataFrame(rows, columns=["pnl", "saida"])
        sx = t["saida"].value_counts(normalize=True)
        print(f"{name:38s} {len(t):4d}  {t['pnl'].mean():+6.1%}  {t['pnl'].sum():+7.1f}  "
              f"tp {sx.get('tp',0):4.0%} stop {sx.get('stop',0):4.0%} liq {sx.get('liq',0):4.0%} tempo {sx.get('tempo',0):4.0%}"
              f"  acerto {(t['pnl']>0).mean():4.0%}")

    print(f"{'variante':38s} {'n':>4s}  {'média':>6s}  {'soma':>7s}")
    run("Atual: alvo fixo 10%", lambda atr: dict(tp=0.10))
    for k in (1, 1.5, 2, 3):
        run(f"Alvo {k} ATR", lambda atr, k=k: dict(tp=k * atr))
    for k in (1, 1.5, 2):
        run(f"Alvo 10% + stop {k} ATR", lambda atr, k=k: dict(tp=0.10, sl=k * atr))
    for k in (1, 1.5, 2, 3):
        run(f"Trailing {k} ATR (sem alvo)", lambda atr, k=k: dict(trail=k * atr))
    for k in (1, 1.5, 2):
        run(f"Trailing {k} ATR ativa após 1 ATR", lambda atr, k=k: dict(trail=k * atr, act=atr))
    for k in (1, 2):
        run(f"Alvo 2 ATR + trailing {k} ATR", lambda atr, k=k: dict(tp=2 * atr, trail=k * atr))
    run("Trailing fixo 5% (sem alvo)", lambda atr: dict(trail=0.05))
    run("Trailing 5% ativa após queda de 5%", lambda atr: dict(trail=0.05, act=0.05))
    run("Alvo 10% + trailing 5% ativa após 5%", lambda atr: dict(tp=0.10, trail=0.05, act=0.05))
    run("Sem alvo, 48h", lambda atr: dict(hold=2 * DAY))
    run("Trailing 2 ATR, 48h", lambda atr: dict(trail=2 * atr, hold=2 * DAY))


if __name__ == "__main__":
    main()
