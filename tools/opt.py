"""Otimização da estratégia com dados da Binance (data/cache/binance), dividida em treino / validação / teste.

Etapas:
  python tools/opt.py prep     # calcula indicadores de todos os ativos (uma vez) -> data/cache/binance/prep.pkl
  python tools/opt.py entry    # grade de parâmetros de ENTRADA no treino (saída padrão)
  python tools/opt.py exit     # grade de SAÍDAS para os melhores conjuntos de entrada
  python tools/opt.py eval --cfg '<json>'   # avalia um conjunto em treino/validação/teste

Custos: taxa por lado (padrão 0, como AlphaX) + funding real da Binance.
Execução: short 10x, liquidação em +9,5%; dentro do mesmo candle de 15m, eventos adversos vêm antes do alvo.
"""
import argparse, glob, itertools, json, pathlib, pickle, sys, time

import numpy as np
import pandas as pd
from numba import njit

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = ROOT / "data/cache/binance"
BAR = 15 * 60 * 1000
DAY = 96
LEV, LIQ = 10, 0.095
SPLITS = {"treino": ("2023-01-01", "2024-07-01"), "validacao": ("2024-07-01", "2025-07-01"),
          "teste": ("2025-07-01", "2026-12-01")}
COLS = ["h", "l", "c", "s4", "big4", "s15", "ord15", "dist15", "big15", "atr4", "fcum"]


# ---------------------------------------------------------------- indicadores
def prep_symbol(df, fund):
    t0, t1 = df["t"].iat[0], df["t"].iat[-1]
    grid = np.arange(t0, t1 + BAR, BAR)
    df = df.set_index("t").reindex(grid)
    df["c"] = df["c"].ffill()
    for k in "ohl":
        df[k] = df[k].fillna(df["c"])
    df["v"] = df["v"].fillna(0)
    df = df.reset_index().rename(columns={"index": "t"})
    c, o, h, l = df["c"], df["o"], df["h"], df["l"]
    out = pd.DataFrame({"h": h, "l": l, "c": c})
    out["ret24"] = c / c.shift(DAY) - 1
    out["vol24"] = df["v"].rolling(DAY).sum()
    # 15m
    ma30 = c.rolling(30).mean()
    out["s15"] = (c < ma30) & (ma30 < ma30.shift(10))
    out["ord15"] = c.rolling(5).mean() < c.rolling(10).mean()
    out["dist15"] = 1 - c / ma30
    rng = (h - l) / o
    base = rng.shift(10).rolling(30).mean()
    out["big15"] = (rng / base).where(c > o, 0).rolling(10).max()
    # 4h com vela em formação
    b = df["t"] // (16 * BAR)
    g = df.groupby(b)
    full = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()})
    fr = (full["h"] - full["l"]) / full["o"]
    fbase = fr.shift(10).rolling(30).mean()
    fratio = (fr / fbase).where(full["c"] > full["o"], 0)
    cs = full["c"].shift(1)
    m = pd.DataFrame({"s4": cs.rolling(4).sum(), "s9": cs.rolling(9).sum(), "s29": cs.rolling(29).sum(),
                      "m30_10": full["c"].rolling(30).mean().shift(10),
                      "bigprev": fratio.shift(1).rolling(9).max(), "base": fbase}).reindex(b).to_numpy()
    cv = c.to_numpy()
    ma5, ma10, ma30_4 = (m[:, 0] + cv) / 5, (m[:, 1] + cv) / 10, (m[:, 2] + cv) / 30
    out["s4"] = (cv < ma30_4) & (ma5 < ma10) & (ma10 < ma30_4) & (ma30_4 < m[:, 3])
    cur_o = g["o"].transform("first").to_numpy()
    cur_r = ((g["h"].cummax() - g["l"].cummin()).to_numpy() / cur_o) / m[:, 5]
    cur_r = np.where(cv > cur_o, cur_r, 0)
    out["big4"] = np.fmax(m[:, 4], cur_r)
    pc = full["c"].shift(1)
    tr = pd.concat([full["h"] - full["l"], (full["h"] - pc).abs(), (full["l"] - pc).abs()], axis=1).max(axis=1)
    out["atr4"] = (tr.rolling(14).mean() / full["c"]).shift(1).reindex(b).to_numpy()
    # funding acumulado (positivo = short recebe), por candle
    fc = np.zeros(len(df))
    if fund is not None and len(fund):
        k = np.searchsorted(df["t"].to_numpy() + BAR, fund["t"].to_numpy(), side="left")
        ok = (k >= 0) & (k < len(df))
        np.add.at(fc, k[ok], fund["rate"].to_numpy()[ok])
    out["fcum"] = np.cumsum(fc)
    for k in out.columns:
        out[k] = out[k].astype(np.float32) if out[k].dtype != bool else out[k]
    return int(t0), out


