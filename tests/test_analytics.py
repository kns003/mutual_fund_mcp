from datetime import date,timedelta
from decimal import Decimal
import pytest
from mutual_fund_mcp.models import NavPoint,Transaction,TransactionType
from mutual_fund_mcp import analytics

def navs(values): return [NavPoint(date=date(2020,1,1)+timedelta(days=i),nav=Decimal(str(v))) for i,v in enumerate(values)]
def test_returns_and_cagr():
    p=[NavPoint(date=date(2020,1,1),nav=Decimal('100')),NavPoint(date=date(2021,1,1),nav=Decimal('110'))]
    r=analytics.returns(p); assert r['absolute_return']==pytest.approx(.1); assert r['cagr']==pytest.approx(.1,rel=.01)
def test_drawdown_recovery():
    d=analytics.drawdowns(navs([100,120,90,120])); assert d['maximum_drawdown']==pytest.approx(-.25); assert d['recovery_date']
def test_risk_and_xirr():
    r=analytics.risk(navs([100,101,99,104,107])); assert r['annualized_volatility']>0
    assert analytics.xirr([(date(2020,1,1),-100),(date(2021,1,1),110)])==pytest.approx(.1,rel=.01)
def test_sip_first_available_nav():
    p=[NavPoint(date=date(2020,1,2),nav=Decimal('100')),NavPoint(date=date(2020,2,3),nav=Decimal('110'))]
    r=analytics.sip(p,1000,date(2020,1,1),date(2020,2,3),1); assert r['installments']==2; assert r['units']==pytest.approx(19.0909,rel=.001)
def test_transaction_validation():
    with pytest.raises(ValueError): Transaction(scheme_code=1,date=date.today(),transaction_type=TransactionType.BUY,units=0,nav=1,amount=0)
