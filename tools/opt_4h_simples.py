"""C6 sem a exigência MA5 < MA10 < MA30 no 4h.
Variantes de 4h: 'C6' (atual), 'A' só preço < MA30 e MA30 caindo (vs 10 velas), 'sem 4h'.
Também testa o 15m com e sem MA5 < MA10. Com e sem filtro de volatilidade (índice de 30).
Uso: python tools/opt_4h_simples.py
"""
import pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from vol_regime import C6


def s4_simples(P):
    out = {}
    for j, s in enumerate(P["names"]):
        c = pd.Series(P["arrs"][s]["c"].astype(np.float64))
        t = P["tmin"] + (P["offs"][j] + np.arange(len(c), dtype=np.int64)) * opt.BAR
        b = pd.Series(t // (16 * opt.BAR))
        fc = c.groupby(b).last()
        m = pd.DataFrame({"s29": fc.shift(1).rolling(29).sum(), "m30_10": fc.rolling(30).mean().shift(10)}).reindex(b).to_numpy()
        cv = c.to_numpy(); ma30 = (m[:, 0] + cv) / 30
        out[s] = (cv < ma30) & (ma30 < m[:, 1])
    return out


def main():
    P = opt.load()
    orig = {s: P["arrs"][s]["s4"].copy() for s in P["names"]}
    simp = s4_simples(P)
    variantes = {"C6 (MA5<MA10<MA30)": orig, "A: só preço<MA30 e MA30 caindo": simp,
                 "sem 4h": {s: np.ones_like(v) for s, v in orig.items()}}
    lvl = None
    off = np.array(P["offs"])
    for fee in (0, 0.0005):
        rows = []
        for nm, s4 in variantes.items():
            for s in P["names"]:
                P["arrs"][s]["s4"] = s4[s]
            E = opt.Engine(P, (50_000,))
            if lvl is None:
                E.regimes(); lvl = pd.Series(E.index_level)
                vol = lvl.pct_change(fill_method=None).rolling(672).std()
                med = vol.rolling(90 * 96, min_periods=45 * 96).median()
                low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
            for ord15 in (1, 0):
                for top in (5, 10):
                    for filt in ("sem filtro", "vol baixa"):
                        r = {"4h": nm, "15m ma5<10": "sim" if ord15 else "não", "top": top, "filtro": filt}
                        for per in opt.SPLITS:
                            t = E.run({**C6, "top": top, "ord15": ord15}, per, fee)
                            if filt == "vol baixa":
                                t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                            r[per] = f"{t['pnl'].mean()*100:+.1f}% ({len(t)})"
                        rows.append(r)
        print(f"\n== taxa {fee} | média por trade em % da margem (n)")
        print(pd.DataFrame(rows).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
