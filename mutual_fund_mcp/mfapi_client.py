import logging
from datetime import date
import httpx
from mutual_fund_mcp.models import NavPoint, Scheme
logger=logging.getLogger(__name__)

class MFAPIError(RuntimeError): pass
class MFAPIClient:
    def __init__(self, base_url:str, client:httpx.AsyncClient|None=None): self.base_url=base_url.rstrip("/"); self.client=client
    async def _get(self,path,params=None):
        own=self.client is None; c=self.client or httpx.AsyncClient(timeout=20)
        try:
            r=await c.get(self.base_url+path,params=params); r.raise_for_status(); return r.json()
        except (httpx.HTTPError,ValueError) as e: raise MFAPIError(f"MFAPI request failed for {path}: {e}") from e
        finally:
            if own: await c.aclose()
    @staticmethod
    def scheme(x): return Scheme(scheme_code=x.get("scheme_code",x.get("schemeCode")),scheme_name=x.get("scheme_name",x.get("schemeName")),fund_house=x.get("fund_house",x.get("fundHouse")),scheme_type=x.get("scheme_type",x.get("schemeType")),scheme_category=x.get("scheme_category",x.get("schemeCategory")),isin_growth=x.get("isin_growth",x.get("isinGrowth")),isin_div_reinvestment=x.get("isin_div_reinvestment",x.get("isinDivReinvestment")))
    async def search(self,q): return [self.scheme(x) for x in await self._get("/mf/search",{"q":q})]
    async def list(self,limit,offset): return [self.scheme(x) for x in await self._get("/mf",{"limit":limit,"offset":offset})]
    async def history(self,code,start=None,end=None):
        params={k:v.isoformat() for k,v in {"startDate":start,"endDate":end}.items() if v}; raw=await self._get(f"/mf/{code}",params)
        return self.scheme(raw["meta"]), sorted([NavPoint(date=date.fromisoformat(x["date"][6:]+"-"+x["date"][3:5]+"-"+x["date"][:2]),nav=x["nav"]) for x in raw.get("data",[])],key=lambda x:x.date)
    async def latest(self,code):
        raw=await self._get(f"/mf/{code}/latest"); scheme, navs=self.scheme(raw["meta"]), raw.get("data",[])
        if not navs: raise MFAPIError("MFAPI returned no latest NAV")
        x=navs[0]; return scheme, NavPoint(date=date.fromisoformat(x["date"][6:]+"-"+x["date"][3:5]+"-"+x["date"][:2]),nav=x["nav"])
