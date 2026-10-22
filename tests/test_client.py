import httpx,respx,pytest
from mutual_fund_mcp.mfapi_client import MFAPIClient

@pytest.mark.asyncio
async def test_search_contract():
    async with httpx.AsyncClient() as c:
        with respx.mock:
            respx.get('https://api.mfapi.in/mf/search').mock(return_value=httpx.Response(200,json=[{'schemeCode':1,'schemeName':'Example'}]))
            out=await MFAPIClient('https://api.mfapi.in',c).search('example')
    assert out[0].scheme_code==1
