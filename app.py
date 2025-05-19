import streamlit as st
from dotenv import load_dotenv
import json
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

# Load environment variables
load_dotenv()

# Streamlit page config
st.set_page_config(
    page_title="TipsterHeroes - Football Match Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Initialize Supabase client
supabase_client = init_supabase(
    st.secrets.get("SUPABASE_URL"),
    st.secrets.get("SUPABASE_KEY"),
)

# Helper to fetch all match-related data
def fetch_match_data(match_id):
    match_data = get_match_by_id(supabase_client, match_id)
    if not match_data:
        st.error("Match not found!")
        return None

    # Resolve country
    existing = match_data.get("country")
    home_stats = get_team_stats(supabase_client, match_data["home_team"])
    away_stats = get_team_stats(supabase_client, match_data["away_team"])
    if existing and existing != "Unknown":
        country = existing
    else:
        country = get_country_name_by_id(supabase_client, match_data.get("country_id"))
        if not country or country == "Unknown Country":
            country = home_stats.get("country") or away_stats.get("country") or "Unknown"
    match_data["country"] = country

    # Fetch standings
    standings = get_league_standings(supabase_client, match_data["league_name"])

    return {
        "match": match_data,
        "home_team_stats": home_stats,
        "away_team_stats": away_stats,
        "league_standings": standings,
    }

# Get URL param
match_id = st.query_params.get("match_id", [None])[0]
try:
    match_id = int(match_id)
except (ValueError, TypeError):
    # leave as string if not numeric
    pass

st.title("⚽ TipsterHeroes.AI")
st.subheader("Football Match Analysis")

if match_id is None:
    st.info("Provide a valid `match_id` in the URL to load match data.")
else:
    details = fetch_match_data(match_id)
    if not details:
        st.stop()

    m = details["match"]

    # 1) Check for existing WordPress analysis by match_id
    exists, analysis_id = check_analysis_exists(supabase_client, match_id)
    if exists:
        # 2) Load and parse saved HTML
        record = get_analysis_by_id(supabase_client, analysis_id)
        html = record.get("content", "")
        parsed_text = parse_wordpress_analysis(html)

        st.subheader("🔖 Saved Analysis")
        st.text(parsed_text)

        # 3) Recompute fresh DB insights for chat context
        db_insights = agents.process_database_insights(
            match_data   = get_match_with_bets(supabase_client, m["home_team"], m["away_team"]),
            team1_data   = details["home_team_stats"],
            team2_data   = details["away_team_stats"],
            league_data  = details["league_standings"],
        )

        # 4) Assemble chat context
        full_query = f"{m['home_team']} vs {m['away_team']} {m['league_name']} {m['match_date']}"
        chat_context = f"""
MATCH: {full_query}

SAVED ANALYSIS:
{parsed_text}

DATABASE INSIGHTS:
{db_insights}
"""
        st.session_state.chat_context = chat_context

    else:
        # Display match info
        with st.expander("Raw Match Data & Details", expanded=True):
            st.subheader("Match Object")
            st.json(m)

        st.header(f"{m['home_team']} vs {m['away_team']}")
        st.markdown(f"**Country:** {m.get('country','Unknown')}")
        st.markdown(f"**League:** {m.get('league_name','Unknown')}")
        raw_date = m.get("match_date")
        try:
            pretty = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d %B %Y")
        except:
            pretty = raw_date or "Unknown"
        st.markdown(f"**Date:** {pretty}")

        # Team stats
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(m["home_team"])
            st.json(details["home_team_stats"])
        with c2:
            st.subheader(m["away_team"])
            st.json(details["away_team_stats"])

        # Standings
        st.subheader("League Standings")
        st.dataframe(details["league_standings"])

        # Analysis flow
        if st.button("Analyze Match"):
            with st.spinner("Running analysis..."):
                db_insights = agents.process_database_insights(
                    match_data   = get_match_with_bets(supabase_client, m["home_team"], m["away_team"]),
                    team1_data   = details["home_team_stats"],
                    team2_data   = details["away_team_stats"],
                    league_data  = details["league_standings"],
                )
                news_insights = agents.process_football_news(
                    f"{m['home_team']} vs {m['away_team']} {m['league_name']} {raw_date}"
                )
                combined = agents.combine_analysis_with_database(news_insights, db_insights)

                st.subheader("🔍 Comprehensive Match Analysis")
                st.markdown(combined)

                # Save for WordPress
                match_info = {
                    "match": f"{m['home_team']} vs {m['away_team']}",
                    "league": m["league_name"],
                    "date": datetime.strptime(raw_date, "%Y-%m-%d") if raw_date else datetime.now(),
                }
                results = {
                    "combined_analysis": combined,
                    "db_insights": db_insights,
                    "news_insights": news_insights,
                }
                ok, blog_id = save_analysis_for_wordpress(
                    supabase_client, match_info, results
                )
                if ok:
                    st.sidebar.success(f"Analysis saved for WordPress (ID: {blog_id})")

                # Prepare chat context for new analysis
                full_query = f"{m['home_team']} vs {m['away_team']} {m['league_name']} {raw_date}"
                chat_context = f"""
MATCH: {full_query}

ANALYSIS:
{combined}

DATABASE INSIGHTS:
{db_insights}
"""
                st.session_state.chat_context = chat_context

    # --- Chatbot Interface ---
    st.subheader("💬 Match Analysis Chatbot")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    question = st.text_input("Ask a question about this match:")
    if question:
        with st.spinner("Chatbot is thinking..."):
            answer = agents.chat_with_analysis(question, st.session_state.chat_context)
            st.session_state.chat_history.append((question, answer))

    for q, a in st.session_state.chat_history:
        st.markdown(f"**You:** {q}")
        st.markdown(f"**Bot:** {a}")
