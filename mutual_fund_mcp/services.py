import asyncio
from datetime import date
from decimal import Decimal
from mutual_fund_mcp import analytics
from mutual_fund_mcp.mfapi_client import MFAPIClient
from mutual_fund_mcp.models import Transaction
from mutual_fund_mcp.storage import Store

class Service:
    def __init__(self, client:MFAPIClient, store:Store, ttl:int, risk_free_rate:float): self.client,self.store,self.ttl,self.rf=client,store,ttl,risk_free_rate
    async def history(self,code:int,start:date|None=None,end:date|None=None):
        key=f"history:{code}:{start}:{end}"; cached=self.store.get_cache(key)
        if cached:
            from .mfapi_client import MFAPIClient
            return MFAPIClient.scheme(cached["scheme"]), [__import__('mutual_fund_mcp.models',fromlist=['NavPoint']).NavPoint(**x) for x in cached['navs']], True
        scheme, navs=await self.client.history(code,start,end)
        self.store.set_cache(key,{"scheme":scheme.model_dump(),"navs":[x.model_dump(mode='json') for x in navs]},self.ttl); return scheme,navs,False
    async def latest(self,code): return await self.client.latest(code)
    async def batch_history(self,codes,start,end):
        results=await asyncio.gather(*(self.history(c,start,end) for c in codes),return_exceptions=True)
        return {str(c): r if not isinstance(r,Exception) else r for c,r in zip(codes,results)}
    async def portfolio_value(self):
        tx=self.store.list_transactions(); by={}
        for t in tx:
            d=by.setdefault(t.scheme_code,[]); d.append(t)
        rows=[]; flows=[]
        for code, ts in by.items():
            units=sum(float(t.units)*(1 if t.transaction_type in {"BUY","SIP","SWITCH_IN"} else -1 if t.transaction_type in {"SELL","SWITCH_OUT"} else 0) for t in ts)
            invested=sum(float(t.amount)*(1 if t.transaction_type in {"BUY","SIP","SWITCH_IN"} else -1 if t.transaction_type in {"SELL","SWITCH_OUT"} else 0) for t in ts)
            scheme,nav=await self.latest(code); value=units*float(nav.nav)
            rows.append({"scheme_code":code,"scheme_name":scheme.scheme_name,"fund_house":scheme.fund_house,"category":scheme.scheme_category,"units":units,"invested_amount":invested,"average_purchase_nav":invested/units if units else None,"current_nav":float(nav.nav),"nav_date":nav.date.isoformat(),"current_value":value,"gain_loss":value-invested,"return":value/invested-1 if invested else None})
            flows += [(t.date,-float(t.amount)*(1 if t.transaction_type in {"BUY","SIP","SWITCH_IN"} else -1)) for t in ts]
        total=sum(x['current_value'] for x in rows)
        for x in rows:x['portfolio_weight']=x['current_value']/total if total else 0
        if rows: flows.append((date.today(),total))
        return {"funds":rows,"total_invested":sum(x['invested_amount'] for x in rows),"current_value":total,"unrealized_gain_loss":total-sum(x['invested_amount'] for x in rows),"absolute_return":total/sum(x['invested_amount'] for x in rows)-1 if sum(x['invested_amount'] for x in rows) else None,"xirr":analytics.xirr(flows),"warning":"XIRR uses recorded transactions and latest NAV; dividends are not reinvested unless recorded as a BUY/SIP."}
