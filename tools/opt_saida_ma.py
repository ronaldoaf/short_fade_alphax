"""C6 com saída extra: fechar a posição quando um candle de 15m fecha ACIMA da MA30 do 15m.
Só cripto no ranking, filtro de volatilidade (vol 7d do índice <= mediana 90d), 10x.
Variantes: C6 atual · C6 + saída MA30 · C6 + saída MA30 sem o stop de 1 ATR.
Uso: python tools/opt_saida_ma.py
"""
import pathlib, sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
import universe
from vol_regime import C6

VAR = {"C6 atual": C6,
       "C6 + sai se fechar > MA30 15m": {**C6, "exit_ma": 30},
       "idem, sem stop ATR": {**C6, "exit_ma": 30, "sl_atr": 0}}


def main():
    P = opt.load()
    off = np.array(P["offs"])
    E = opt.Engine(P, (50_000,))
    E.regimes()
    vol = pd.Series(E.index_level).pct_change(fill_method=None).rolling(672).std()
    med = vol.rolling(90 * 96, min_periods=45 * 96).median()
    low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
    m = universe.mascara_binance(P)
    P["R"][:, ~m] = np.nan
    P["V"][:, ~m] = 0
    E = opt.Engine(P, (50_000,))
    for fee in (0, 0.0005):
        rows = []
        for top in (5, 10):
            for nome, cfg in VAR.items():
                for per in opt.SPLITS:
                    t = E.run({**cfg, "top": top}, per, fee)
                    t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                    st = opt.stats(t)
                    ts = P["tmin"] + (t["i"].to_numpy() + off[t["j"].to_numpy()]) * opt.BAR
                    eq = pd.Series(t["pnl"].to_numpy(), index=ts).sort_index().cumsum()
                    dur = (t["k"] - t["i"]).mean() / 4 if "k" in t else np.nan
                    rows.append({"top": top, "regra": nome, "período": per, "n": st["n"], "média": f"{st['media']:+.1f}%",
                                 "soma": round(st["soma"]), "pior queda": round(float((eq - eq.cummax()).min())),
                                 "alvo/stop/liq/tempo/MA30": f"{st['pct_tp']}/{st['pct_stop']}/{st['pct_liq']}/{st['pct_tempo']}/{st['pct_ma']}"})
        d = pd.DataFrame(rows)
        print(f"\n== só cripto, vol baixa, taxa {fee}")
        for per in opt.SPLITS:
            print(f"\n-- {per}")
            print(d[d["período"] == per].drop(columns="período").to_string(index=False))
        d.to_csv(opt.ROOT / f"data/opt_saida_ma_fee{fee}.csv", index=False)


if __name__ == "__main__":
    main()
