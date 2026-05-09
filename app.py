import streamlit as st
import pandas as pd
import requests
import plotly.express as px


st.set_page_config(
    page_title="SEC Filing Intelligence Agent",
    page_icon="📄",
    layout="wide"
)


# -----------------------------
# Basic settings
# -----------------------------

SEC_HEADERS = {
    "User-Agent": "SEC Filing Intelligence Agent contact@example.com"
}


# -----------------------------
# Helper functions
# -----------------------------

@st.cache_data
def get_company_tickers():
    """
    Gets the SEC's ticker-to-CIK mapping file.

    This lets the app turn a ticker like AAPL into a CIK number.
    """
    url = "https://www.sec.gov/files/company_tickers.json"

    response = requests.get(url, headers=SEC_HEADERS, timeout=20)
    response.raise_for_status()

    data = response.json()

    companies = []

    for item in data.values():
        companies.append(
            {
                "ticker": item["ticker"].upper(),
                "title": item["title"],
                "cik": str(item["cik_str"]).zfill(10)
            }
        )

    return pd.DataFrame(companies)


@st.cache_data
def get_company_submissions(cik):
    """
    Gets recent filing history for a company from the SEC submissions API.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    response = requests.get(url, headers=SEC_HEADERS, timeout=20)
    response.raise_for_status()

    return response.json()


@st.cache_data
def get_company_facts(cik):
    """
    Gets structured financial statement facts for a company.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    response = requests.get(url, headers=SEC_HEADERS, timeout=20)
    response.raise_for_status()

    return response.json()


def find_company_by_ticker(ticker, companies_df):
    """
    Finds a company row using the stock ticker.
    """
    ticker = ticker.upper().strip()

    result = companies_df[companies_df["ticker"] == ticker]

    if result.empty:
        return None

    return result.iloc[0]


def get_recent_filings_table(submissions_json):
    """
    Turns recent SEC filings into a clean table.
    """
    recent = submissions_json["filings"]["recent"]

    filings = pd.DataFrame(
        {
            "form": recent["form"],
            "filing_date": recent["filingDate"],
            "report_date": recent["reportDate"],
            "accession_number": recent["accessionNumber"],
            "primary_document": recent["primaryDocument"]
        }
    )

    return filings


def get_latest_annual_facts(company_facts_json):
    """
    Pulls useful financial numbers from companyfacts.

    This is intentionally simple for version 1.
    """
    facts = company_facts_json.get("facts", {}).get("us-gaap", {})

    metrics_to_try = {
        "Revenue": [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet"
        ],
        "Net Income": [
            "NetIncomeLoss"
        ],
        "Total Assets": [
            "Assets"
        ],
        "Total Liabilities": [
            "Liabilities"
        ],
        "Cash": [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
        ],
        "Operating Cash Flow": [
            "NetCashProvidedByUsedInOperatingActivities"
        ]
    }

    rows = []

    for display_name, possible_tags in metrics_to_try.items():
        found_value = None
        found_year = None
        found_form = None
        found_tag = None

        for tag in possible_tags:
            if tag not in facts:
                continue

            units = facts[tag].get("units", {})

            if "USD" not in units:
                continue

            values = units["USD"]

            annual_values = [
                item for item in values
                if item.get("form") == "10-K" and item.get("fy") is not None
            ]

            if not annual_values:
                continue

            annual_values = sorted(
                annual_values,
                key=lambda x: str(x.get("filed", "")),
                reverse=True
            )

            latest = annual_values[0]

            found_value = latest.get("val")
            found_year = latest.get("fy")
            found_form = latest.get("form")
            found_tag = tag

            break

        rows.append(
            {
                "metric": display_name,
                "value": found_value,
                "fiscal_year": found_year,
                "form": found_form,
                "source_tag": found_tag
            }
        )

    return pd.DataFrame(rows)


def format_money(value):
    """
    Turns big numbers into readable dollars.
    """
    if pd.isna(value) or value is None:
        return "Not available"

    value = float(value)

    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"

    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    return f"${value:,.0f}"


def create_plain_english_summary(metrics_df, company_name):
    """
    Creates simple commentary based on the extracted numbers.
    """
    metric_lookup = {
        row["metric"]: row["value"]
        for _, row in metrics_df.iterrows()
    }

    revenue = metric_lookup.get("Revenue")
    net_income = metric_lookup.get("Net Income")
    assets = metric_lookup.get("Total Assets")
    liabilities = metric_lookup.get("Total Liabilities")
    cash = metric_lookup.get("Cash")
    operating_cash_flow = metric_lookup.get("Operating Cash Flow")

    comments = []

    comments.append(
        f"This dashboard provides a quick SEC-data snapshot for {company_name}."
    )

    if revenue is not None and not pd.isna(revenue):
        comments.append(
            f"The company reported latest annual revenue of approximately {format_money(revenue)}."
        )
    else:
        comments.append(
            "Revenue was not available from the selected SEC XBRL tags."
        )

    if net_income is not None and not pd.isna(net_income):
        if net_income > 0:
            comments.append(
                f"The company was profitable on a net income basis, reporting approximately {format_money(net_income)}."
            )
        else:
            comments.append(
                f"The company reported a net loss of approximately {format_money(net_income)}."
            )
    else:
        comments.append(
            "Net income was not available from the selected SEC XBRL tags."
        )

    if assets is not None and liabilities is not None:
        if not pd.isna(assets) and not pd.isna(liabilities) and assets != 0:
            liability_ratio = liabilities / assets

            comments.append(
                f"Total liabilities are approximately {liability_ratio:.1%} of total assets."
            )

            if liability_ratio > 0.75:
                comments.append(
                    "This suggests a relatively liability-heavy balance sheet, which may deserve further review."
                )
            elif liability_ratio > 0.5:
                comments.append(
                    "This suggests a moderate level of balance sheet leverage."
                )
            else:
                comments.append(
                    "This suggests a relatively conservative balance sheet based on liabilities versus assets."
                )

    if cash is not None and not pd.isna(cash):
        comments.append(
            f"Reported cash and cash equivalents were approximately {format_money(cash)}."
        )

    if operating_cash_flow is not None and not pd.isna(operating_cash_flow):
        if operating_cash_flow > 0:
            comments.append(
                f"Operating cash flow was positive at approximately {format_money(operating_cash_flow)}."
            )
        else:
            comments.append(
                f"Operating cash flow was negative at approximately {format_money(operating_cash_flow)}, which may require further investigation."
            )

    comments.append(
        "This is not investment advice. It is a demonstration of how SEC data can be converted into a fast analyst-style company snapshot."
    )

    return comments


