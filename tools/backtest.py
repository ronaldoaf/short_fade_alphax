"""Backtest da estratégia short-fade na AlphaX com dados de 15m (data/cache/15m).

Sinal avaliado no fechamento de cada candle de 15m:
  Universo : top-N piores retornos de 24h entre todos os perpétuos, volume 24h >= VOL_MIN
  4h       : preço < MA30, MA5 < MA10 < MA30, MA30 caindo (vs 10 velas de 4h atrás),
             sem candle de alta com amplitude > BIG_X vezes a média nas últimas 10 velas de 4h
  15m      : preço < MA30 e MA30 caindo (vs 10 velas atrás)
O candle de 4h em formação entra nas médias (como no app).

Execução: short 10x isolado. TP = queda de 10%; liquidação = alta de LIQ%;
saída a mercado após 24h. Se TP e liquidação caem no mesmo candle de 15m, conta liquidação.
Uma posição por ativo de cada vez; reentrada permitida após a saída.

Uso: python tools/backtest.py [--top 10] [--vol 50000] [--liq 9.5] [--big 4]
"""
import argparse, glob, pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAR = 15 * 60 * 1000
H4 = 16  # candles de 15m por candle de 4h
DAY = 96


def features(df, big_x):
    """Adiciona colunas de regra a um DataFrame de 15m de um ativo."""
    c = df["c"]
    df["ret24"] = c / c.shift(DAY) - 1
    df["vol24"] = (df["v"] * c).rolling(DAY).sum()

    # 15m
    ma30 = c.rolling(30).mean()
    df["ok15"] = (c < ma30) & (ma30 < ma30.shift(10))
    m5_15, m10_15 = c.rolling(5).mean(), c.rolling(10).mean()
    df["ord15"] = m5_15 < m10_15
    df["below10"] = c < m10_15
    rng15 = (df["h"] - df["l"]) / df["o"]
    up15 = (df["c"] > df["o"]) & (rng15 > 0) 
    df["bigup15"] = (rng15.where(up15, 0) / rng15.shift(10).rolling(30).mean()).rolling(10).max()

    # 4h a partir do 15m (blocos UTC de 4h), com a vela em formação
    b = df["t"] // (H4 * BAR)
    g = df.groupby(b)
    full = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()})
    full["rng"] = (full["h"] - full["l"]) / full["o"]
    full["bigup"] = (full["c"] > full["o"]) & (full["rng"] > big_x * full["rng"].shift(10).rolling(30).mean())
    prev = full.shift(1)  # velas de 4h já fechadas antes do bloco atual
    cs = full["c"].shift(1)
    s4, s9, s29 = (cs.rolling(n).sum() for n in (4, 9, 29))
    ma30_10ago = full["c"].rolling(30).mean().shift(10)
    big_recent = prev["bigup"].astype(float).rolling(9).max()
    m = pd.DataFrame({"s4": s4, "s9": s9, "s29": s29, "ma30_10": ma30_10ago, "big": big_recent}).reindex(b).to_numpy()
    ma5 = (m[:, 0] + c) / 5
    ma10 = (m[:, 1] + c) / 10
    ma30_4 = (m[:, 2] + c) / 30
    # vela de 4h em formação
    cur_o = g["o"].transform("first")
    cur_rng = (g["h"].cummax() - g["l"].cummin()) / cur_o
    base = full["rng"].shift(10).rolling(30).mean().reindex(b).to_numpy()
    cur_big = (c > cur_o) & (cur_rng > big_x * base)
    full["dn"] = (full["o"] - full["c"]) / full["o"] / full["rng"].shift(10).rolling(30).mean()
    dn_prev = full["dn"].shift(1).rolling(2).max().reindex(b).to_numpy()
    cur_dn = ((cur_o - c) / cur_o) / base
    df["bigdn"] = np.fmax(dn_prev, cur_dn.to_numpy())
    low20 = full["l"].shift(1).rolling(20).min().reindex(b).to_numpy()
    # tendência já existia antes: MA5<MA10<MA30 e MA30 caindo no fechamento de 2 velas de 4h atrás
    fm5, fm10, fm30 = (full["c"].rolling(n).mean() for n in (5, 10, 30))
    pre = (fm5 < fm10) & (fm10 < fm30) & (fm30 < fm30.shift(10))
    df["pre"] = pre.shift(2).reindex(b).fillna(False).to_numpy()
    df["brk"] = c < low20  # rompeu a mínima das últimas 20 velas de 4h
    df["ok4"] = (c < ma30_4) & (ma5 < ma10) & (ma10 < ma30_4) & (ma30_4 < m[:, 3]) & (m[:, 4] == 0) & ~cur_big
    return df


def simulate(df, i, liq, tp=0.10, lev=10):
    """Resultado (fração da margem) e saída para um short aberto no fechamento do candle i."""
    e = df["c"].iat[i]
    hi = df["h"].to_numpy()[i + 1:i + 1 + DAY]
    lo = df["l"].to_numpy()[i + 1:i + 1 + DAY]
    for k in range(len(hi)):
        if hi[k] >= e * (1 + liq):
            return -1.0, "liq", i + 1 + k
        if lo[k] <= e * (1 - tp):
            return 1.0, "tp", i + 1 + k
    if len(hi) < DAY:
        return None, "aberta", None
    x = df["c"].iat[i + DAY]
    return max(-1.0, -(x / e - 1) * lev), "tempo", i + DAY


