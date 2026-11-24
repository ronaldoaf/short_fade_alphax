"""C6 com 'MA30 caindo' comparando com N períodos atrás (padrão C6: 10). LAG=5 python tools/opt_lag.py"""
import os, pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from vol_regime import C6


def feats(P, s, j, k4, k15):
    c = pd.Series(P["arrs"][s]["c"].astype(np.float64))
    ma = c.rolling(30).mean()
    s15 = ((c < ma) & (ma < ma.shift(k15))).to_numpy()
    t = P["tmin"] + (P["offs"][j] + np.arange(len(c), dtype=np.int64)) * opt.BAR
    b = pd.Series(t // (16 * opt.BAR))
    fc = c.groupby(b).last(); cs = fc.shift(1)
    m = pd.DataFrame({"a": cs.rolling(4).sum(), "b": cs.rolling(9).sum(), "c": cs.rolling(29).sum(),
                      "d": fc.rolling(30).mean().shift(k4)}).reindex(b).to_numpy()
    cv = c.to_numpy()
    ma5, ma10, m30 = (m[:, 0] + cv) / 5, (m[:, 1] + cv) / 10, (m[:, 2] + cv) / 30
    return (cv < m30) & (ma5 < ma10) & (ma10 < m30) & (m30 < m[:, 3]), s15


def main():
    L = int(os.environ.get("LAG", 5))
    P = opt.load(); off = np.array(P["offs"]); low = None
    var = {"C6 (10 períodos)": (10, 10), f"{L} no 4h": (L, 10), f"{L} no 15m": (10, L), f"{L} nos dois": (L, L)}
    res = {0: [], 0.0005: []}
    for nm, (k4, k15) in var.items():
        for j, s in enumerate(P["names"]):
            P["arrs"][s]["s4"], P["arrs"][s]["s15"] = feats(P, s, j, k4, k15)
        E = opt.Engine(P, (50_000,))
        if low is None:
            E.regimes()
            vol = pd.Series(E.index_level).pct_change(fill_method=None).rolling(672).std()
            med = vol.rolling(8640, min_periods=4320).median()
            low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
        for fee in res:
            for top in (5, 10):
                r = {"variante": nm, "top": top}
                for per in opt.SPLITS:
                    t = E.run({**C6, "top": top}, per, fee)
                    t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                    r[per] = f"{t['pnl'].mean()*100:+.1f}% ({len(t)})"
                    if per == "teste": r["soma teste"] = round(t["pnl"].sum())
                res[fee].append(r)
    for fee, rows in res.items():
        print(f"\n== vol baixa, taxa {fee}"); print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
