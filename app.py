import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from data_service import (
    init_supabase,
    get_match_by_id,
    get_team_stats,
    get_league_standings,
    get_match_with_bets,
    get_country_name_by_id,
    save_analysis_for_wordpress,
    check_analysis_exists,
    get_analysis_by_id,
    parse_wordpress_analysis,
)
import agents

# Load env & configure page
load_dotenv()
st.set_page_config(
    page_title="TipsterHeroes - Football Match Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",  # ← Add this
)

# Supabase client
supabase = init_supabase(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"],
)

# Ensure session state keys
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("chat_context", "")

def fetch_match_data(match_id):
    m = get_match_by_id(supabase, match_id)
    if not m:
        st.error("Match not found!")
        return None

    # Resolve country
    existing = m.get("country")
    home_stats = get_team_stats(supabase, m["home_team"])
    away_stats = get_team_stats(supabase, m["away_team"])
    if existing and existing != "Unknown":
        country = existing
    else:
        country = get_country_name_by_id(supabase, m.get("country_id"))
        if not country or country == "Unknown Country":
            country = home_stats.get("country") or away_stats.get("country") or "Unknown"
    m["country"] = country

    # League standings
    standings = get_league_standings(supabase, m["league_name"])

    return {
        "match": m,
        "home_team_stats": home_stats,
        "away_team_stats": away_stats,
        "league_standings": standings,
    }

# Read match_id from URL
param = st.query_params.match_id
try:
    match_id = int(param) if param is not None else None
except ValueError:
    match_id = None


st.title("⚽ TipsterHeroes.AI")
st.subheader("Football Match Analysis")

if not match_id:
    st.info("❗ Provide a valid `match_id` in the URL, e.g. `?match_id=123`")
    st.stop()

# Load match details
data = fetch_match_data(match_id)
if not data:
    st.stop()
m = data["match"]

# Create Tabs
details_tab, analysis_tab, chat_tab = st.tabs([
    "📋 Match Details", "📝 Analysis", "💬 Chat"
])

# --- Tab 1: Match Details ---
with details_tab:
    with st.expander("Raw Match Data & Details", expanded=False):
        st.json(m)

    st.header(f"{m['home_team']} vs {m['away_team']}")
    date_str = m.get("match_date","Unknown")
    pretty  = datetime.strptime(date_str,"%Y-%m-%d").strftime("%d %B %Y") if date_str!="Unknown" else "Unknown"
    st.markdown(f"**Date:** {pretty}")
    st.markdown(f"**League:** {m['league_name']}")
    st.markdown(f"**Country:** {m['country']}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(m["home_team"])
        st.json(data["home_team_stats"])
    with col2:
        st.subheader(m["away_team"])
        st.json(data["away_team_stats"])

    st.subheader("League Standings")
    st.dataframe(data["league_standings"])

# --- Tab 2: Analysis ---
# --- Tab 2: Analysis ---
with analysis_tab:
    exists, analysis_id = check_analysis_exists(supabase, match_id)
    if exists:
        # Load & parse saved HTML
        record = get_analysis_by_id(supabase, analysis_id)
        html    = record.get("content", "")
        parsed  = parse_wordpress_analysis(html)

        st.subheader("🔖 Saved Analysis")
        # Show each paragraph as Markdown
        for para in parsed.split("\n\n"):
            if para.strip():
                st.markdown(para)

        # Recompute DB insights so chat has fresh context
        db_insights = agents.process_database_insights(
            match_data  = get_match_with_bets(supabase, m["home_team"], m["away_team"]),
            team1_data  = data["home_team_stats"],
            team2_data  = data["away_team_stats"],
            league_data = data["league_standings"],
        )

        qc = f"{m['home_team']} vs {m['away_team']} | {m['league_name']} | {m['match_date']}"
        st.session_state.chat_context = f"""
MATCH: {qc}

SAVED ANALYSIS:
{parsed}

DATABASE INSIGHTS:
{db_insights}
"""
    else:
        st.subheader("📝 Generate Analysis")
        if st.button("Analyze Match"):
            with st.spinner("Running analysis…"):
                # database insights
                db_insights = agents.process_database_insights(
                    match_data  = get_match_with_bets(supabase, m["home_team"], m["away_team"]),
                    team1_data  = data["home_team_stats"],
                    team2_data  = data["away_team_stats"],
                    league_data = data["league_standings"],
                )
                # news → combined
                news_insights = agents.process_football_news(
                    f"{m['home_team']} vs {m['away_team']} {m['league_name']} {m['match_date']}"
                )
                combined = agents.combine_analysis_with_database(news_insights, db_insights)

                st.markdown("### 🔍 Comprehensive Match Analysis")
                # Display combined analysis (already plain text/Markdown)
                st.markdown(combined)

                # persist to WP
                match_info = {
                    "match":  f"{m['home_team']} vs {m['away_team']}",
                    "league": m["league_name"],
                    "date":   datetime.strptime(m["match_date"], "%Y-%m-%d"),
                }
                results = {
                    "combined_analysis": combined,
                    "db_insights":       db_insights,
                    "news_insights":     news_insights,
                }
                ok, blog_id = save_analysis_for_wordpress(supabase, match_info, results)
                if ok:
                    st.sidebar.success(f"✅ Saved Analysis (ID: {blog_id})")

                # set up chat context
                qc = f"{m['home_team']} vs {m['away_team']} | {m['league_name']} | {m['match_date']}"
                st.session_state.chat_context = f"""
MATCH: {qc}

ANALYSIS:
{combined}

DATABASE INSIGHTS:
{db_insights}
"""


# --- Tab 3: Chat ---
# --- Tab 3: Chat ---
with chat_tab:
    st.subheader("💬 Match Analysis Chatbot")

    if not st.session_state.chat_context:
        st.info("Run or load an analysis first in the Analysis tab.")
    else:
        # 1) First render the full history, oldest first
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # 2) Then present the input box (which clears itself on send)
        user_prompt = st.chat_input("Ask a question about this match:")
        if user_prompt:
            # append & show the user message
            st.session_state.chat_history.append({"role":"user","content":user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            # compute & show assistant reply
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    answer = agents.chat_with_analysis(
                        user_prompt,
                        st.session_state.chat_context
                    )
                st.markdown(answer)

            # store it
            st.session_state.chat_history.append({"role":"assistant","content":answer})