def load_funding(symbol):
    f = ROOT / "data/cache/funding" / f"{symbol}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    return d if len(d) else None


def funding_pnl(fund, t0, t1, lev=10):
    """Soma do funding (fração da margem) entre abertura e saída. Rate > 0: short recebe."""
    if fund is None:
        return 0.0
    m = (fund["t"] > t0) & (fund["t"] <= t1)
    return float(fund.loc[m, "rate"].sum()) * lev


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--vol", type=float, default=50_000)
    p.add_argument("--liq", type=float, default=9.5)
    p.add_argument("--big", type=float, default=4)
    p.add_argument("--big15", type=float, default=4, help="máx. candle de alta no 15m (últimas 10 velas, x média)")
    p.add_argument("--m15", type=int, default=0, help="1: exige MA5<MA10 no 15m; 2: exige preço < MA10 no 15m")
    p.add_argument("--pre", action="store_true", help="exige tendência de queda no 4h já 2 velas antes")
    p.add_argument("--brk", type=int, default=0, help="1: só rompimento da mínima de 20 velas 4h; 2: só sem rompimento")
    p.add_argument("--bigdn", type=float, default=99, help="máx. queda de vela 4h recente (x amplitude média)")
    a = p.parse_args()

    data = {}
    for f in glob.glob(str(ROOT / "data/cache/15m/*.csv")):
        df = pd.read_csv(f)
        if len(df) < 1000:
            continue
        data[pathlib.Path(f).stem] = features(df.reset_index(drop=True), a.big)

    # ranking de 24h por timestamp
    panel = pd.concat([d[["t", "ret24", "vol24"]].assign(s=s) for s, d in data.items()])
    panel = panel.dropna()
    panel["rank"] = panel.groupby("t")["ret24"].rank(method="first")
    panel = panel[(panel["rank"] <= a.top) & (panel["vol24"] >= a.vol)]
    cand = panel.set_index(["s", "t"])["rank"]

    trades = {"regra": [], "base (só ranking)": []}
    for s, d in data.items():
        if s not in cand.index.get_level_values(0):
            continue
        fund = load_funding(s)
        ranks = cand.loc[s]
        idx = pd.Index(d["t"])
        pos = idx.get_indexer(ranks.index)
        for name in trades:
            free_at = -1
            for i, r in zip(pos, ranks.to_numpy()):
                if i <= free_at:
                    continue
                if name == "regra" and not (d["ok4"].iat[i] and d["ok15"].iat[i] and d["bigdn"].iat[i] <= a.bigdn
                                          and d["bigup15"].iat[i] <= a.big15
                                          and (not a.pre or d["pre"].iat[i])
                                          and (a.m15 == 0 or (d["ord15"].iat[i] if a.m15 == 1 else d["below10"].iat[i]))
                                          and (a.brk == 0 or (d["brk"].iat[i] == (a.brk == 1)))):
                    continue
                pnl, how, j = simulate(d, i, a.liq / 100)
                if pnl is None:
                    continue
                fp = funding_pnl(fund, d["t"].iat[i], d["t"].iat[j])
                trades[name].append({"s": s, "t": d["t"].iat[i], "rank": r, "pnl_preco": pnl,
                                     "funding": fp, "pnl": max(-1.0, pnl + fp), "saida": how,
                                     "tem_funding": fund is not None})
                free_at = j

    print(f"top={a.top} vol>={a.vol:,.0f} liq={a.liq}% big={a.big}x | "
          f"período {pd.to_datetime(panel['t'].min(), unit='ms'):%Y-%m-%d} a "
          f"{pd.to_datetime(panel['t'].max(), unit='ms'):%Y-%m-%d}")
    for name, tr in trades.items():
        t = pd.DataFrame(tr)
        if t.empty:
            print(name, "sem trades")
            continue
        sx = t["saida"].value_counts(normalize=True)
        days = (t["t"].max() - t["t"].min()) / 86_400_000 or 1
        print(f"\n== {name}: {len(t)} trades ({len(t)/days:.1f}/dia)")
        print(f"   TP {sx.get('tp',0):.0%}  liq {sx.get('liq',0):.0%}  tempo {sx.get('tempo',0):.0%}"
              f"  | resultado médio {t['pnl'].mean():+.1%} da margem  (soma {t['pnl'].sum():+.1f} margens)")
        print(f"   sem funding {t['pnl_preco'].mean():+.1%} | funding médio {t['funding'].mean():+.2%}"
              f" (pior {t['funding'].min():+.1%}) | trades com dado de funding: {t['tem_funding'].mean():.0%}")
        t["dia"] = pd.to_datetime(t["t"], unit="ms").dt.strftime("%m-%d")
        wk = t.groupby(pd.to_datetime(t["t"], unit="ms").dt.to_period("W"))["pnl"].agg(["count", "mean", "sum"])
        print(wk.round(2).to_string())
        if name == "regra":
            t.to_csv(ROOT / "data" / "backtest_trades.csv", index=False)


if __name__ == "__main__":
    main()
