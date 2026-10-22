"""stdio MCP entrypoint. Start with: fastmcp run mutual_fund_mcp.server:mcp"""
from datetime import date
from decimal import Decimal
from pathlib import Path
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse
from mutual_fund_mcp.config import settings
from mutual_fund_mcp.mfapi_client import MFAPIClient
from mutual_fund_mcp.storage import Store
from mutual_fund_mcp.services import Service
from mutual_fund_mcp.models import Transaction, TransactionType
from mutual_fund_mcp import analytics

mcp=FastMCP("Indian Mutual Fund Analytics", instructions="Analytics only; not investment advice. MFAPI supplies scheme/NAV data, not holdings, AUM, ratings, benchmarks, taxation, or recommendations.")
svc=Service(MFAPIClient(settings.base_url),Store(settings.db_path),settings.ttl_hours,settings.risk_free_rate)

@mcp.custom_route("/", methods=["GET"])
async def landing_page(request: Request) -> HTMLResponse:
    """Serve the public landing page separately from Horizon's /mcp endpoint."""
    page = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
    return HTMLResponse(page)

def quality(navs, cached=False): return {"data_source":"MFAPI.in","nav_date_range":[navs[0].date.isoformat(),navs[-1].date.isoformat()] if navs else None,"observations":len(navs),"cache_hit":cached,"warnings":["MFAPI does not provide holdings; stock-level overlap is unavailable."]}

@mcp.tool()
async def search_schemes(query:str, limit:int=20)->list[dict]:
    """Find schemes by name/AMC/keywords. Use before analytics to obtain scheme codes."""
    if not query.strip(): raise ValueError("query is required")
    return [s.model_dump() for s in (await svc.client.search(query))[:min(limit,100)]]
@mcp.tool()
async def list_schemes(limit:int=100,offset:int=0)->list[dict]:
    """List MFAPI schemes, bounded to 1..1000."""
    if not 1<=limit<=1000 or offset<0: raise ValueError("limit must be 1..1000 and offset >= 0")
    return [s.model_dump() for s in await svc.client.list(limit,offset)]
@mcp.tool()
async def get_scheme_details(scheme_code:int)->dict:
    """Return normalized scheme metadata from MFAPI NAV history."""
    s,n,c=await svc.history(scheme_code); return {**s.model_dump(),"data_quality":quality(n,c)}
@mcp.tool()
async def get_latest_nav(scheme_code:int)->dict:
    """Return latest published NAV, not a live market price."""
    s,n=await svc.latest(scheme_code); return {"scheme":s.model_dump(),"nav":n.model_dump(mode='json'),"data_source":"MFAPI.in"}
@mcp.tool()
async def get_nav_history(scheme_code:int,start_date:date|None=None,end_date:date|None=None)->dict:
    """Return normalized NAV history. Dates are ISO dates; source DD-MM-YYYY is normalized."""
    s,n,c=await svc.history(scheme_code,start_date,end_date); return {"scheme":s.model_dump(),"nav":[x.model_dump(mode='json') for x in n],"data_quality":quality(n,c)}
@mcp.tool()
async def calculate_returns(scheme_code:int,start_date:date|None=None,end_date:date|None=None,frequency:str="daily")->dict:
    """Calculate absolute return and CAGR from NAV history; frequency is informational."""
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.returns(n),"frequency":frequency,"data_quality":quality(n,c)}
@mcp.tool()
async def calculate_rolling_returns(scheme_code:int,window:str="3Y",start_date:date|None=None,end_date:date|None=None)->dict:
    """Summarize rolling annualized returns for 1Y/3Y/5Y/10Y windows."""
    if window not in {"1Y","3Y","5Y","10Y"}: raise ValueError("window must be 1Y, 3Y, 5Y, or 10Y")
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.rolling(n,int(window[:-1])),"data_quality":quality(n,c)}
@mcp.tool()
async def calculate_risk_metrics(scheme_code:int,start_date:date|None=None,end_date:date|None=None,risk_free_rate:float|None=None)->dict:
    """Calculate volatility, downside deviation, Sharpe, Sortino, VaR, Calmar and maximum drawdown. Risk-free rate is explicit/configured."""
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.risk(n,settings.risk_free_rate if risk_free_rate is None else risk_free_rate),"data_quality":quality(n,c)}
@mcp.tool()
async def calculate_drawdowns(scheme_code:int,start_date:date|None=None,end_date:date|None=None)->dict:
    """Return the largest NAV drawdown, peak/trough and recovery if recovered."""
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.drawdowns(n),"data_quality":quality(n,c)}
@mcp.tool()
async def get_calendar_returns(scheme_code:int,start_date:date|None=None,end_date:date|None=None)->dict:
    """Return calendar-year NAV returns, including best/worst/median and positive-year ratio."""
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.calendar_returns(n),"data_quality":quality(n,c)}
@mcp.tool()
async def get_monthly_returns(scheme_code:int,start_date:date|None=None,end_date:date|None=None)->dict:
    """Return month-end NAV returns and summary statistics."""
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.calendar_returns(n,"ME"),"data_quality":quality(n,c)}
@mcp.tool()
async def analyze_consistency(scheme_code:int,window:str="1Y",start_date:date|None=None,end_date:date|None=None)->dict:
    """Measure positive months/years and best/worst rolling returns without inventing a success hurdle."""
    if window not in {"1Y","3Y","5Y","10Y"}: raise ValueError("window must be 1Y, 3Y, 5Y, or 10Y")
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.consistency(n,int(window[:-1])),"data_quality":quality(n,c)}
@mcp.tool()
async def calculate_sip(scheme_code:int,monthly_investment:float,start_date:date,end_date:date,sip_day:int=1,step_up_percent:float=0)->dict:
    """Simulate a SIP using first published NAV on/after each installment date."""
    if monthly_investment<=0 or not 1<=sip_day<=31 or step_up_percent<0: raise ValueError("positive investment, day 1..31, and non-negative step-up required")
    _,n,c=await svc.history(scheme_code,start_date,end_date); return {**analytics.sip(n,monthly_investment,start_date,end_date,sip_day,step_up_percent/100),"data_quality":quality(n,c)}
