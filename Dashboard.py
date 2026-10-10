import datetime
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from streamlit import plotly_chart
import requests
import time
from streamlit_cookies_controller import CookieController
import locale

# Initialize cookie controller
controller = CookieController()
# ⚠️ Streamlit needs a tiny pause to read cookies on the very first load
time.sleep(0.2)

# --- CORRECTED USER VISIT TRACKING ---
# 1. Try to get the existing visit count from the browser cookie
visit_count = controller.get("user_visits")

# 2. Check if we have already accounted for this specific tab session
if "has_counted_this_session" not in st.session_state:
    if visit_count is None:
        # First-time visitor setup
        visit_count = 1
        controller.set("user_visits", visit_count)
        st.session_state.is_first_timer = True
    else:
        # Returning visitor logic - ONLY increment once per tab session lifecycle
        visit_count = int(visit_count) + 1
        controller.set("user_visits", visit_count)
        st.session_state.is_first_timer = False

    # Lock the counter for the rest of this session's reruns
    st.session_state.has_counted_this_session = True
    st.session_state.current_visit_number = visit_count
else:
    # On script reruns, use the cached visit number without changing the cookie
    visit_count = st.session_state.current_visit_number

# 3. Render the correct UI messages based on the locked session state
if getattr(st.session_state, "is_first_timer", False):
    st.write("### Welcome! This is your **First Time** visiting this website.")
else:
    if visit_count == 2:
        st.write("### Welcome back! This is your **2nd visit**.")
    elif visit_count == 3:
        st.write("### Great to see you again! This is your **3rd visit**.")
        st.balloons()
    else:
        st.write(f"### You are a frequent flyer! This is visit number **{visit_count}**.")
        st.balloons()

# Reset historical data cleanly
if st.button("Reset my visit history"):
    controller.remove("user_visits")
    # Also wipe out the session lock so it resets immediately
    if "has_counted_this_session" in st.session_state:
        del st.session_state.has_counted_this_session
    st.rerun()

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

# Page Configuration
st.set_page_config(page_title="FinTech: Analysing Stock Data", initial_sidebar_state="expanded", layout="wide")
st.title("FinTech: Analysing Stock Data")
st.sidebar.header("KESHAV KARTHIKEYA VALLURI")

# --- INITIALIZE STATE & COOKIES FOR RECENT SEARCHES ---
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

# Retrieve recent searches from cookie or default to empty list
cookie_searches = controller.get("recent_searches")
if "recent_searches" not in st.session_state:
    st.session_state.recent_searches = cookie_searches if isinstance(cookie_searches, list) else []


# Helper function to add a query to history safely
def add_to_recent_searches(query):
    query = query.strip()
    if not query:
        return

    # Bring query to the front if it already exists, avoiding duplication
    current_searches = [s for s in st.session_state.recent_searches if s.lower() != query.lower()]
    current_searches.insert(0, query)

    # Cap at a maximum of 5 recent items
    st.session_state.recent_searches = current_searches[:5]
    controller.set("recent_searches", st.session_state.recent_searches)


# --- CACHED DATA FETCHING FUNCTIONS ---
@st.cache_data(ttl=3600)
def fetch_stock_data(ticker, start, end):
    """Cached wrapper for yfinance historical data download."""
    data = yf.download(ticker, start=start, end=end, auto_adjust=False, multi_level_index=False)
    return data


@st.cache_data(ttl=3600)
def fetch_ticker_metadata(ticker):
    """Cached wrapper for Ticker info and actions."""
    tick = yf.Ticker(ticker)
    info = tick.info if isinstance(tick.info, dict) else {}
    actions = tick.actions
    return info, actions


# --- STEP 1: Search Form Container ---
with st.form("search_form"):
    user_typed_query = st.text_input(
        label="Type Ticker / Company Name (e.g., MSFT, AAPL, Reliance, Tata):",
        value="MSFT",
        placeholder="🔍Search For A Company"
    )
    submit_search = st.form_submit_button("Search Global Database")

# --- RECENT SEARCH PILLS / QUICK BUTTONS ---
target_search_query = None

if st.session_state.recent_searches:
    st.caption("Recent Searches (Click to re-search):")
    # Display recent queries horizontally as inline buttons
    cols = st.columns(len(st.session_state.recent_searches) + 1)

    for idx, search_item in enumerate(st.session_state.recent_searches):
        if cols[idx].button(f"🕒 {search_item}", key=f"recent_{idx}"):
            target_search_query = search_item

    # Add an option to clear recent history
    if cols[-1].button("🗑️ Clear History", key="clear_history"):
        st.session_state.recent_searches = []
        controller.remove("recent_searches")
        st.rerun()

# Determine if a user fired a raw form submission or clicked a recent search history pill
active_search = False
search_string = ""

if submit_search and len(user_typed_query) >= 2:
    active_search = True
    search_string = user_typed_query
    add_to_recent_searches(user_typed_query)
elif target_search_query:
    active_search = True
    search_string = target_search_query

# Trigger background lookup immediately upon valid event execution
if active_search:
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        params = {"q": search_string, "quotes_count": 10}

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
news = st.sidebar._link_button("Latest NEWS On YFinance", "https://finance.yahoo.com/", icon="📈")
git = st.sidebar._link_button("GitHub Code!", "https://github.com/PyCoder527/Python-Finance-Dashboard", icon= "🧑🏻‍💻")

tabs = st.tabs(["Company Info", "Raw Data", "Splits", "Dividends", "Adj. Close", "Line Chart", "Candlestick Chart", "Achievements"])

