"""C6 + filtro de volatilidade, (1) só cripto no ranking e (2) alavancagem por operação conforme o ATR.

Universo: ranking dos piores de 24h com todos os perpétuos da Binance x só cripto (tools/universe.py).
Alavancagem (short isolado, liquidação em alta de 1/L - 0,5%):
  10x fixo            : regra atual
  5x se ATR > 9%      : 10x, mas 5x quando o stop de 1 ATR passaria da liquidação de 10x
  risco 50% / 70%     : L = risco / ATR (o stop de 1 ATR custa ~50% ou ~70% da margem), entre 1x e 10x
Margem igual por operação; resultados em % da margem. Como alavancagem menor reduz ganho e perda,
a comparação justa é soma / pior queda (retorno por unidade de risco).
Uso: python tools/opt_lev.py
"""
import pathlib, sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import opt
import universe
from vol_regime import C6

ALAV = {
    "10x fixo": None,
    "5x se ATR > 9%": lambda a: 10.0 if not np.isfinite(a) or a <= 0.09 else 5.0,
    "risco 50%": lambda a: 10.0 if not np.isfinite(a) else float(np.clip(0.5 / a, 1, 10)),
    "risco 70%": lambda a: 10.0 if not np.isfinite(a) else float(np.clip(0.7 / a, 1, 10)),
}


def resumo(t, P):
    if t.empty:
        return {}
    ts = pd.to_datetime(P["tmin"] + (t["i"].to_numpy() + np.array(P["offs"])[t["j"].to_numpy()]) * opt.BAR, unit="ms")
    s = pd.Series(t["pnl"].to_numpy(), index=ts).sort_index()
    eq = s.cumsum()
    dd = float((eq - eq.cummax()).min())
    mes = s.resample("MS").sum()
    sx = t["saida"].value_counts(normalize=True)
    return {"n": len(t), "média": f"{s.mean()*100:+.1f}%", "soma": round(s.sum()), "pior queda": round(dd),
            "soma/queda": round(s.sum() / -dd, 1) if dd < 0 else np.nan, "meses +": f"{(mes > 0).sum()}/{len(mes)}",
            "liq": f"{sx.get(2, 0)*100:.0f}%", "alav. média": round(t["lev"].mean(), 1) if "lev" in t else 10}


def main():
    P = opt.load()
    E_all = opt.Engine(P, (50_000,))
    E_all.regimes()
    vol = pd.Series(E_all.index_level).pct_change(fill_method=None).rolling(672).std()
    med = vol.rolling(90 * 96, min_periods=45 * 96).median()
    low = ((vol <= med) & vol.notna() & med.notna()).to_numpy()
    off = np.array(P["offs"])

    cripto = universe.mascara_binance(P)
    print(f"Binance: {len(cripto)} perpétuos, {cripto.sum()} cripto, {(~cripto).sum()} não cripto (ações/ETFs/índices)")
    R, V = P["R"].copy(), P["V"].copy()
    P["R"][:, ~cripto] = np.nan
    P["V"][:, ~cripto] = 0
    E_cr = opt.Engine(P, (50_000,))
    P["R"], P["V"] = R, V

    for fee in (0, 0.0005):
        rows = []
        for un, E in (("todos", E_all), ("só cripto", E_cr)):
            for nome, fn in ALAV.items():
                if un == "todos" and fn is not None:
                    continue
                for per in opt.SPLITS:
                    t = E.run({**C6, "levfn": fn}, per, fee)
                    t = t[low[t["i"].to_numpy() + off[t["j"].to_numpy()]]]
                    rows.append({"universo": un, "alavancagem": nome, "período": per, **resumo(t, P)})
        d = pd.DataFrame(rows)
        print(f"\n== C6 top 5 + vol baixa | taxa {fee}")
        for per in opt.SPLITS:
            print(f"\n-- {per}")
            print(d[d["período"] == per].drop(columns="período").to_string(index=False))
        d.to_csv(opt.ROOT / f"data/opt_lev_fee{fee}.csv", index=False)


if __name__ == "__main__":
    main()