def cmd_prep():
    syms = {}
    files = sorted(glob.glob(str(B / "15m/*.csv.gz")))
    t = time.time()
    for n, f in enumerate(files, 1):
        s = pathlib.Path(f).name.split(".")[0]
        df = pd.read_csv(f)
        if len(df) < 2000:
            continue
        fp = B / "funding" / f"{s}.csv"
        fund = pd.read_csv(fp) if fp.exists() else None
        t0, out = prep_symbol(df, fund)
        syms[s] = (t0, out)
        if n % 100 == 0:
            print(n, "/", len(files), f"{time.time()-t:.0f}s", flush=True)
    tmin = min(v[0] for v in syms.values())
    tmax = max(v[0] + (len(v[1]) - 1) * BAR for v in syms.values())
    T = (tmax - tmin) // BAR + 1
    names = sorted(syms)
    R = np.full((T, len(names)), np.nan, np.float32)
    V = np.zeros((T, len(names)), np.float32)
    arrs, offs = {}, []
    for j, s in enumerate(names):
        t0, out = syms[s]
        o = (t0 - tmin) // BAR
        R[o:o + len(out), j] = out["ret24"].to_numpy()
        V[o:o + len(out), j] = np.nan_to_num(out["vol24"].to_numpy())
        arrs[s] = {k: out[k].to_numpy() for k in COLS}
        offs.append(o)
    with open(B / "prep.pkl", "wb") as f:
        pickle.dump({"tmin": tmin, "names": names, "offs": np.array(offs), "R": R, "V": V, "arrs": arrs}, f, protocol=4)
    print("ok", len(names), "ativos,", T, "candles")


# ---------------------------------------------------------------- simulação
@njit(cache=True)
def sim_one(h, l, c, i, tp, sl, hold):
    """Short no fechamento de i. tp/sl em fração (sl<=0: sem stop). Retorna (pnl_preço, saída, j)."""
    e = c[i]
    n = len(c)
    if i + hold >= n:
        return np.nan, -1, -1
    liq_px = e * (1 + LIQ)
    stop = e * (1 + sl) if sl > 0 else 1e30
    for k in range(i + 1, i + hold + 1):
        if h[k] >= min(liq_px, stop):
            if stop < liq_px:
                return max(-1.0, -(stop / e - 1) * LEV), 1, k  # stop
            return -1.0, 2, k  # liquidação
        if l[k] <= e * (1 - tp):
            return tp * LEV, 0, k  # alvo
    return max(-1.0, -(c[i + hold] / e - 1) * LEV), 3, i + hold  # tempo


def load():
    with open(B / "prep.pkl", "rb") as f:
        return pickle.load(f)


def ranks(P, vmin, nmax=20):
    """(t_global, j) dos nmax piores de 24h com volume >= vmin, e a posição no ranking."""
    R = np.where(P["V"] >= vmin, P["R"], np.inf)
    R = np.where(np.isnan(R), np.inf, R)
    idx = np.argpartition(R, nmax, axis=1)[:, :nmax]
    vals = np.take_along_axis(R, idx, 1)
    order = np.argsort(vals, axis=1)
    idx, vals = np.take_along_axis(idx, order, 1), np.take_along_axis(vals, order, 1)
    tt, rk = np.nonzero(np.isfinite(vals))
    return tt, idx[tt, rk], rk + 1


