"""Filtro de volatilidade com índice das 10 maiores criptos por valor de mercado (sem stablecoins), pesos iguais.

Não há histórico de market cap nos dados da Binance: a composição usa listas aproximadas por semestre
(top 10 por market cap no início de cada semestre, sem stablecoins). Pequeno viés de seleção possível.
Compara com o índice atual (30 maiores por volume spot).
Uso: python tools/vol_mcap.py
"""
import pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
from vol_regime import C6

TOP10 = [  # início do semestre -> membros
    ("2022-12-01", "BTC ETH BNB XRP DOGE ADA MATIC DOT LTC SOL"),
    ("2023-07-01", "BTC ETH BNB XRP SOL DOGE ADA TRX LTC MATIC"),
    ("2024-01-01", "BTC ETH BNB SOL XRP ADA AVAX DOGE TRX LINK"),
    ("2024-07-01", "BTC ETH BNB SOL XRP DOGE TON ADA TRX AVAX"),
    ("2025-01-01", "BTC ETH XRP BNB SOL DOGE ADA TRX AVAX LINK"),
    ("2025-07-01", "BTC ETH XRP BNB SOL TRX DOGE ADA HYPE LINK"),
    ("2026-01-01", "BTC ETH BNB XRP SOL TRX DOGE ADA HYPE LINK"),
]


def mcap_index(P):
    T = P["R"].shape[0]
    ts = pd.to_datetime(P["tmin"] + np.arange(T, dtype=np.int64) * opt.BAR, unit="ms")
    r = np.full(T, np.nan)
    for k, (d, mem) in enumerate(TOP10):
        a = np.searchsorted(ts.values, pd.Timestamp(d).to_datetime64())
        b = np.searchsorted(ts.values, pd.Timestamp(TOP10[k + 1][0]).to_datetime64()) if k + 1 < len(TOP10) else T
        cols = []
        for s in mem.split():
            if s + "USDT" not in P["names"]:
                print("sem dados:", s); continue
            j = P["names"].index(s + "USDT")
            c = np.full(T, np.nan); x = P["arrs"][s + "USDT"]["c"]
            c[P["offs"][j]:P["offs"][j] + len(x)] = x
            cols.append(pd.Series(c).pct_change(fill_method=None).to_numpy()[a:b])
        with np.errstate(all="ignore"):
            r[a:b] = np.nanmean(np.column_stack(cols), axis=1)
    return pd.Series(r)


def main():
    P = opt.load()
    E = opt.Engine(P, (50_000,)); E.regimes()
    off = np.array(P["offs"])
    idx = {"30 por volume": pd.Series(E.index_level).pct_change(fill_method=None), "10 por mkt cap": mcap_index(P)}
    for fee in (0, 0.0005):
        rows = []
        for top in (5, 10):
            trades = {per: E.run({**C6, "top": top}, per, fee) for per in opt.SPLITS}
            rows.append({"top": top, "filtro": "sem filtro", **{p: f"{t['pnl'].mean()*100:+.1f}% ({len(t)})" for p, t in trades.items()}})
            for nm, ret in idx.items():
                vol = ret.rolling(672).std(); med = vol.rolling(90 * 96, min_periods=45 * 96).median()
                low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
                r = {"top": top, "filtro": "vol baixa " + nm}
                for per, t in trades.items():
                    m = low[t["i"].to_numpy() + off[t["j"].to_numpy()]]
                    r[per] = f"{t['pnl'][m].mean()*100:+.1f}% ({m.sum()})"
                rows.append(r)
                if top == 5 and fee == 0:
                    print(f"{nm}: % do tempo liberado = {low[med.notna().to_numpy()].mean()*100:.0f}%")
        print(f"\n== taxa {fee} | média por trade em % da margem (n)")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
