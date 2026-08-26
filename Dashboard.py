import datetime
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from streamlit import plotly_chart
import requests
import locale

st.markdown(
    """
    <style>
    button[data-baseweb="tab"] {
        flex: 1 1 0%;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Headings
st.set_page_config(page_title="FinTech: Analysing Stock Data", initial_sidebar_state="expanded", layout="wide")
st.title("FinTech: Analysing Stock Data")
st.sidebar.header("KESHAV KARTHIKEYA VALLURI")

# Maintain persistent storage directory caches
if "company_directory" not in st.session_state:
    st.session_state.company_directory = {
        "MICROSOFT CORP (MSFT)": "MSFT",
        "APPLE INC (AAPL)": "AAPL",
        "TATA POWER CO LTD (TATAPOWER.NS)": "TATAPOWER.NS",
        "RELIANCE INDUSTRIES LTD (RELIANCE.NS)": "RELIANCE.NS",
        "ADANI POWER LTD. (ADANIPOWER.BO)": "ADANIPOWER.BO",
        "Amazon.com, Inc.(AMZN)": "AMZN"
    }
if "chosen_ticker" not in st.session_state:
    st.session_state.chosen_ticker = "MSFT"

# --- STEP 1: Search Form Container ---
with st.form("search_form"):
    user_typed_query = st.text_input(
        label="Type Ticker / Company Name (e.g., MSFT, AAPL, Reliance, Tata):",
        value="MSFT",
        placeholder="🔍Search For A Company"
    )
    submit_search = st.form_submit_button("Search Global Database")

# Trigger background lookup immediately upon button submission
if submit_search and len(user_typed_query) >= 2:
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        params = {"q": user_typed_query, "quotes_count": 10}

        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            payload = response.json()
            if "quotes" in payload and len(payload["quotes"]) > 0:
                fresh_discoveries = {}
                for quote in payload["quotes"]:
                    name = quote.get("shortname") or quote.get("longname") or quote.get("symbol", "")
                    symbol = quote.get("symbol", "").upper()

                    display_text = f"{name} ({symbol})"
                    fresh_discoveries[display_text] = symbol

                if fresh_discoveries:
                    st.session_state.company_directory = fresh_discoveries
                    st.rerun()
    except Exception:
        pass

# --- STEP 2: Unified Selector ---
available_options = list(st.session_state.company_directory.keys())
selected_display = st.selectbox(
    label="Choose A Company From The Directory",
    options=available_options,
    index=0
)

if selected_display:
    st.session_state.chosen_ticker = st.session_state.company_directory[selected_display]

final_ticker = st.session_state.chosen_ticker

# Sidebar Controls
st.sidebar.write("ℹ️ Help Documentation")
st.sidebar.info(
        """
        1. **Select A Company**
        2. **Select The Target Company From The Directory**
        3. **Select The Desired Date Inputs**
        4. **Change The Slider To The Desired Number (Higher Numbers Smooth Out Fluctuations)**
        """
    )

value = datetime.datetime.now()
start_date = st.sidebar.date_input("Enter The Start Date", value=datetime.date(2025, 5, 24))
end_date = st.sidebar.date_input("Enter The End Date", value=value)
slider = st.sidebar.slider("Moving Average Window", min_value=1, max_value=50, value=10)

tabs = st.tabs(["Company Info", "Raw Data", "Splits", "Dividends", "Adj. Close", "Line Chart", "Candlestick Chart"])

png = {
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'chart_img',
        'height': 600,
        'width': 1000,
        'scale': 2
    }
}


# CRITICAL FIX 2: Environment-safe formatting engine without OS-dependent locale modules
def format_market_cap(number, ticker_symbol):
    if not number or pd.isna(number):
        return "N/A"

    if ticker_symbol.endswith(".NS") or ticker_symbol.endswith(".BO"):
        # Initialize Indian locale for proper formatting
        locale.setlocale(locale.LC_ALL, 'en_IN.UTF-8')

        crore = 10_000_000
        lakh_unit = 100_000

        # 1. Check for Crore first
        if number >= crore:
            val = number / crore
            return f"₹ {locale.format_string('%.2f', val, grouping=True)} Crore"

        # 2. Check for Lakh next
        elif number >= lakh_unit:
            val = number / lakh_unit
            return f"₹ {locale.format_string('%.2f', val, grouping=True)} Lakh"

        # 3. Fallback for numbers smaller than 1 Lakh
        else:
            return f"₹ {locale.format_string('%.2f', number, grouping=True)}"



    else:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

        def format_large_currency(number):
            if number >= 1_000_000_000_000:
                val = number / 1_000_000_000_000
                return f"$ {locale.format_string('%.2f', val, grouping=True)} Trillion"

            elif number >= 1_000_000_000:
                val = number / 1_000_000_000
                return f"$ {locale.format_string('%.2f', val, grouping=True)} Billion"

            elif number >= 1_000_000:
                val = number / 1_000_000
                return f"$ {locale.format_string('%.2f', val, grouping=True)} Million"

            else:
                return f"$ {locale.format_string('%.2f', number, grouping=True)}"

        return format_large_currency(number)


# --- STEP 3: Fetch and Display Data ---
if final_ticker:
    try:
        # CRITICAL FIX 3: Force multi_level_index=False to flatten yfinance data tables instantly
        data = yf.download(final_ticker, start=start_date, end=end_date, auto_adjust=False, multi_level_index=False)
        tick = yf.Ticker(final_ticker)
        info = tick.info if isinstance(tick.info, dict) else {}

        # Safely determine currency parameters
        currency_code = info.get("currency", "USD")
        currency_symbol = "₹" if currency_code == "INR" else "$"

        if data is not None and not data.empty:
            # Flatten index safely if any leftovers exist
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Ensure all core data columns are clean 1D vectors for visual generation
            for col in ['Open', 'High', 'Low', 'Close', 'Adj Close']:
                if col in data.columns and data[col].ndim > 1:
                    data[col] = data[col].iloc[:, 0]

            # Tab 0: Company Info
            with tabs[0]:
                st.header("Company Information")

                raw_market = info.get("marketCap")
                formatted_market_cap = format_market_cap(raw_market, final_ticker)

                raw_div_yield = info.get('dividendYield')
                if raw_div_yield is not None:
                    try:
                        formatted_div_yield = f"{float(raw_div_yield) * 100:.2f}%"
                    except (ValueError, TypeError):
                        formatted_div_yield = "0.00%"
                else:
                    formatted_div_yield = "0.00%"

                company_name = info.get('longName', 'N/A')
                company_sector = info.get('sector', 'N/A')

                st.markdown(f"<h4>🏢 Name: <span style='font-weight:normal;'>{company_name}</span></h4>", unsafe_allow_html=True)
                st.markdown(f"<h4>💰 Market Cap: <span style='font-weight:normal;'>{formatted_market_cap}</span></h4>", unsafe_allow_html=True)
                st.markdown(f"<h4>📈 Dividend Yield: <span style='font-weight:normal;'>{formatted_div_yield}</span></h4>", unsafe_allow_html=True)
                st.markdown(f"<h4>🧩 Sector: <span style='font-weight:normal;'>{company_sector}</span></h4>", unsafe_allow_html=True)

            # Tab 1: Raw Data
            with tabs[1]:
                st.subheader(f"Raw Data For {final_ticker} From {start_date} To {end_date}")

                formatted_df = data.tail().copy()
                price_cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Adj Close'] if c in formatted_df.columns]

                # Format elements explicitly before calling Streamlit's container
                styled_df = formatted_df.style.format({col: f"{currency_symbol}{{:.2f}}" for col in price_cols})
                st.dataframe(styled_df, use_container_width=True)

                st.download_button("Download Raw Data as CSV", data.to_csv(), file_name=f"{final_ticker}_data.csv")

            # Extract Corporate Actions securely
            action = tick.actions
            splits = pd.DataFrame()
            action_div = pd.DataFrame()

            if action is not None and not action.empty:
                if "Stock Splits" in action.columns:
                    splits = action[action["Stock Splits"] > 0.00][["Stock Splits"]]
                if "Dividends" in action.columns:
                    action_div = action[action["Dividends"] > 0.00][["Dividends"]]

            # Tab 2: Splits
            with tabs[2]:
                if not splits.empty:
                    st.dataframe(splits, use_container_width=True)
                else:
                    st.error("No Splits Data Available")
                st.download_button("Download Splits Data as CSV", splits.to_csv(), file_name=f"{final_ticker}_splits.csv")

            # Tab 3: Dividends
            with tabs[3]:
                if not action_div.empty:
                    styled_div = action_div.style.format({"Dividends": f"{currency_symbol}{{:.2f}}"})
                    st.dataframe(styled_div, use_container_width=True)
                else:
                    st.error("No Dividends Data Available")
                st.download_button("Download Dividends Data as CSV", action_div.to_csv(), file_name=f"{final_ticker}_dividends.csv")

            # Tab 4: Adj. Close Chart
            with tabs[4]:
                st.subheader(f"Adj. Close Data For {final_ticker} From {start_date} To {end_date}")
                candle_adj = go.Figure(data=[go.Candlestick(
                    x=data.index,
                    open=data['Open'],
                    high=data['High'],
                    low=data['Low'],
                    close=data['Close']
                )])

                candle_adj.update_layout(
                    xaxis_rangeslider_visible=False,
                    template="plotly_dark",
                    yaxis=dict(title=f"Price ({currency_code})", tickprefix=currency_symbol)
                )

                if "Adj Close" in data.columns:
                    candle_adj.add_trace(go.Scatter(
                        x=data.index,
                        y=data["Adj Close"],
                        mode="lines",
                        name="Adj Close",
                        line=dict(color='#00FFCC', width=2)
                    ))
                plotly_chart(candle_adj, use_container_width=True, config=png, key="adj_close")
                st.caption("📸 **To download:** Hover over the chart and click the Camera Icon.")

            # Tab 5: Line Chart
            with tabs[5]:
                st.subheader(f"Line Chart Data For {final_ticker} From {start_date} To {end_date}")
                line = go.Figure()
                line.add_trace(go.Scatter(
                    x=data.index,
                    y=data["Close"],
                    mode="lines",
                    line=dict(color='#1591EA', width=2),
                ))
                line.update_layout(
                    xaxis_rangeslider_visible=False,
                    template="plotly_dark",
                    yaxis=dict(title=f"Price ({currency_code})", tickprefix=currency_symbol)
                )
                plotly_chart(line, use_container_width=True, config=png, key="line_close")
                st.caption("📸 **To download:** Hover over the chart and click the Camera Icon.")

            # Tab 6: Candlestick Chart
            with tabs[6]:
                st.subheader(f"Candlestick Data For {final_ticker} From {start_date} To {end_date}")
                candle = go.Figure(data=[go.Candlestick(
                    x=data.index,
                    open=data['Open'],
                    high=data['High'],
                    low=data['Low'],
                    close=data['Close'])])
                candle.update_layout(
                    xaxis_rangeslider_visible=False,
                    template="plotly_dark",
                    yaxis=dict(title=f"Price ({currency_code})", tickprefix=currency_symbol)
                )
                plotly_chart(candle, use_container_width=True, config=png, key="candle")
                st.caption("📸 To download: Hover over the chart and click the Camera Icon.")
        else:
            st.error("Error: Invalid Stock Ticker Or Date.")

    except Exception as e:
        st.error(f"An error occurred while fetching data!")