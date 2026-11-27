"""C6 + espera de X horas após stop (e liquidação) antes de o ativo poder entrar de novo. Só cripto, vol baixa.
Uso: python tools/opt_cooldown.py"""
import pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt, universe
from vol_regime import C6


def main():
    P = opt.load(); off = np.array(P["offs"])
    E = opt.Engine(P, (50_000,)); E.regimes()
    vol = pd.Series(E.index_level).pct_change(fill_method=None).rolling(672).std()
    med = vol.rolling(8640, min_periods=4320).median()
    low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
    m = universe.mascara_binance(P); P["R"][:, ~m] = np.nan; P["V"][:, ~m] = 0
    E = opt.Engine(P, (50_000,))
    for fee in (0, 0.0005):
        rows = []
        for on, nome in (((1, 2), "stop ou liq"), ((1,), "só stop")):
            for X in (0, 4, 8, 12, 24, 48, 96):
                if X == 0 and on == (1,):
                    continue
                r = {"após": "-" if X == 0 else nome, "espera h": X}
                for per in opt.SPLITS:
                    t = E.run({**C6, "cool": X, "cool_on": on}, per, fee)
                    t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                    r[per] = f"{t['pnl'].mean()*100:+.1f}% ({len(t)})"
                    if per == "teste": r["soma teste"] = round(t["pnl"].sum())
                rows.append(r)
        print(f"\n== C6 top 5, só cripto, vol baixa, taxa {fee}"); print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
