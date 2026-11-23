import pandas as pd,requests,io,zipfile,os
from concurrent.futures import ThreadPoolExecutor
syms=set(pd.read_csv('trades_N10.csv').sym)
m={l.split()[0]:l.split()[1] for l in open('dl.log') if len(l.split())==3}
months=[f'{y}-{mm:02d}' for y in (2025,2026) for mm in range(1,13)][:22]
s=requests.Session();os.makedirs('fund',exist_ok=True)
def one(sym):
    bs=m[sym];parts=[]
    for mo in months:
        r=s.get(f'https://data.binance.vision/data/futures/um/monthly/fundingRate/{bs}/{bs}-fundingRate-{mo}.zip',timeout=60)
        if r.status_code!=200: continue
        z=zipfile.ZipFile(io.BytesIO(r.content));parts.append(pd.read_csv(z.open(z.namelist()[0])))
    if parts: pd.concat(parts).to_csv(f'fund/{sym}.csv',index=False)
with ThreadPoolExecutor(12) as ex: list(ex.map(one,sorted(syms)))
