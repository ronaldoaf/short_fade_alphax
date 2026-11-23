import pandas as pd,requests,io,zipfile,os,sys
from concurrent.futures import ThreadPoolExecutor
d=pd.read_csv('/mnt/project-files/corretoras/alphax_perps_lista.csv')
syms=set(d[d.classe=='CRYPTO'].symbol)|{'XAU','WTI','CL','US100','NAS100'}
months=[f'{y}-{m:02d}' for y in (2025,2026) for m in range(1,13)][:22]
s=requests.Session()
def get(bs,mo):
    u=f'https://data.binance.vision/data/futures/um/monthly/klines/{bs}/15m/{bs}-15m-{mo}.zip'
    r=s.get(u,timeout=60)
    if r.status_code!=200: return None
    z=zipfile.ZipFile(io.BytesIO(r.content));t=z.read(z.namelist()[0]).decode()
    df=pd.read_csv(io.StringIO(t),header=None)
    if not str(df.iloc[0,0]).isdigit(): df=df.iloc[1:]
    df=df.iloc[:,[0,1,2,3,4,7]].astype(float);df.columns=['t','o','h','l','c','qv'];return df
def one(sym):
    for bs in (sym+'USDT','1000'+sym+'USDT','1000000'+sym+'USDT'):
        if get(bs,'2026-10') is None and get(bs,'2026-09') is None: continue
        with ThreadPoolExecutor(6) as ex: parts=[p for p in ex.map(lambda m:get(bs,m),months) if p is not None]
        df=pd.concat(parts).drop_duplicates('t').sort_values('t');df.to_pickle(f'raw/{sym}.pkl');return sym,bs,len(df)
    return sym,None,0
with ThreadPoolExecutor(8) as ex:
    for r in ex.map(one,sorted(syms)):
        if r[1]: print(*r,flush=True)
