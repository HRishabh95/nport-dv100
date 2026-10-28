import pandas as pd, numpy as np, warnings, sys
warnings.filterwarnings("ignore")
from pathlib import Path
OUT=str(Path(__file__).resolve().parents[3] / 'data/interim/nport_risk_value/replication') + '/'
p=pd.read_parquet(OUT+'panel.parquet')
p['CIK']=p.CIK.str.lstrip('0')
print('all fund-quarters with IRR rows',len(p))
nav=p.NAV
base=(nav>1e6)&np.isfinite(nav)&p.DV100.notna()&(p.DV100!=0)&(p.DV100.abs()<nav)
print('NAV<=0',(nav<=0).sum(),'NAV<=1e6',(nav<=1e6).sum(),'DV100==0',(p.DV100==0).sum(),'|DV100|>=NAV',(p.DV100.abs()>=nav).sum())
p['dl']=p.debtL/nav; p['Dhat']=p.dv_est/(p.debtL*0.01)
plainh=base&p.dl.between(0.8,1.2)&(p.debtS/nav<=0.005)&(p.equity/nav<=0.05)&(p.derivN/nav<=0.10)&(p.optcnt.fillna(0)==0)&(p.debtFixed/p.debtL>=0.5)&(p.Dhat>=1)
p['ratio']=p.DV100.abs()/p.dv_est
plaus=plainh&p.ratio.between(1/3,3)
print('base',base.sum(),'plain(holdings)',plainh.sum(),'plain+plausible',plaus.sum())
mode=sys.argv[1] if len(sys.argv)>1 else 'plaus'
P=p[plaus if mode=='plaus' else plainh].copy()
print('ratio quantiles (plain holdings):',p.loc[plainh,'ratio'].quantile([.05,.25,.5,.75,.95]).round(2).tolist())
P['pos']=(P.DV100>0).astype(int)
print('MODE',mode,'n',len(P),'funds',P.FUND_KEY.nunique(),'registrants',P.CIK.nunique())
print('overall share positive %.3f'%P.pos.mean())
print('mixed-sign buckets share %.3f'%((P.npos_b>0)&(P.nneg_b>0)).mean())
bq=P.groupby('QUARTER').agg(n=('pos','size'),pos=('pos','mean'))
print(bq.round(3).to_string()); print('min %.3f max %.3f'%(bq.pos.min(),bq.pos.max()))
# registrant unanimity
g=P.groupby(['QUARTER','CIK']).pos.agg(['size','mean'])
g3=g[g['size']>=3]
un=((g3['mean']==0)|(g3['mean']==1))
print('reg-quarters >=3 plain',len(g3),'unanimous %.3f'%un.mean(),'covering funds',g3['size'].sum(),
      'unanimous pos %d neg %d'%(((g3['mean']==1)).sum(),((g3['mean']==0)).sum()))
# LOO
P=P.join(g.rename(columns={'size':'gn','mean':'gm'}),on=['QUARTER','CIK'])
P['peer_n']=P.gn-1; P['peer_pos']=P.gm*P.gn-P.pos
P['peer_neg']=P.peer_n-P.peer_pos
has=(P.peer_n>=1)&(P.peer_pos!=P.peer_neg)
pred=(P.peer_pos>P.peer_neg).astype(int)
print('LOO (>=1 peer, no tie): coverage %.3f accuracy %.3f n=%d'%(has.mean(),(pred[has]==P.pos[has]).mean(),has.sum()))
has2=(P.peer_n>=2)&(P.peer_pos!=P.peer_neg)
print('LOO (>=2 peers, no tie): coverage %.3f accuracy %.3f n=%d'%(has2.mean(),(pred[has2]==P.pos[has2]).mean(),has2.sum()))
# baseline: predict overall majority
maj=int(P.pos.mean()>0.5); print('naive majority-sign accuracy on LOO-covered %.3f'%(P.pos[has]==maj).mean())
# fund-level persistence
s=P.groupby('FUND_KEY').pos.agg(['size','mean']); s=s[s['size']>=4]
print('funds >=4 qtrs: always same sign %.3f (n=%d)'%(((s['mean']==0)|(s['mean']==1)).mean(),len(s)))
# top 15
t=P.groupby('CIK').agg(name=('REGISTRANT_NAME','last'),n=('pos','size'),pos=('pos','mean'),nq=('QUARTER','nunique'))
t['dominant']=np.where(t.pos>=0.5,'+','-'); t['share']=np.maximum(t.pos,1-t.pos)
t=t.sort_values('n',ascending=False).head(15)
print(t[['name','n','nq','dominant','share']].round(3).to_string())
# within-registrant sign switches over time
r=P.groupby(['CIK','QUARTER']).pos.mean().reset_index()
