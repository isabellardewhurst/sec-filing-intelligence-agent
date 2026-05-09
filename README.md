# SEC Filing Intelligence Agent

SEC Filing Intelligence Agent is a Streamlit web app that turns SEC EDGAR company data into a fast analyst-style company snapshot.

Users enter a US-listed stock ticker, and the app retrieves company information, recent SEC filings, structured financial statement data, and plain-English commentary.

## Disclaimer

This app is for educational and portfolio demonstration purposes only. It is not financial advice.

## What the app does

- Accepts a stock ticker such as AAPL, MSFT, NVDA, TSLA, JPM, or AMZN
- Maps the ticker to the company's SEC CIK number
- Pulls recent SEC filings from EDGAR
- Displays recent 10-K, 10-Q, and 8-K filings
- Retrieves structured XBRL financial data
- Extracts revenue, net income, assets, liabilities, cash, and operating cash flow
- Displays financial metrics in tables and charts
- Generates plain-English analyst-style commentary

## Why this matters

Investment analysts, hedge funds, and financial research teams spend large amounts of time reviewing filings and extracting company fundamentals. This app demonstrates how AI-assisted tooling can turn SEC data into a faster, repeatable research workflow.

## Tech stack

- Python
- Streamlit
- pandas
- requests
- Plotly
- SEC EDGAR APIs
- GitHub
- Streamlit Community Cloud

## Example tickers

```text
AAPL
MSFT
NVDA
TSLA
JPM
AMZN
