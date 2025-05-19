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
param = st.experimental_get_query_params().get("match_id", [None])[0]
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

# 1) See if there's already a saved analysis for this match_id
exists, analysis_id = check_analysis_exists(supabase, match_id)
if exists:
    # Pull and parse the HTML
    record = get_analysis_by_id(supabase, analysis_id)
    html   = record.get("content","")
    text   = parse_wordpress_analysis(html)

    st.subheader("🔖 Saved Analysis")
    st.text_area("Analysis Text", text, height=300)

    # Recompute DB insights
    db_insights = agents.process_database_insights(
        match_data  = get_match_with_bets(supabase, m["home_team"], m["away_team"]),
        team1_data  = data["home_team_stats"],
        team2_data  = data["away_team_stats"],
        league_data = data["league_standings"],
    )

    # Build chat context
    qc = f"{m['home_team']} vs {m['away_team']} | {m['league_name']} | {m['match_date']}"
    st.session_state.chat_context = f"""
MATCH: {qc}

SAVED ANALYSIS:
{text}

DATABASE INSIGHTS:
{db_insights}
"""

else:
    # No saved analysis → show raw info + “Analyze Match” button
    with st.expander("Raw Match Data & Details", expanded=True):
        st.json(m)

    st.header(f"{m['home_team']} vs {m['away_team']}")
    st.markdown(f"**Country:** {m['country']}")
    st.markdown(f"**League:** {m['league_name']}")
    date_str = m.get("match_date","Unknown")
    pretty  = datetime.strptime(date_str,"%Y-%m-%d").strftime("%d %B %Y") if date_str!="Unknown" else "Unknown"
    st.markdown(f"**Date:** {pretty}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(m["home_team"])
        st.json(data["home_team_stats"])
    with col2:
        st.subheader(m["away_team"])
        st.json(data["away_team_stats"])

    st.subheader("League Standings")
    st.dataframe(data["league_standings"])

    if st.button("Analyze Match"):
        with st.spinner("Running analysis…"):
            # DB insights
            db_insights = agents.process_database_insights(
                match_data  = get_match_with_bets(supabase, m["home_team"], m["away_team"]),
                team1_data  = data["home_team_stats"],
                team2_data  = data["away_team_stats"],
                league_data = data["league_standings"],
            )
            # News + synthesis
            news_insights = agents.process_football_news(
                f"{m['home_team']} vs {m['away_team']} {m['league_name']} {m['match_date']}"
            )
            combined = agents.combine_analysis_with_database(news_insights, db_insights)

            st.subheader("🔍 Comprehensive Match Analysis")
            st.markdown(combined)

            # Save back to WordPress
            match_info = {
                "match": f"{m['home_team']} vs {m['away_team']}",
                "league": m["league_name"],
                "date": datetime.strptime(m["match_date"], "%Y-%m-%d"),
            }
            results = {
                "combined_analysis": combined,
                "db_insights": db_insights,
                "news_insights": news_insights,
            }
            ok, blog_id = save_analysis_for_wordpress(supabase, match_info, results)
            if ok:
                st.sidebar.success(f"✅ Saved Analysis (ID: {blog_id})")

            # Build chat context
            qc = f"{m['home_team']} vs {m['away_team']} | {m['league_name']} | {m['match_date']}"
            st.session_state.chat_context = f"""
MATCH: {qc}

ANALYSIS:
{combined}

DATABASE INSIGHTS:
{db_insights}
"""

# --- Chat Interface ---
st.subheader("💬 Match Analysis Chatbot")
question = st.text_input("Ask a question about this match:")
if question:
    with st.spinner("Thinking…"):
        answer = agents.chat_with_analysis(
            question,
            st.session_state.chat_context,
            scraped_content = {},            # if you wish, hook in raw_news here
            chat_history    = st.session_state.chat_history,
        )
    st.session_state.chat_history.append({"role":"user",    "content":question})
    st.session_state.chat_history.append({"role":"assistant","content":answer})

# Render conversation
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
