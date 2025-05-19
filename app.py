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
st.set_page_config(page_title="TipsterHeroes - Football Match Analysis", page_icon="⚽", layout="wide")

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

    # Resolve country name if needed
    country_name = get_country_name_by_id(supabase_client, match_data.get("country_id"))
    match_data["country"] = country_name

    # Fetch stats and standings
    home_stats = get_team_stats(supabase_client, match_data["home_team"])
    away_stats = get_team_stats(supabase_client, match_data["away_team"])
    standings = get_league_standings(supabase_client, match_data["league_name"])

    return {
        "match": match_data,
        "home_team_stats": home_stats,
        "away_team_stats": away_stats,
        "league_standings": standings
    }

# Get URL parameter
match_id = st.experimental_get_query_params().get("match_id", [None])[0]

# Main UI
st.title("⚽ TipsterHeroes.AI")
st.subheader("Football Match Analysis")

if match_id:
    details = fetch_match_data(match_id)
    if details:
        # Display full details for debugging/inspection as JSON widget
        st.subheader("Raw Details (JSON)")
        st.json(details)

        # Also render full details in markdown code block
        st.subheader("Raw Details (Markdown)")
        st.markdown(f"```json\n{json.dumps(details, indent=2)}\n```")

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
else:
    st.info("Provide a valid `match_id` in the URL to load match data.")
