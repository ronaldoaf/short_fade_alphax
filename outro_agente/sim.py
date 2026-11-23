import pandas as pd,numpy as np,glob,os,sys,pickle
W=96
def prep(f):
    d=pd.read_pickle(f);d['t']=pd.to_datetime(d.t,unit='ms');d=d.set_index('t').asfreq('15min')
    d['c']=d.c.ffill();
    for k in 'ohl': d[k]=d[k].fillna(d.c)
    d['qv']=d.qv.fillna(0)
    T=d.index+pd.Timedelta('15min')   # close time
    c,o,h,l=d.c,d.o,d.h,d.l
    r=pd.DataFrame(index=T)
    r['c']=c.values;r['ret24']=(c/c.shift(W)-1).values;r['vol24']=d.qv.rolling(W).sum().values
    # 15m filters
    m30=c.rolling(30).mean();rng=h-l;avg=rng.rolling(100).mean()
    big=((c>o)&(rng>4*avg)).rolling(10).max()
    r['f15']=((c<m30)&(m30<m30.shift(10))&(big==0)).values
    r['f15b']=(c.rolling(5).mean()<c.rolling(10).mean()).values
    # 4h with forming candle: at each 15m close time T, 4h candle = completed 4h candles + partial
    g=(d.index.floor('4h'))
    full=d.resample('4h').agg({'o':'first','h':'max','l':'min','c':'last'})
    po=d.o.groupby(g).transform('first');ph=d.h.groupby(g).cummax();pl=d.l.groupby(g).cummin()
    fc=full.c;fr=full.h-full.l
    # previous completed candles indexed by group start
    idx=g
    def prevroll(s,n,fn):  # stats over the n-1 completed candles before current
        return s.shift(1).rolling(n-1).agg(fn).reindex(idx).values
    s4=prevroll(fc,5,'sum');s9=prevroll(fc,10,'sum');s29=prevroll(fc,30,'sum')
    cc=c.values;ma5=(s4+cc)/5;ma10=(s9+cc)/10;ma30=(s29+cc)/30
    ma30_10=fc.rolling(30).mean().shift(10).reindex(idx).values  # MA30 10 candles back (completed)
    prng=(ph-pl).values;pgreen=(cc>po.values)
    avg4=fr.shift(1).rolling(100).mean().reindex(idx).values
    bigprev=((fc>full.o)&(fr>4*fr.rolling(100).mean())).shift(1).rolling(9).max().reindex(idx).values
    big4=(bigprev>0)|(pgreen&(prng>4*avg4))
    r['f4']=(cc<ma30)&(ma5<ma10)&(ma10<ma30)&(ma30<ma30_10)&(~big4)
    tr=pd.concat([fr,(full.h-fc.shift()).abs(),(full.l-fc.shift()).abs()],axis=1).max(axis=1)
    r['atr']=tr.ewm(alpha=1/14,adjust=False).mean().shift(1).reindex(idx).values  # ATR of completed 4h
    r['h']=h.values;r['l']=l.values
    return r
if __name__=='__main__':
    out={}
    for f in sorted(glob.glob('raw/*.pkl')):
        s=os.path.basename(f)[:-4]
        try: out[s]=prep(f)
        except Exception as e: print(s,e)
    pickle.dump(out,open('prep.pkl','wb'))