png = {
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'chart_img',
        'height': 600,
        'width': 1000,
        'scale': 2
    }
}

# Environment-safe formatting engine using built-in Python string formatting
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
        # Load data using cached functions
        data = fetch_stock_data(final_ticker, start_date, end_date)
        info, action = fetch_ticker_metadata(final_ticker)

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
                        formatted_div_yield = f"{float(raw_div_yield) * 1:.2f}%"
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

                styled_df = formatted_df.style.format({col: f"{currency_symbol}{{:.2f}}" for col in price_cols})
                st.dataframe(styled_df, use_container_width=True)

                st.download_button("Download Raw Data as CSV", data.to_csv(), file_name=f"{final_ticker}_data.csv")

            # Extract Corporate Actions securely
            splits = pd.DataFrame()
            action_div = pd.DataFrame()

            if action is not None and not action.empty:
                if "Stock Splits" in action.columns:
                    splits = action[action["Stock Splits"] > 0][["Stock Splits"]]
                if "Dividends" in action.columns:
                    action_div = action[action["Dividends"] > 0][["Dividends"]]

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

            with tabs[7]:
                if "achievements_unlocked" not in st.session_state:
                    st.session_state.achievements_unlocked = {
                        "first_step": False,
                        "A Curious Mind": False,
                        "That is Some Dedication!!": False,
                        "30 mins": False,
                        "1hr": False,
                        "visits": False,
                        "news": False,
                        "git": False,
                    }


                @st.fragment(run_every=1)  # Automatically updates ONLY this block every 1 second
                def live_achievement_tracker():
                    # 1. Calculate Elapsed Time safely
                    if "start_time" not in st.session_state:
                        st.session_state.start_time = time.time()
                    elapsed_seconds = int(time.time() - st.session_state.start_time)

                    # --- ACHIEVEMENT LOGIC (Independent IF statements) ---

                    # Achievement 1: Immediate
                    if not st.session_state.achievements_unlocked["first_step"]:
                        st.session_state.achievements_unlocked["first_step"] = True
                        st.toast("🎉 Achievement Unlocked: First Steps (App Loaded)", icon="🏆")

                    # Achievement 2: 60 seconds
                    if elapsed_seconds >= 60 and not st.session_state.achievements_unlocked["A Curious Mind"]:
                        st.session_state.achievements_unlocked["A Curious Mind"] = True
                        st.toast("🚀 Achievement Unlocked: A Curious Mind! (60s Milestone)", icon="⭐")

                    # Achievement 3: 10 minutes (600s)
                    if elapsed_seconds >= 600 and not st.session_state.achievements_unlocked[
                        "That is Some Dedication!!"]:
                        st.session_state.achievements_unlocked["That is Some Dedication!!"] = True
                        st.toast("🚀 Achievement Unlocked: That is Some Dedication!! (10 mins Milestone)", icon="🍵")

                    # Achievement 4: 30 minutes (1800s)
                    if elapsed_seconds >= 1800 and not st.session_state.achievements_unlocked["30 mins"]:
                        st.session_state.achievements_unlocked["30 mins"] = True
                        st.toast("🚀 Achievement Unlocked: Keep it Up! (30 mins Milestone)", icon="✊🏻")

                    # Achievement 5: 1 hour (3600s)
                    if elapsed_seconds >= 3600 and not st.session_state.achievements_unlocked["1hr"]:
                        st.session_state.achievements_unlocked["1hr"] = True
                        st.toast("🚀 Achievement Unlocked: Alpha Analyst (1hr Milestone)", icon="📈")

                    if visit_count == 3 and not st.session_state.achievements_unlocked["visits"]:
                        st.session_state.achievements_unlocked["visits"] = True
                        st.toast("🚀 Achievement Unlocked: A Regular Visitor!", icon="👋🏻")

                    # --- AUTOMATIC SCORE CALCULATION ---
                    # Counts how many True values exist in your session dictionary
                    achievements_gotten = sum(st.session_state.achievements_unlocked.values())
                    total_achievements = len(st.session_state.achievements_unlocked)

                    # Display Counter & Timer at the top of the tab
                    st.subheader(f"🏆 Achievements Unlocked: {achievements_gotten} / {total_achievements}")
                    st.write(f"⏱️ Time Spent In App: **{elapsed_seconds}s**")
                    st.divider()

                    # --- PERSISTENT UI BANNERS ---
                    if st.session_state.achievements_unlocked["first_step"]:
                        st.info("🎉 Achievement Unlocked: First Steps (App Loaded)", icon="🏆")

                    if st.session_state.achievements_unlocked["A Curious Mind"]:
                        st.info("🚀 Achievement Unlocked: A Curious Mind! (60s Milestone)", icon="⭐")

                    if st.session_state.achievements_unlocked["That is Some Dedication!!"]:
                        st.info("🚀 Achievement Unlocked: That is Some Dedication!! (10 mins Milestone)", icon="🍵")

                    if st.session_state.achievements_unlocked["30 mins"]:
                        st.info("🚀 Achievement Unlocked: Keep it Up! (30 mins Milestone)", icon="✊🏻")

                    if st.session_state.achievements_unlocked["1hr"]:
                        st.info("🚀 Achievement Unlocked: Alpha Analyst (1hr Milestone)", icon="📈")

                    if st.session_state.achievements_unlocked["visits"]:
                        st.info("🚀 Achievement Unlocked: A Regular Visitor!", icon="👋🏻")

                # Call the fragment inside the tab
                live_achievement_tracker()






        else:
            st.error("Error: Invalid Stock Ticker Or Date.")

    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")