class Engine:
    def __init__(self, P, vmins=(50_000,)):
        self.P = P
        self.tmin = P["tmin"]
        self.cand = {}
        for vmin in vmins:
            tt, jj, rk = ranks(P, vmin)
            rows = []
            for j in np.unique(jj):
                s = P["names"][j]
                m = jj == j
                i = tt[m] - P["offs"][j]
                a = P["arrs"][s]
                ok = (i >= 0) & (i < len(a["c"])) & a["s4"][np.clip(i, 0, len(a["c"]) - 1)]
                ok &= a["s15"][np.clip(i, 0, len(a["c"]) - 1)]
                ii = i[ok]
                rows.append(pd.DataFrame({"j": j, "i": ii, "t": tt[m][ok], "rank": rk[m][ok],
                                          **{k: a[k][ii] for k in ("big4", "big15", "ord15", "dist15", "atr4")}}))
            self.cand[vmin] = pd.concat(rows).sort_values(["j", "i"]).reset_index(drop=True)

    def regimes(self):
        """Filtros de mercado (True = mercado em baixa), no grid global de 15m."""
        if hasattr(self, "_reg"):
            return self._reg
        P, T = self.P, self.P["R"].shape[0]
        def glob_c(sym):
            j = P["names"].index(sym)
            c = np.full(T, np.nan)
            a = P["arrs"][sym]["c"]
            c[P["offs"][j]:P["offs"][j] + len(a)] = a
            return pd.Series(c).ffill()
        btc, eth = glob_c("BTCUSDT"), glob_c("ETHUSDT")
        r = {}
        for nm, c in (("btc", btc), ("eth", eth)):
            r[nm + "_4h"] = (c < c.rolling(480).mean()).to_numpy()          # abaixo da MA30 do 4h
            r[nm + "_d20"] = (c < c.rolling(1920).mean()).to_numpy()        # abaixo da MA20 diária
            r[nm + "_d50"] = (c < c.rolling(4800).mean()).to_numpy()        # abaixo da MA50 diária
            r[nm + "_24h"] = (c < c.shift(96)).to_numpy()                   # caiu nas últimas 24h
            r[nm + "_7d"] = (c < c.shift(672)).to_numpy()                   # caiu nos últimos 7 dias
        r["ambos_4h"] = r["btc_4h"] & r["eth_4h"]
        r["ambos_d20"] = r["btc_d20"] & r["eth_d20"]
        r["algum_4h"] = r["btc_4h"] | r["eth_4h"]
        # amplitude: % dos ativos com retorno de 24h negativo
        R = P["R"]
        frac = np.nanmean(np.where(np.isnan(R), np.nan, R < 0), axis=1)
        r["amplitude60"] = frac > 0.6
        r["amplitude50"] = frac > 0.5
        self._reg = r
        return r

    def run(self, cfg, period=None, fee=0.0):
        c = self.cand[cfg.get("vmin", 50_000)]
        if cfg.get("regime"):
            reg = self.regimes()[cfg["regime"]]
            c = c[reg[c["t"].to_numpy()]]
        m = ((c["rank"] <= cfg.get("top", 10)) & (c["big4"].fillna(0) <= cfg.get("big4", 4))
             & (c["big15"].fillna(0) <= cfg.get("big15", 4)) & (c["dist15"] <= cfg.get("maxdist", 9)))
        if cfg.get("ord15"):
            m &= c["ord15"]
        if period:
            a, b = (pd.Timestamp(x).value // 10**6 for x in SPLITS[period])
            ts = self.tmin + c["t"].to_numpy().astype(np.int64) * BAR
            m &= (ts >= a) & (ts < b)
        c = c[m]
        tp, hold = cfg.get("tp", 0.10), int(cfg.get("hold", DAY))
        rows = []
        names, arrs = self.P["names"], self.P["arrs"]
        for j, g in c.groupby("j", sort=False):
            a = arrs[names[j]]
            free = -1
            for i, atr in zip(g["i"].to_numpy(), g["atr4"].to_numpy()):
                if i <= free:
                    continue
                slk = cfg.get("sl_atr", 0)
                sl = slk * atr if slk and np.isfinite(atr) else cfg.get("sl", 0)
                pnl, how, k = sim_one(a["h"], a["l"], a["c"], int(i), tp, sl, hold)
                if how < 0:
                    continue
                f = float(a["fcum"][k] - a["fcum"][i]) * LEV
                rows.append((i, j, max(-1.0, pnl + f - 2 * fee * LEV), how, f))
                free = k
        return pd.DataFrame(rows, columns=["i", "j", "pnl", "saida", "fund"])


def stats(t):
    if t.empty:
        return dict(n=0, media=np.nan, soma=0)
    sx = t["saida"].value_counts(normalize=True)
    return dict(n=len(t), media=round(t["pnl"].mean() * 100, 2), soma=round(t["pnl"].sum(), 1),
                pct_tp=round(sx.get(0, 0) * 100), pct_stop=round(sx.get(1, 0) * 100),
                pct_liq=round(sx.get(2, 0) * 100), pct_tempo=round(sx.get(3, 0) * 100))


BASE = dict(top=10, vmin=50_000, big4=4, big15=4, maxdist=9, ord15=0, tp=0.10, sl=0, sl_atr=0, hold=DAY)


def cmd_entry(E, out):
    grid = dict(top=[3, 5, 10, 20], vmin=list(E.cand), big4=[3, 4, 6, 99], big15=[3, 4, 6, 99],
                ord15=[0, 1], maxdist=[0.1, 0.2, 9])
    keys = list(grid)
    res = []
    t = time.time()
    for k, vals in enumerate(itertools.product(*grid.values())):
        cfg = {**BASE, **dict(zip(keys, vals))}
        st = stats(E.run(cfg, "treino"))
        res.append({**dict(zip(keys, vals)), **st})
        if k % 100 == 0:
            print(k, f"{time.time()-t:.0f}s", flush=True)
    r = pd.DataFrame(res)
    r.to_csv(out, index=False)
    print(r[r.n >= 300].sort_values("media", ascending=False).head(25).to_string(index=False))


def cmd_exit(E, entries, out):
    grid = dict(tp=[0.05, 0.075, 0.10, 0.15, 0.20], sl_atr=[0, 1, 1.5, 2], hold=[48, 96, 192])
    res = []
    for e in entries:
        for vals in itertools.product(*grid.values()):
            cfg = {**BASE, **e, **dict(zip(grid, vals))}
            res.append({**cfg, **stats(E.run(cfg, "treino"))})
    r = pd.DataFrame(res)
    r.to_csv(out, index=False)
    print(r.sort_values("media", ascending=False).head(25).to_string(index=False))


def cmd_eval(E, cfgs, fee, periods=tuple(SPLITS)):
    rows = []
    for name, cfg in cfgs.items():
        cfg = {**BASE, **cfg}
        for per in periods:
            rows.append({"config": name, "periodo": per, **stats(E.run(cfg, per, fee))})
    print(pd.DataFrame(rows).to_string(index=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["prep", "entry", "exit", "eval"])
    p.add_argument("--cfg", default=None, help='JSON {"nome": {param: valor}}')
    p.add_argument("--fee", type=float, default=0.0, help="taxa por lado em fração (0.0005 = 0,05%%)")
    p.add_argument("--periods", default="treino,validacao,teste")
    p.add_argument("--vmins", default="50000,500000,2000000")
    a = p.parse_args()
    if a.cmd == "prep":
        return cmd_prep()
    P = load()
    E = Engine(P, tuple(int(x) for x in a.vmins.split(",")))
    if a.cmd == "entry":
        cmd_entry(E, ROOT / "data/opt_entry.csv")
    elif a.cmd == "exit":
        ent = json.loads(a.cfg)
        cmd_exit(E, ent if isinstance(ent, list) else [ent], ROOT / "data/opt_exit.csv")
    else:
        cmd_eval(E, json.loads(a.cfg) if a.cfg else {"base": {}}, a.fee, a.periods.split(","))


if __name__ == "__main__":
    main()
