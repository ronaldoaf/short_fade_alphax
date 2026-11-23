import pandas as pd,numpy as np,pickle,sys
P=pickle.load(open('prep.pkl','rb'))
syms=list(P);T=P['BTC'].index
for s in syms: P[s]=P[s][~P[s].index.duplicated()].reindex(T)
def M(k): return np.column_stack([P[s][k].values for s in syms])
C,R,V,F4,F15,F15B,ATR,H,L=[M(k) for k in ['c','ret24','vol24','f4','f15','f15b','atr','h','l']]
F4=F4.astype(float)==1;F15=F15.astype(float)==1;F15B=F15B.astype(float)==1
hourly=np.where(T.minute==0)[0]
def run(N,minvol=5e4,lev=10,fee=0.0005,tp=0.10,need_b=False,hold=96):
    busy=np.zeros(len(syms),int);tr=[]
    for i in hourly:
        if i<3000 or i+hold>=len(T): continue
        r=np.where((V[i]>=minvol)&~np.isnan(R[i]),R[i],np.inf)
        cand=np.argsort(r)[:N]
        for j in cand:
            if not np.isfinite(r[j]) or busy[j]>i: continue
            ok=F4[i,j]&F15[i,j]&(F15B[i,j] if need_b else True)
            if not ok or not ATR[i,j]>0: continue
            e=C[i,j];sl=e+ATR[i,j];tpp=e*(1-tp);liq=e*(1+1/lev*0.95)
            stop=min(sl,liq);x=None
            for k in range(i+1,i+hold+1):
                if H[k,j]>=stop: x=stop;why='sl' if sl<=liq else 'liq';break
                if L[k,j]<=tpp: x=tpp;why='tp';break
            if x is None: x=C[k,j];why='tempo'
            pr=(e-x)/e*lev - 2*fee*lev
            if why=='liq': pr=-1.0
            tr.append((T[i],syms[j],R[i,j],e,x,why,pr,k-i));busy[j]=k
    return pd.DataFrame(tr,columns=['t','sym','ret24','ent','sai','motivo','pnl','barras'])
if __name__=='__main__':
    for N in (5,10):
        d=run(N);d.to_csv(f'trades_N{N}.csv',index=False);print(N,len(d),d.pnl.mean(),(d.pnl>0).mean())
