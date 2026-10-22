from datetime import date
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field, field_validator, model_validator

class Scheme(BaseModel):
    scheme_code: int
    scheme_name: str
    fund_house: str | None = None
    scheme_type: str | None = None
    scheme_category: str | None = None
    isin_growth: str | None = None
    isin_div_reinvestment: str | None = None

class NavPoint(BaseModel):
    date: date
    nav: Decimal

    @field_validator("nav")
    @classmethod
    def positive(cls, value):
        if value <= 0: raise ValueError("NAV must be positive")
        return value

class TransactionType(StrEnum):
    BUY="BUY"; SELL="SELL"; SIP="SIP"; DIVIDEND="DIVIDEND"; SWITCH_IN="SWITCH_IN"; SWITCH_OUT="SWITCH_OUT"

class Transaction(BaseModel):
    transaction_id: int | None = None
    scheme_code: int = Field(gt=0)
    date: date
    transaction_type: TransactionType
    units: Decimal = Field(ge=0)
    nav: Decimal = Field(gt=0)
    amount: Decimal = Field(ge=0)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def nonzero(self):
        if self.units == 0 and self.amount == 0: raise ValueError("units or amount must be positive")
        return self
