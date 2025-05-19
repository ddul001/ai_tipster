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
)
import agents

# Load environment variables
load_dotenv()

# Streamlit page config
st.set_page_config(
    page_title="TipsterHeroes - Football Match Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Supabase client
supabase_client = init_supabase(
    st.secrets.get("SUPABASE_URL"),
    st.secrets.get("SUPABASE_KEY")
)

# Helper to fetch all match-related data
def fetch_match_data(match_id):
    match_data = get_match_by_id(supabase_client, match_id)
    if not match_data:
        st.error("Match not found!")
        return None

    # Fix country: use existing 'country' if present else resolve via ID or fallback to home team country
    existing_country = match_data.get("country")
    # Fetch team stats early for fallback
    home_stats = get_team_stats(supabase_client, match_data["home_team"])
    away_stats = get_team_stats(supabase_client, match_data["away_team"])
    if existing_country and existing_country != "Unknown":
        country_name = existing_country
    else:
        country_name = get_country_name_by_id(supabase_client, match_data.get("country_id"))
        if not country_name or country_name == "Unknown Country":
            # fallback to team-level country
            country_name = home_stats.get("country") or away_stats.get("country") or "Unknown"
    match_data["country"] = country_name

    # Fetch stats and standings
    # home_stats and away_stats already fetched
    standings = get_league_standings(supabase_client, match_data["league_name"])

    return {
        "match": match_data,
        "home_team_stats": home_stats,
        "away_team_stats": away_stats,
        "league_standings": standings
    }

# Get URL parameters
details_params = st.query_params.match_id
raw_id = details_params
try:
    match_id = int(raw_id)
except (ValueError, TypeError):
    match_id = raw_id  # fallback to string if non-numeric

# Main UI
st.title("⚽ TipsterHeroes.AI")
st.subheader("Football Match Analysis")

if match_id:
    details = fetch_match_data(match_id)
    if details:
        # Show raw match-level data and full details
        with st.expander("Raw Match Data & Details", expanded=True):
            st.subheader("Match Object")
            st.json(details["match"])


        m = details["match"]
        st.header(f"{m['home_team']} vs {m['away_team']}")
        st.markdown(f"**Country:** {m.get('country', 'Unknown')}")
        st.markdown(f"**League:** {m.get('league_name', 'Unknown')}")

        # Format date
        raw_date = m.get('match_date')
        if raw_date:
            try:
                formatted = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%d %B %Y')
            except:
                formatted = raw_date
        else:
            formatted = 'Date Unavailable'
        st.markdown(f"**Date:** {formatted}")

        # Show team stats
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(m['home_team'])
            st.json(details['home_team_stats'])
        with col2:
            st.subheader(m['away_team'])
            st.json(details['away_team_stats'])

        # Display standings
        st.subheader("League Standings")
        st.dataframe(details['league_standings'])

        # Analysis button
        if st.button("Analyze Match"):
            with st.spinner("Running analysis..."):
                db_insights = agents.process_database_insights(
                    match_data=get_match_with_bets(
                        supabase_client, m['home_team'], m['away_team']
                    ),
                    team1_data=details['home_team_stats'],
                    team2_data=details['away_team_stats'],
                    league_data=details['league_standings']
                )
                news_insights = agents.process_football_news(
                    f"{m['home_team']} vs {m['away_team']} {m['league_name']} {raw_date}"
                )
                combined = agents.combine_analysis_with_database(news_insights, db_insights)
                st.subheader("Comprehensive Match Analysis")
                st.markdown(combined)

                # --- Chatbot Interface ---
                # Prepare chat context with analysis and match data
                chat_context = {
                    "match": details['match'],
                    "db_insights": db_insights,
                    "analysis": combined
                }
                if 'chat_history' not in st.session_state:
                    st.session_state.chat_history = []

                st.subheader("Match Analysis Chatbot")
                user_input = st.text_input("Ask a question about this match:")
                if user_input:
                    with st.spinner("Chatbot is thinking..."):
                        # agents.chat_with_analysis should be implemented to accept context dict
                        response = agents.chat_with_analysis(user_input, chat_context)
                        st.session_state.chat_history.append((user_input, response))

                # Display chat history
                for query, answer in st.session_state.chat_history:
                    st.markdown(f"**You:** {query}")
                    st.markdown(f"**Bot:** {answer}")

else:
    st.info("Provide a valid `match_id` in the URL to load match data.")
