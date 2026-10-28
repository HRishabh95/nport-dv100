import pandas as pd, numpy as np, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
D=str(Path(__file__).resolve().parents[3] / 'data/interim/nport_risk_value/extract') + '/'
from pathlib import Path
OUT=str(Path(__file__).resolve().parents[3] / 'data/interim/nport_risk_value/replication') + '/'
qs=[f"{y}q{k}" for y in range(2019,2027) for k in range(1,5)]
qs=[q for q in qs if '2019q4'<=q<='2026q3']
B=['3MON','1YR','5YR','10YR','30YR']
num=lambda s: pd.to_numeric(s,errors='coerce')
rows=[]
for q in qs:
    f=pd.read_parquet(D+f'{q}_funds.parquet',columns=['ACCESSION_NUMBER','CIK','REGISTRANT_NAME','SERIES_NAME','FUND_KEY','NET_ASSETS','REPORT_DATE_D'])
    f['NAV']=num(f.NET_ASSETS)
    irr=pd.read_parquet(D+f'{q}_irr.parquet')
    cols=[f'INTRST_RATE_CHANGE_{b}_DV100' for b in B]; c01=[f'INTRST_RATE_CHANGE_{b}_DV01' for b in B]
    for c in cols+c01: irr[c]=num(irr[c]).fillna(0)
    g=irr.groupby('ACCESSION_NUMBER')
    a=pd.DataFrame({'DV100':g[cols].sum().sum(axis=1),'DV01':g[c01].sum().sum(axis=1),
        'npos_b':g[cols].apply(lambda x:(x>0).sum().sum()),'nneg_b':g[cols].apply(lambda x:(x<0).sum().sum()),
        'ncur':g.size()}).reset_index()
    h=pd.read_parquet(D+f'{q}_holdings.parquet',columns=['ACCESSION_NUMBER','HOLDING_ID','CURRENCY_VALUE','PAYOFF_PROFILE','ASSET_CAT','DERIVATIVE_CAT'])
    h=h[h.ACCESSION_NUMBER.isin(a.ACCESSION_NUMBER)]
    h['V']=num(h.CURRENCY_VALUE).fillna(0)
    ds=pd.read_parquet(D+f'{q}_DEBT_SECURITY.parquet',columns=['HOLDING_ID','MATURITY_DATE','COUPON_TYPE','ANNUALIZED_RATE'])
    h=h.merge(ds,on='HOLDING_ID',how='left')
    h=h.merge(f[['ACCESSION_NUMBER','REPORT_DATE_D']],on='ACCESSION_NUMBER',how='left')
    isder=h.DERIVATIVE_CAT.fillna('')!=''
    isdebt=h.MATURITY_DATE.notna()&~isder
    h['debtL']=np.where(isdebt&(h.PAYOFF_PROFILE=='Long'),h.V,0.)
    h['debtS']=np.where(isdebt&(h.PAYOFF_PROFILE=='Short'),h.V.abs(),0.)
    h['equity']=np.where(h.ASSET_CAT.isin(['EC','EP'])&~isder,h.V.abs(),0.)
    h['optcnt']=(h.DERIVATIVE_CAT.isin(['OPT','SWO'])).astype(int)
    # crude duration for long debt
    T=((pd.to_datetime(h.MATURITY_DATE,format='%d-%b-%Y',errors='coerce')-h.REPORT_DATE_D).dt.days/365.25).clip(0,40)
    c=(num(h.ANNUALIZED_RATE).fillna(0)/100).clip(0,0.2)
    y=np.maximum(c,0.03)  # crude yield
    # modified duration of annual-pay bond priced at yield y with coupon c
    def mdur(T,c,y):
        T=np.asarray(T,float); c=np.asarray(c,float); y=np.asarray(y,float)
        out=np.full(T.shape,np.nan)
        for i in range(len(T)):
            t=T[i]
            if not np.isfinite(t): continue
            if t<=0.0: out[i]=0.; continue
            ts=np.arange(t,0,-1.0)[::-1]
            cf=np.full(len(ts),c[i]); cf[-1]+=1
            pv=cf/(1+y[i])**ts
            out[i]=(ts*pv).sum()/pv.sum()/(1+y[i])
        return out
    fixed=h.COUPON_TYPE.isin(['Fixed','None'])
    sel=(h.debtL!=0)
    dur=np.full(len(h),np.nan)
    idx=np.where(sel&fixed)[0]
    # vectorize via rounding T to 0.25y grid
    Tg=(T.iloc[idx]*4).round()/4; cg=(c.iloc[idx]*200).round()/200
    key=pd.DataFrame({'T':Tg.values,'c':cg.values}); uk=key.drop_duplicates()
    uk['d']=mdur(uk['T'],uk['c'],np.maximum(uk['c'],0.03))
    dur[idx]=key.merge(uk,on=['T','c'],how='left')['d'].values
    fl=np.where(sel&~fixed)[0]; dur[fl]=0.25
    h['dur']=dur
    h['debtFixed']=np.where(sel&fixed,h.debtL,0.)
    h['dv']=np.where(sel,h.debtL*np.nan_to_num(h.dur)*0.01,0.)
    hg=h.groupby('ACCESSION_NUMBER').agg(debtL=('debtL','sum'),debtS=('debtS','sum'),equity=('equity','sum'),
        optcnt=('optcnt','sum'),debtFixed=('debtFixed','sum'),dv_est=('dv','sum'),nhold=('V','size')).reset_index()
    # derivative notional (futures + swaps)
    fu=pd.read_parquet(D+f'{q}_FUT_FWD_NONFOREIGNCUR_CONTRACT.parquet',columns=['HOLDING_ID','NOTIONAL_AMOUNT'])
    sw=pd.read_parquet(D+f'{q}_NONFOREIGN_EXCHANGE_SWAP.parquet',columns=['HOLDING_ID','NOTIONAL_AMOUNT'])
    dn=pd.concat([fu,sw]); dn['N']=num(dn.NOTIONAL_AMOUNT).abs().fillna(0)
    dn=dn.merge(h[['HOLDING_ID','ACCESSION_NUMBER']],on='HOLDING_ID').groupby('ACCESSION_NUMBER').N.sum().rename('derivN').reset_index()
    x=f.merge(a,on='ACCESSION_NUMBER').merge(hg,on='ACCESSION_NUMBER',how='left').merge(dn,on='ACCESSION_NUMBER',how='left')
    x['derivN']=x.derivN.fillna(0); x['QUARTER']=q
    rows.append(x.drop(columns=['NET_ASSETS'])); print(q,len(x),flush=True)
pd.concat(rows).to_parquet(OUT+'panel.parquet')
