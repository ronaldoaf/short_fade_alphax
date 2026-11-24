"""Filtro de volatilidade com índice das 10 maiores por volume spot (mesma regra do índice de 30, n=10).
Uso: python tools/vol_top10.py
"""
import pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from vol_regime import C6


def main():
    P = opt.load()
    E = opt.Engine(P, (50_000,)); E.regimes()
    off = np.array(P["offs"])
    idx = {"30 por volume": pd.Series(E.index_level), "10 por volume": pd.Series(opt.crypto_index(P, n=10))}
    for fee in (0, 0.0005):
        rows = []
        for top in (5, 10):
            trades = {per: E.run({**C6, "top": top}, per, fee) for per in opt.SPLITS}
            rows.append({"top": top, "filtro": "sem filtro", **{p: f"{t['pnl'].mean()*100:+.1f}% ({len(t)})" for p, t in trades.items()}})
            for nm, lvl in idx.items():
                vol = lvl.pct_change(fill_method=None).rolling(672).std()
                med = vol.rolling(90 * 96, min_periods=45 * 96).median()
                low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
                r = {"top": top, "filtro": "vol baixa " + nm}
                for per, t in trades.items():
                    m = low[t["i"].to_numpy() + off[t["j"].to_numpy()]]
                    r[per] = f"{t['pnl'][m].mean()*100:+.1f}% ({m.sum()})"
                rows.append(r)
                if top == 5 and fee == 0:
                    print(f"{nm}: liberado {low[med.notna().to_numpy()].mean()*100:.0f}% do tempo")
        print(f"\n== taxa {fee} | média por trade em % da margem (n)")
        print(pd.DataFrame(rows).to_string(index=False))
    print("\nmembros atuais (10):", opt.crypto_index.members[-1][1])


if __name__ == "__main__":
    main()
