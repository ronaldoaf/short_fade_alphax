"""C6 trocando a MA30 por MA25 (no 4h, no 15m e nos dois). Top 5 e 10, com e sem filtro de volatilidade.
Uso: python tools/opt_ma25.py
"""
import pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from vol_regime import C6


def feats(P, s, j, n4, n15):
    c = pd.Series(P["arrs"][s]["c"].astype(np.float64))
    ma = c.rolling(n15).mean()
    s15 = ((c < ma) & (ma < ma.shift(10))).to_numpy()
    dist = (1 - c / ma).to_numpy()
    t = P["tmin"] + (P["offs"][j] + np.arange(len(c), dtype=np.int64)) * opt.BAR
    b = pd.Series(t // (16 * opt.BAR))
    fc = c.groupby(b).last(); cs = fc.shift(1)
    m = pd.DataFrame({"a": cs.rolling(4).sum(), "b": cs.rolling(9).sum(), "c": cs.rolling(n4 - 1).sum(),
                      "d": fc.rolling(n4).mean().shift(10)}).reindex(b).to_numpy()
    cv = c.to_numpy()
    ma5, ma10, mL = (m[:, 0] + cv) / 5, (m[:, 1] + cv) / 10, (m[:, 2] + cv) / n4
    s4 = (cv < mL) & (ma5 < ma10) & (ma10 < mL) & (mL < m[:, 3])
    return s4, s15, dist.astype(np.float32)


def main():
    P = opt.load()
    off = np.array(P["offs"])
    low = None
    variantes = {"MA30 (atual)": (30, 30), "MA25 só no 4h": (25, 30), "MA25 só no 15m": (30, 25), "MA25 nos dois": (25, 25)}
    res = {0: [], 0.0005: []}
    for nm, (n4, n15) in variantes.items():
        for j, s in enumerate(P["names"]):
            P["arrs"][s]["s4"], P["arrs"][s]["s15"], P["arrs"][s]["dist15"] = feats(P, s, j, n4, n15)
        E = opt.Engine(P, (50_000,))
        if low is None:
            E.regimes()
            vol = pd.Series(E.index_level).pct_change(fill_method=None).rolling(672).std()
            med = vol.rolling(90 * 96, min_periods=45 * 96).median()
            low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
        for fee in res:
            for top in (5, 10):
                for filt in ("sem filtro", "vol baixa"):
                    r = {"variante": nm, "top": top, "filtro": filt}
                    for per in opt.SPLITS:
                        t = E.run({**C6, "top": top}, per, fee)
                        if filt == "vol baixa":
                            t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                        r[per] = f"{t['pnl'].mean()*100:+.1f}% ({len(t)})"
                    res[fee].append(r)
    for fee, rows in res.items():
        print(f"\n== taxa {fee} | média por trade em % da margem (n)")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
