"""Testa se a volatilidade do índice cripto (30 maiores por volume spot, pesos iguais) separa trades bons e ruins.

Volatilidade = desvio-padrão dos retornos de 15m do índice numa janela W.
Limiar = mediana dessa volatilidade:
  - 'movel'  : mediana dos últimos L dias (só passado, sem olhar o futuro)
  - 'treino' : mediana fixa calculada só no período de treino
Para cada trade da regra C6 (top 5), compara o resultado com volatilidade ACIMA x ABAIXO do limiar.

Uso: python tools/vol_regime.py [--periodos treino,validacao]
"""
import argparse, pathlib, sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt

C6 = {**opt.BASE, "top": 5, "big4": 99, "big15": 99, "ord15": 1, "maxdist": 0.2, "tp": 0.15, "sl_atr": 1, "hold": 192}
JANELAS = {"1d": 96, "3d": 288, "7d": 672, "30d": 2880}
LOOKBACK = {"90d": 90 * 96, "365d": 365 * 96}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--periodos", default="treino,validacao")
    a = p.parse_args()
    P = opt.load()
    E = opt.Engine(P, (50_000,))
    E.regimes()
    lvl = pd.Series(E.index_level)
    ret = lvl.pct_change(fill_method=None)
    ts = pd.to_datetime(P["tmin"] + np.arange(len(lvl), dtype=np.int64) * opt.BAR, unit="ms")
    tr0, tr1 = (pd.Timestamp(x) for x in opt.SPLITS["treino"])
    off = np.array(P["offs"])

    limiares = {}
    for wn, w in JANELAS.items():
        vol = ret.rolling(w).std()
        for ln, L in LOOKBACK.items():
            med = vol.rolling(L, min_periods=L // 2).median()
            limiares[(wn, "móvel " + ln)] = (vol > med).to_numpy() , vol.notna().to_numpy() & med.notna().to_numpy()
        fixo = vol[(ts >= tr0) & (ts < tr1)].median()
        limiares[(wn, "fixa treino")] = (vol > fixo).to_numpy(), vol.notna().to_numpy()

    rows = []
    trades = {per: E.run(C6, per) for per in a.periodos.split(",")}
    for (wn, ln), (alta, valido) in limiares.items():
        r = {"janela vol": wn, "mediana": ln}
        for per, t in trades.items():
            g = t["i"].to_numpy() + off[t["j"].to_numpy()]
            ok = valido[g]
            hi = alta[g] & ok
            lo = ~alta[g] & ok
            r[f"{per} ALTA"] = f"{t['pnl'][hi].mean()*100:+.1f}% ({hi.sum()})"
            r[f"{per} BAIXA"] = f"{t['pnl'][lo].mean()*100:+.1f}% ({lo.sum()})"
        rows.append(r)
    print("C6 top 5 | resultado médio por trade (n) com volatilidade do índice ACIMA x ABAIXO da mediana")
    for per, t in trades.items():
        print(f"  {per}: todos {t['pnl'].mean()*100:+.1f}% ({len(t)})")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
