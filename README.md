# Indian Mutual Fund Analytics MCP

MCP server for research and calculations using [MFAPI's documented OpenAPI contract](https://www.mfapi.in/docs/openapi.json). It runs locally over stdio and can be deployed to Horizon over Streamable HTTP. It is an analytics tool, not investment advice.

## Install and run

```bash
cd mutual_fund_mcp
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env  # adjust paths/risk-free rate if needed
fastmcp run mutual_fund_mcp.server:mcp
pytest
```

## Deploy to Horizon

Set the Horizon server entrypoint to:

```text
horizon_entrypoint.py:mcp
```

The root-level entrypoint imports the server through its package, so FastMCP's
file-based inspection can resolve the `mutual_fund_mcp` package during Horizon's
build. The default SQLite path is `/tmp/mutual_fund.db` because the application
directory is read-only at runtime. `/tmp` is temporary instance storage; use
`CACHE_DB_PATH` with a persistent writable volume if portfolio transactions
must survive restarts or be shared across instances.

Claude Desktop/MCP client configuration:

```json
{"mcpServers":{"mutual-fund-analytics":{"command":"/absolute/path/mutual_fund_mcp/.venv/bin/python","args":["-m","mutual_fund_mcp.server"],"cwd":"/absolute/path/mutual_fund_mcp"}}}
```

## Architecture

`mfapi_client.py` is the only external-data layer. `analytics.py` is pure calculation code, `storage.py` owns SQLite cache/portfolio tables, `services.py` composes operations, and `server.py` is the MCP boundary. SQLite stores NAV response cache and local transactions; it never transmits the latter.

## Tool catalogue

- Discovery/data: `search_schemes`, `list_schemes`, `get_scheme_details`, `get_latest_nav`, `get_nav_history`, `refresh_scheme_data`, `clear_cache`.
- Analytics: `calculate_returns`, `calculate_rolling_returns`, `calculate_risk_metrics`, `calculate_drawdowns`, `calculate_sip`, `calculate_lumpsum`, `compare_funds`.
- Portfolio: `add_transaction`, `list_transactions`, `delete_transaction`, `get_portfolio_value`, `get_portfolio_allocation`.

Examples: “Find HDFC flexicap funds”; “Calculate the 5-year CAGR of scheme 122639”; “Compare these scheme codes over five years”; “If I invested ₹10,000 monthly, what is the simulated value?”

## Methodology and limitations

MFAPI only exposes schemes and NAV/metadata. Its history endpoint uses `startDate`/`endDate` ISO query parameters and returns DD-MM-YYYY NAV dates, which are normalized internally. CAGR uses actual elapsed days/365.25. Volatility/Sharpe/Sortino annualize daily NAV returns by 252; the risk-free rate comes from `RISK_FREE_RATE` or the explicit tool parameter. SIP buys at the first published NAV on or after each scheduled date. XIRR is money-weighted and belongs to multi-cash-flow investment/portfolio analysis; it is not CAGR.

NAV is not a price ranking signal. MFAPI does not provide holdings, benchmarks, AUM, expenses, ratings, fund managers, tax, or exit-load data. Consequently stock-level fund overlap and benchmark analytics are explicitly unavailable. Portfolio historical risk is not fabricated from today's holdings.

## Data quality, cache, and testing

Analytics return source, observation count, NAV range, cache state, and assumptions. Cache TTL/default path are configured through `.env.example`; `clear_cache` only clears cached remote data. Tests use deterministic NAV series/mocked HTTP and do not call MFAPI. The analytics services are transport-independent and are exposed through FastMCP over local stdio or Horizon HTTP.
