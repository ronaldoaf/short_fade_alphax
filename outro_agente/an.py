import pandas as pd,numpy as np,glob,os
from bt import run
F={os.path.basename(f)[:-4]:pd.read_csv(f) for f in glob.glob('fund/*.csv')}
for s in F: F[s]['t']=pd.to_datetime(F[s].calc_time,unit='ms')
def fund(d,lev=10):
    out=[]
    for _,r in d.iterrows():
        f=F.get(r.sym);
        if f is None: out.append(0);continue
        a=r.t;b=a+pd.Timedelta(minutes=15*r.barras)
        out.append(f[(f.t>a)&(f.t<=b)].last_funding_rate.sum()*lev)  # short recebe funding positivo
    return np.array(out)
def stats(d,col):
    p=d[col];eq=p.cumsum();dd=(eq-eq.cummax()).min()
    # retorno por dia com $1 por operação
    return dict(n=len(p),win=round((p>0).mean()*100,1),ev_pct_margem=round(p.mean()*100,2),soma=round(p.sum(),1),maxDD=round(dd,1),
                tp=round((d.motivo=='tp').mean()*100,1),sl=round((d.motivo.isin(['sl','liq'])).mean()*100,1),tempo=round((d.motivo=='tempo').mean()*100,1))
rows=[]
for N in (5,10):
  for nb in (False,True):
    d=run(N,need_b=nb);d['fund']=fund(d);d['pnl0']=d.pnl+2*0.0005*10;d['liq']=d.pnl+d.fund;d['liq0']=d.pnl0+d.fund
    tag=f'N{N}'+('_ma5<ma10_15m' if nb else '')
    d.to_csv(f'trades_{tag}.csv',index=False)
    for per,sub in [('tudo',d),('treino_2025',d[d.t<'2026-01-01']),('teste_2026',d[d.t>='2026-01-01'])]:
      for col,lab in [('liq','taxa 0,05%/lado + funding'),('liq0','taxa 0 + funding')]:
        rows.append(dict(variante=tag,periodo=per,custos=lab,**stats(sub,col)))
r=pd.DataFrame(rows);r.to_csv('resumo.csv',index=False);print(r.to_string())
d=pd.read_csv('trades_N10.csv');print(d[d.sym.isin(['BTC','ETH','XAU','CL'])].groupby('sym').agg(n=('liq','size'),ev=('liq','mean')))
d['m']=d.t.str[:7];print(d.groupby('m').liq.agg(['size','mean','sum']).round(3).to_string())
print('funding medio por trade',d.fund.mean())