# -----------------------------
# App interface
# -----------------------------

st.title("📄 SEC Filing Intelligence Agent")

st.write(
    "Enter a stock ticker to pull recent SEC filings and structured financial data from EDGAR."
)

st.caption(
    "This app uses the SEC's public EDGAR APIs for company submissions and XBRL company facts. "
    "It is for educational/demo purposes only and is not investment advice."
)

ticker_input = st.text_input(
    "Enter a US-listed stock ticker",
    value="AAPL"
)

analyze_button = st.button("Analyze Company")


if analyze_button:
    ticker = ticker_input.upper().strip()

    if ticker == "":
        st.error("Please enter a ticker.")
        st.stop()

    try:
        with st.spinner("Loading SEC company ticker database..."):
            companies_df = get_company_tickers()

        company = find_company_by_ticker(ticker, companies_df)

        if company is None:
            st.error(
                f"Ticker '{ticker}' was not found in the SEC company ticker database."
            )
            st.stop()

        company_name = company["title"]
        cik = company["cik"]

        st.success(f"Found company: {company_name}")

        col1, col2, col3 = st.columns(3)

        col1.metric("Ticker", ticker)
        col2.metric("CIK", cik)
        col3.metric("Company", company_name[:20] + "..." if len(company_name) > 20 else company_name)

        with st.spinner("Downloading recent SEC filings..."):
            submissions_json = get_company_submissions(cik)

        with st.spinner("Downloading structured financial facts..."):
            company_facts_json = get_company_facts(cik)

        # Recent filings
        filings_df = get_recent_filings_table(submissions_json)

        st.subheader("Recent SEC Filings")

        important_filings = filings_df[
            filings_df["form"].isin(["10-K", "10-Q", "8-K"])
        ].head(20)

        st.dataframe(important_filings)

        # Latest 10-K and 10-Q
        st.subheader("Latest 10-K and 10-Q")

        latest_10k = filings_df[filings_df["form"] == "10-K"].head(1)
        latest_10q = filings_df[filings_df["form"] == "10-Q"].head(1)

        col_a, col_b = st.columns(2)

        if not latest_10k.empty:
            col_a.write("Latest 10-K")
            col_a.dataframe(latest_10k)
        else:
            col_a.info("No recent 10-K found.")

        if not latest_10q.empty:
            col_b.write("Latest 10-Q")
            col_b.dataframe(latest_10q)
        else:
            col_b.info("No recent 10-Q found.")

        # Financial metrics
        st.subheader("Latest Annual Financial Snapshot")

        metrics_df = get_latest_annual_facts(company_facts_json)

        metrics_df["formatted_value"] = metrics_df["value"].apply(format_money)

        st.dataframe(
            metrics_df[
                [
                    "metric",
                    "formatted_value",
                    "fiscal_year",
                    "form",
                    "source_tag"
                ]
            ]
        )

        # Metric cards
        metric_lookup = {
            row["metric"]: row["formatted_value"]
            for _, row in metrics_df.iterrows()
        }

        col1, col2, col3 = st.columns(3)

        col1.metric("Revenue", metric_lookup.get("Revenue", "N/A"))
        col2.metric("Net Income", metric_lookup.get("Net Income", "N/A"))
        col3.metric("Cash", metric_lookup.get("Cash", "N/A"))

        col4, col5, col6 = st.columns(3)

        col4.metric("Total Assets", metric_lookup.get("Total Assets", "N/A"))
        col5.metric("Total Liabilities", metric_lookup.get("Total Liabilities", "N/A"))
        col6.metric("Operating Cash Flow", metric_lookup.get("Operating Cash Flow", "N/A"))

        # Simple chart
        st.subheader("Financial Metrics Chart")

        chart_df = metrics_df.dropna(subset=["value"])

        if not chart_df.empty:
            fig = px.bar(
                chart_df,
                x="metric",
                y="value",
                title="Latest Annual Financial Metrics"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No chartable financial metrics were available.")

        # Plain English commentary
        st.subheader("Analyst Commentary")

        comments = create_plain_english_summary(metrics_df, company_name)

        for comment in comments:
            st.write("• " + comment)

    except requests.exceptions.HTTPError as e:
        st.error("The SEC API returned an error.")
        st.code(str(e))

    except requests.exceptions.RequestException as e:
        st.error("There was a network problem while contacting the SEC API.")
        st.code(str(e))

    except Exception as e:
        st.error("Something went wrong.")
        st.code(str(e))

else:
    st.info("Enter a ticker like AAPL, MSFT, NVDA, TSLA, JPM, or AMZN, then click Analyze Company.")
