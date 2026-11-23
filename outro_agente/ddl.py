import pandas as pd,requests,io,zipfile,os
from concurrent.futures import ThreadPoolExecutor
m={l.split()[0]:l.split()[1] for l in open('dl.log') if len(l.split())==3}
days=[f'2026-11-{d:02d}' for d in range(1,22)]
s=requests.Session()
def get(u):
    r=s.get(u,timeout=60)
    if r.status_code!=200: return None
    z=zipfile.ZipFile(io.BytesIO(r.content));return z.read(z.namelist()[0]).decode()
def one(sym):
    bs=m[sym];parts=[]
    for dd in days:
        t=get(f'https://data.binance.vision/data/futures/um/daily/klines/{bs}/15m/{bs}-15m-{dd}.zip')
        if t is None: continue
        df=pd.read_csv(io.StringIO(t),header=None)
        if not str(df.iloc[0,0]).isdigit(): df=df.iloc[1:]
        df=df.iloc[:,[0,1,2,3,4,7]].astype(float);df.columns=['t','o','h','l','c','qv'];parts.append(df)
    if parts:
        old=pd.read_pickle(f'raw/{sym}.pkl');pd.concat([old]+parts).drop_duplicates('t').sort_values('t').to_pickle(f'raw/{sym}.pkl')
    if os.path.exists(f'fund/{sym}.csv'):
        t=get(f'https://data.binance.vision/data/futures/um/monthly/fundingRate/{bs}/{bs}-fundingRate-2026-11.zip')
        if t is None:  # monthly not ready; fallback none
            return sym,len(parts)
        f=pd.read_csv(io.StringIO(t));pd.concat([pd.read_csv(f'fund/{sym}.csv'),f]).to_csv(f'fund/{sym}.csv',index=False)
    return sym,len(parts)
with ThreadPoolExecutor(12) as ex: r=list(ex.map(one,sorted(m)))
print(pd.Series([x[1] for x in r]).value_counts().head())
