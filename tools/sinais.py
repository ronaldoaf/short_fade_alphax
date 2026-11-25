"""Confere o resultado dos sinais gravados pelo scanner (data/sinais.csv) com os candles de 15m da AlphaX.

Simula a regra C6 a partir do preço do scan: short 10x, alvo -15%, stop +1 ATR(14) do 4h, liquidação +9,5%,
saída em 48h. No mesmo candle, stop/liquidação contam antes do alvo (como no backtest).
Uso: python tools/sinais.py [--todos]   (padrão: só sinais com o filtro de volatilidade liberado)
"""
import argparse, pathlib, sys, time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import alphax

LOG = pathlib.Path(__file__).resolve().parent.parent / "data/sinais.csv"
BAR, HOLD, LEV = 15 * 60 * 1000, 192, 10
REF = ("Backtest de referência (teste jul/25-nov/26, só cripto, 10x, taxa 0): média +4,4% por operação; "
       "saídas: alvo 26%, stop 38%, liquidação 20%, tempo 16%.")


def resultado(r, now_ms):
    t0 = int(pd.Timestamp(r["candle_utc"]).value // 10**6)
    fim = t0 + (HOLD + 1) * BAR
    k = pd.DataFrame(alphax.klines(r["ativo"], "15m", 220, min(now_ms, fim)))
    k = k[k["t"] > t0]  # candles seguintes ao do sinal
    e, alvo, stop, liq = r["preco"], r["alvo"], r["stop"], r["liquidacao"]
    lim = min(stop, liq) if np.isfinite(stop) else liq
    for _, c in k.iterrows():
        if c["h"] >= lim:
            if np.isfinite(stop) and stop < liq:
                return "stop", max(-1.0, -(stop / e - 1) * LEV), c["t"]
            return "liquidação", -1.0, c["t"]
        if c["l"] <= alvo:
            return "alvo", (1 - alvo / e) * LEV, c["t"]
    if len(k) and k["t"].iloc[-1] + BAR >= fim - BAR:
        return "tempo", max(-1.0, -(k["c"].iloc[-1] / e - 1) * LEV), k["t"].iloc[-1]
    px = k["c"].iloc[-1] if len(k) else e
    return "aberta", max(-1.0, -(px / e - 1) * LEV), None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--todos", action="store_true", help="inclui sinais bloqueados pelo filtro de volatilidade")
    a = p.parse_args()
    if not LOG.exists():
        print("Nenhum sinal gravado ainda (data/sinais.csv).")
        return
    d = pd.read_csv(LOG)
    if not a.todos:
        d = d[d["filtro_liberado"]]
    if d.empty:
        print("Nenhum sinal com o filtro liberado. Use --todos para ver os bloqueados.")
        return
    now = int(time.time() * 1000)
    res = [resultado(r, now) for _, r in d.iterrows()]
    d["saida"] = [x[0] for x in res]
    d["pnl_margem"] = [f"{x[1]*100:+.0f}%" for x in res]
    d["pnl"] = [x[1] for x in res]
    cols = ["candle_utc", "ativo", "rank", "preco", "alvo", "stop", "filtro_liberado", "saida", "pnl_margem"]
    print(d[cols].to_string(index=False))
    fech = d[d["saida"] != "aberta"]
    if len(fech):
        print(f"\nFechadas: {len(fech)} | média {fech['pnl'].mean()*100:+.1f}% da margem | soma {fech['pnl'].sum():+.2f} margens")
        print("Saídas:", fech["saida"].value_counts().to_dict())
    print(REF)


if __name__ == "__main__":
    main()
