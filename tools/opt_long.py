"""Versão LONG espelhada da regra C6, com e sem o filtro de volatilidade baixa do índice cripto.

Espelho exato da C6:
  Universo : N MELHORES retornos de 24h (volume >= 50k)
  4h       : preço > MA30, MA5 > MA10 > MA30, MA30 subindo (vs 10 velas atrás)
  15m      : preço > MA30, MA30 subindo, MA5 > MA10, preço no máx. 20% ACIMA da MA30
  Saída    : long 10x; alvo +15%; stop = entrada - 1 ATR(14) do 4h; liquidação em -9,5%; 48h
  Funding  : long paga funding positivo.
Filtro: volatilidade de 7d do índice abaixo da mediana dos últimos 90 dias.

Uso: python tools/opt_long.py
"""
import pathlib, sys

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from opt import BAR, LEV, LIQ, SPLITS


@njit(cache=True)
def sim_long(h, l, c, i, tp, sl, hold):
    e = c[i]
    if i + hold >= len(c):
        return np.nan, -1, -1
    liq_px = e * (1 - LIQ)
    stop = e * (1 - sl) if sl > 0 else -1.0
    for k in range(i + 1, i + hold + 1):
        if l[k] <= max(liq_px, stop):
            if stop > liq_px:
                return max(-1.0, (stop / e - 1) * LEV), 1, k
            return -1.0, 2, k
        if h[k] >= e * (1 + tp):
            return tp * LEV, 0, k
    return max(-1.0, (c[i + hold] / e - 1) * LEV), 3, i + hold


def long_features(P):
    """Recalcula, a partir dos fechamentos, as condições espelhadas para long."""
    feats = {}
    for j, s in enumerate(P["names"]):
        a = P["arrs"][s]
        c = pd.Series(a["c"].astype(np.float64))
        ma30 = c.rolling(30).mean()
        s15 = (c > ma30) & (ma30 > ma30.shift(10))
        ord15 = c.rolling(5).mean() > c.rolling(10).mean()
        dist = c / ma30 - 1
        t = P["tmin"] + (P["offs"][j] + np.arange(len(c), dtype=np.int64)) * BAR
        b = pd.Series(t // (16 * BAR))
        fc = c.groupby(b).last()
        cs = fc.shift(1)
        m = pd.DataFrame({"s4": cs.rolling(4).sum(), "s9": cs.rolling(9).sum(), "s29": cs.rolling(29).sum(),
                          "m30_10": fc.rolling(30).mean().shift(10)}).reindex(b).to_numpy()
        cv = c.to_numpy()
        ma5, ma10, m30 = (m[:, 0] + cv) / 5, (m[:, 1] + cv) / 10, (m[:, 2] + cv) / 30
        s4 = (cv > m30) & (ma5 > ma10) & (ma10 > m30) & (m30 > m[:, 3])
        feats[s] = dict(s4=s4, s15=s15.to_numpy(), ord15=ord15.to_numpy(), dist=dist.to_numpy())
    return feats


def candidates(P, F, top, vmin=50_000):
    negR = {"R": -P["R"], "V": P["V"]}
    tt, jj, rk = opt.ranks(negR, vmin, nmax=max(top, 20))
    sel = rk <= top
    tt, jj, rk = tt[sel], jj[sel], rk[sel]
    rows = []
    for j in np.unique(jj):
        s = P["names"][j]
        m = jj == j
        i = tt[m] - P["offs"][j]
        f, a = F[s], P["arrs"][s]
        n = len(a["c"])
        ok = (i >= 0) & (i < n)
        i, tg = i[ok], tt[m][ok]
        ok = f["s4"][i] & f["s15"][i] & f["ord15"][i] & (f["dist"][i] <= 0.20)
        rows.append(pd.DataFrame({"j": j, "i": i[ok], "t": tg[ok], "atr4": a["atr4"][i[ok]]}))
    return pd.concat(rows).sort_values(["j", "i"]).reset_index(drop=True)


def run(P, cand, period=None, regime=None, fee=0.0, tp=0.15, sl_atr=1.0, hold=192):
    c = cand
    if regime is not None:
        c = c[regime[c["t"].to_numpy()]]
    if period:
        a, b = (pd.Timestamp(x).value // 10**6 for x in SPLITS[period])
        ts = P["tmin"] + c["t"].to_numpy().astype(np.int64) * BAR
        c = c[(ts >= a) & (ts < b)]
    rows = []
    for j, g in c.groupby("j", sort=False):
        a = P["arrs"][P["names"][j]]
        free = -1
        for i, atr in zip(g["i"].to_numpy(), g["atr4"].to_numpy()):
            if i <= free:
                continue
            sl = sl_atr * atr if np.isfinite(atr) else 0
            pnl, how, k = sim_long(a["h"], a["l"], a["c"], int(i), tp, sl, hold)
            if how < 0:
                continue
            f = -float(a["fcum"][k] - a["fcum"][i]) * LEV  # long paga funding positivo
            rows.append((i, j, max(-1.0, pnl + f - 2 * fee * LEV), how, f))
            free = k
    return pd.DataFrame(rows, columns=["i", "j", "pnl", "saida", "fund"])


def main():
    P = opt.load()
    E = opt.Engine(P, (50_000,))
    E.regimes()
    ret = pd.Series(E.index_level).pct_change(fill_method=None)
    vol = ret.rolling(672).std()
    med = vol.rolling(90 * 96, min_periods=45 * 96).median()
    baixa = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
    alta = ((vol > med) & vol.notna() & med.notna()).to_numpy()
    F = long_features(P)
    for fee in (0, 0.0005):
        rows = []
        for top in (3, 5, 10):
            cand = candidates(P, F, top)
            for nome, rg in (("sem filtro", None), ("vol baixa", baixa), ("vol alta", alta)):
                for per in SPLITS:
                    st = opt.stats(run(P, cand, per, rg, fee))
                    rows.append({"top": top, "filtro": nome, "periodo": per, **st})
        d = pd.DataFrame(rows)
        print(f"\n== LONG espelhado | taxa {fee} | média por trade em % da margem (n)")
        d["cel"] = d.apply(lambda r: f"{r.media:+.1f}% ({r.n})", axis=1)
        print(d.pivot_table(index=["top", "filtro"], columns="periodo", values="cel", aggfunc="first")
              [list(SPLITS)].to_string())
        d.to_csv(opt.ROOT / f"data/opt_long_fee{fee}.csv", index=False)


if __name__ == "__main__":
    main()
