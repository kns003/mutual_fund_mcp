from datetime import date
from decimal import Decimal
import numpy as np, pandas as pd

class InsufficientData(ValueError): pass
def series(points):
    if len(points)<2: raise InsufficientData("At least two valid NAV observations are required")
    return pd.Series([float(p.nav) for p in points],index=pd.to_datetime([p.date for p in points])).sort_index().groupby(level=0).last()
def cagr(start,end,years):
    if start<=0 or end<=0 or years<=0: raise InsufficientData("positive NAVs and a positive period are required")
    return (end/start)**(1/years)-1
def returns(points):
    s=series(points); yrs=(s.index[-1]-s.index[0]).days/365.25; absolute=s.iloc[-1]/s.iloc[0]-1
    return {"start_nav":round(float(s.iloc[0]),5),"end_nav":round(float(s.iloc[-1]),5),"absolute_return":absolute,"cagr":cagr(s.iloc[0],s.iloc[-1],yrs),"period_days":(s.index[-1]-s.index[0]).days,"observations":len(s)}
def risk(points,rf=0.06):
    s=series(points); r=s.pct_change().dropna(); ann=252; vol=r.std(ddof=1)*np.sqrt(ann); downside=r[r<0].std(ddof=1)*np.sqrt(ann)
    annual=(1+r).prod()**(ann/len(r))-1; dd=s/s.cummax()-1; maxdd=float(dd.min()); sharpe=(annual-rf)/vol if vol else None; sortino=(annual-rf)/downside if downside else None
    return {"annualized_return":annual,"annualized_volatility":float(vol),"downside_deviation":float(downside) if not np.isnan(downside) else None,"sharpe_ratio":sharpe,"sortino_ratio":sortino,"maximum_drawdown":maxdd,"calmar_ratio":annual/abs(maxdd) if maxdd else None,"var_95_daily":float(np.quantile(r,.05)),"assumptions":{"risk_free_rate":rf,"annualization_days":252}}
def drawdowns(points):
    s=series(points); peak=s.cummax(); dd=s/peak-1; trough=dd.idxmin(); peak_date=s.loc[:trough].idxmax(); recovered=s.loc[trough:]; rr=recovered[recovered>=s.loc[peak_date]]
    recovery=rr.index[0] if len(rr) else None
    return {"maximum_drawdown":float(dd.loc[trough]),"peak_date":peak_date.date().isoformat(),"trough_date":trough.date().isoformat(),"recovery_date":recovery.date().isoformat() if recovery is not None else None,"duration_days":(trough-peak_date).days,"recovery_days":(recovery-trough).days if recovery is not None else None}
def rolling(points,years):
    s=series(points); out=[]; days=round(years*365.25)
    for d,v in s.items():
        before=s.loc[:d-pd.Timedelta(days=days)]
        if len(before): out.append(cagr(before.iloc[-1],v,years))
    if not out: raise InsufficientData(f"Insufficient history for {years}Y rolling returns")
    a=np.array(out); return {"window_years":years,"observations":len(a),"average":float(a.mean()),"median":float(np.median(a)),"minimum":float(a.min()),"maximum":float(a.max()),"p10":float(np.quantile(a,.1)),"p90":float(np.quantile(a,.9)),"latest":float(a[-1])}
def xirr(cashflows):
    if not cashflows or not any(v<0 for _,v in cashflows) or not any(v>0 for _,v in cashflows): return None
    base=min(d for d,_ in cashflows)
    def npv(rate): return sum(v/(1+rate)**((d-base).days/365.0) for d,v in cashflows)
    lo,hi=-.9999,10.
    for _ in range(200):
        mid=(lo+hi)/2
        if npv(mid)>0: lo=mid
        else: hi=mid
    return (lo+hi)/2
def sip(points,amount,start,end,day,stepup=0):
    s=series(points); dates=pd.date_range(pd.Timestamp(start).replace(day=1),pd.Timestamp(end).replace(day=1),freq="MS"); units=0.; flows=[]
    for i,m in enumerate(dates):
        target=m.replace(day=min(day,28)); eligible=s[s.index>=target]
        if not len(eligible): continue
        instal=amount*((1+stepup)**(i//12)); nav=eligible.iloc[0]; units+=instal/nav; flows.append((eligible.index[0].date(),-instal))
    value=units*s.loc[:pd.Timestamp(end)].iloc[-1]; flows.append((min(pd.Timestamp(end),s.index[-1]).date(),value))
    invested=-sum(v for _,v in flows if v<0); return {"total_invested":invested,"installments":len(flows)-1,"units":units,"current_value":value,"gain":value-invested,"absolute_return":value/invested-1 if invested else None,"xirr":xirr(flows),"nav_rule":"first available NAV on or after each scheduled SIP date"}
def calendar_returns(points, frequency="YE"):
    s=series(points); values=s.resample(frequency).last(); r=values.pct_change().dropna()
    if not len(r): raise InsufficientData("Insufficient periods for calendar returns")
    items={d.strftime("%Y" if frequency=="YE" else "%Y-%m"):float(v) for d,v in r.items()}
    a=r.to_numpy(); return {"returns":items,"average":float(a.mean()),"median":float(np.median(a)),"best":float(a.max()),"worst":float(a.min()),"positive_ratio":float((a>0).mean())}
def consistency(points, window_years=1):
    s=series(points); monthly=s.resample("ME").last().pct_change().dropna(); yearly=s.resample("YE").last().pct_change().dropna(); roll=rolling(points,window_years)
    return {"positive_month_ratio":float((monthly>0).mean()) if len(monthly) else None,"positive_year_ratio":float((yearly>0).mean()) if len(yearly) else None,"rolling_return_success_rate":None,"worst_rolling_period":roll["minimum"],"best_rolling_period":roll["maximum"],"note":"Rolling success rate requires a caller-supplied return hurdle; it is not guessed."}
