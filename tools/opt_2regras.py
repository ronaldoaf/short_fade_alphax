"""Só 2 regras: MA30 caindo (vs 10 velas atrás) no 4h e no 15m. Sem preço<MA30, sem ordem de médias, sem distância.
Mesmas saídas da C6 (alvo -15%, stop 1 ATR 4h, 48h). Compara com a C6. Com e sem filtro de volatilidade.
Uso: python tools/opt_2regras.py
"""
import pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from vol_regime import C6


def feats(P, s, j):
    c = pd.Series(P["arrs"][s]["c"].astype(np.float64))
    ma = c.rolling(30).mean()
    s15 = (ma < ma.shift(10)).to_numpy()
    t = P["tmin"] + (P["offs"][j] + np.arange(len(c), dtype=np.int64)) * opt.BAR
    b = pd.Series(t // (16 * opt.BAR))
    fc = c.groupby(b).last()
    m = pd.DataFrame({"c": fc.shift(1).rolling(29).sum(), "d": fc.rolling(30).mean().shift(10)}).reindex(b).to_numpy()
    m30 = (m[:, 0] + c.to_numpy()) / 30
    return m30 < m[:, 1], s15


def main():
    P = opt.load()
    off = np.array(P["offs"])
    E0 = opt.Engine(P, (50_000,)); E0.regimes()
    vol = pd.Series(E0.index_level).pct_change(fill_method=None).rolling(672).std()
    med = vol.rolling(90 * 96, min_periods=45 * 96).median()
    low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
    for j, s in enumerate(P["names"]):
        P["arrs"][s]["s4"], P["arrs"][s]["s15"] = feats(P, s, j)
    E1 = opt.Engine(P, (50_000,))
    variantes = {"C6 atual": (E0, C6), "2 regras": (E1, {**C6, "ord15": 0, "maxdist": 9})}
    for fee in (0, 0.0005):
        rows = []
        for nm, (E, cfg) in variantes.items():
            for top in (5, 10):
                for filt in ("sem filtro", "vol baixa"):
                    r = {"regra": nm, "top": top, "filtro": filt}
                    for per in opt.SPLITS:
                        t = E.run({**cfg, "top": top}, per, fee)
                        if filt == "vol baixa":
                            t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                        st = opt.stats(t)
                        r[per] = f"{st['media']:+.1f}% ({st['n']})"
                        if per == "teste":
                            r["saídas teste alvo/stop/liq/tempo"] = f"{st['pct_tp']}/{st['pct_stop']}/{st['pct_liq']}/{st['pct_tempo']}"
                    rows.append(r)
        print(f"\n== taxa {fee} | média por trade em % da margem (n)")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