@mcp.tool()
async def calculate_lumpsum(scheme_code:int,investment_amount:float,investment_date:date,valuation_date:date|None=None)->dict:
    """Value a historical lumpsum using first NAV on/after investment date."""
    if investment_amount<=0: raise ValueError("investment_amount must be positive")
    _,n,c=await svc.history(scheme_code,investment_date,valuation_date); s=analytics.series(n); buy=s[s.index>=str(investment_date)].iloc[0]; end=s.iloc[-1]; units=investment_amount/buy; years=(s.index[-1]-s.index[0]).days/365.25
    return {"invested_amount":investment_amount,"units":units,"purchase_nav":buy,"current_value":units*end,"absolute_return":end/buy-1,"cagr":analytics.cagr(buy,end,years),"data_quality":quality(n,c)}
@mcp.tool()
async def compare_funds(scheme_codes:list[int],start_date:date|None=None,end_date:date|None=None,risk_free_rate:float|None=None)->dict:
    """Compare 2..10 funds by returns/risk; NAV levels are explicitly not rankings."""
    if not 2<=len(scheme_codes)<=10: raise ValueError("provide 2..10 scheme codes")
    results=await svc.batch_history(scheme_codes,start_date,end_date); rows=[]
    for code,r in results.items():
        if isinstance(r,Exception): rows.append({"scheme_code":code,"error":str(r)}); continue
        s,n,c=r; rows.append({"scheme_code":code,"scheme_name":s.scheme_name,**analytics.returns(n),**analytics.risk(n,risk_free_rate or settings.risk_free_rate),"data_quality":quality(n,c)})
    return {"comparison":rows,"warning":"NAV price levels are not comparable measures of performance."}
@mcp.tool()
async def add_transaction(scheme_code:int,transaction_date:date,transaction_type:TransactionType,units:Decimal,nav:Decimal,amount:Decimal,notes:str|None=None)->dict:
    """Store a local portfolio transaction. Amount and units×NAV are preserved and any discrepancy is reported."""
    t=Transaction(scheme_code=scheme_code,date=transaction_date,transaction_type=transaction_type,units=units,nav=nav,amount=amount,notes=notes); ident=svc.store.add_transaction(t); expected=units*nav
    return {"transaction_id":ident,"discrepancy":str(amount-expected),"warning":"Amount was not overwritten by units × NAV."}
@mcp.tool()
async def list_transactions()->list[dict]:
    """List locally stored portfolio transactions."""; return [x.model_dump(mode='json') for x in svc.store.list_transactions()]
@mcp.tool()
async def delete_transaction(transaction_id:int)->dict:
    """Delete one local transaction by ID."""; return {"deleted":svc.store.delete_transaction(transaction_id)}
@mcp.tool()
async def get_portfolio_value()->dict:
    """Value current local holdings using latest MFAPI NAV and calculate money-weighted XIRR."""; return await svc.portfolio_value()
@mcp.tool()
async def get_portfolio_allocation()->dict:
    """Break down current portfolio value by scheme, fund house and category; no stock-level holdings overlap is available."""
    p=await svc.portfolio_value(); groups={}
    for field in ("fund_house","category"):
        d={}
        for f in p['funds']: d[f.get(field) or "Unknown"]=d.get(f.get(field) or "Unknown",0)+f['current_value']
        groups[field]=[{"name":k,"value":v,"weight":v/p['current_value'] if p['current_value'] else 0} for k,v in d.items()]
    return {"by_scheme":p['funds'],"breakdowns":groups,"holdings_overlap":"unavailable: MFAPI does not expose holdings"}
@mcp.tool()
async def analyze_portfolio()->dict:
    """Provide valuation, concentration and explicit data boundaries for the locally stored portfolio."""
    p=await svc.portfolio_value(); weights=sorted([f['portfolio_weight'] for f in p['funds']],reverse=True)
    return {**p,"concentration":{"largest_holding":weights[0] if weights else 0,"top_3":sum(weights[:3]),"top_5":sum(weights[:5])},"limitations":["Historical portfolio risk requires dated holdings/cash-flow valuation and is not inferred from current weights.","Stock-level fund overlap is unavailable because MFAPI has no holdings data."]}
@mcp.tool()
async def refresh_scheme_data(scheme_code:int)->dict:
    """Refresh one scheme's full NAV history by expiring its cache namespace through a new fetch."""
    svc.store.clear_cache(); s,n,c=await svc.history(scheme_code); return {"scheme":s.scheme_name,"observations":len(n),"refreshed":not c}
@mcp.tool()
async def clear_cache()->dict:
    """Clear only local MFAPI cache; does not delete portfolio transactions."""; svc.store.clear_cache(); return {"cleared":True}

@mcp.prompt()
def fund_comparison_workflow() -> str: return "Search schemes first, then compare_funds with their scheme codes. Interpret returns and risk; do not recommend investments."
@mcp.prompt()
def portfolio_review_workflow() -> str: return "Add transactions, call get_portfolio_value then get_portfolio_allocation. Explain data limitations including no stock holdings overlap."


if __name__ == "__main__": mcp.run(transport="stdio")
