import streamlit as st
from dotenv import load_dotenv
from datetime import datetime
from data_service import (
    init_supabase,
    get_match_by_id,
    get_team_stats,
    get_league_standings,
    get_match_with_bets,
)
import agents

# Load environment variables
load_dotenv()

# Streamlit page config
st.set_page_config(page_title="TipsterHeroes - Football Match Analysis", page_icon="⚽", layout="wide")

# Initialize Supabase
supabase_client = init_supabase(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Utility to fetch match-related data from DB
def fetch_match_data(match_id):
    match_data = get_match_by_id(supabase_client, match_id)
    if not match_data:
        st.error("Match not found!")
        return None

    # Resolve country name
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

# Extract URL parameters
query_params = st.query_params
match_id = query_params.get("match_id", [None])[0]

# Main UI
st.title("⚽ TipsterHeroes.AI")
st.subheader("Football Match Analysis")

if match_id:
    match_details = fetch_match_data(match_id)

    if match_details:
        match_info = match_details["match"]

        st.header(f"{match_info['home_team']} vs {match_info['away_team']}")
        st.markdown(f"**Country:** {match_info.get('country', 'Unknown')}")
        st.markdown(f"**League:** {match_info.get('league_name', 'Unknown')}")

        # Gracefully handle unknown dates
        match_date = match_info.get('match_date')
        if match_date:
            formatted_date = datetime.strptime(match_date, '%Y-%m-%d').strftime('%d %B %Y')
        else:
            formatted_date = 'Date Unavailable'
        st.markdown(f"**Date:** {formatted_date}")

        # Only display match details once here clearly
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(match_info['home_team'])
            st.json(match_details['home_team_stats'])

        with col2:
            st.subheader(match_info['away_team'])
            st.json(match_details['away_team_stats'])

        st.subheader("League Standings")
        st.dataframe(match_details['league_standings'])

        if st.button("Analyze Match"):
            with st.status("Running full analysis...", expanded=True):
                db_insights = agents.process_database_insights(
                    match_data=get_match_with_bets(supabase_client, match_info['home_team'], match_info['away_team']),
                    team1_data=match_details['home_team_stats'],
                    team2_data=match_details['away_team_stats'],
                    league_data=match_details['league_standings']
                )

                news_insights = agents.process_football_news(
                    f"{match_info['home_team']} vs {match_info['away_team']} {match_info['league_name']} {formatted_date}"
                )

                combined_analysis = agents.combine_analysis_with_database(news_insights, db_insights)

                st.subheader("Comprehensive Match Analysis")
                st.markdown(combined_analysis)

else:
    st.info("Please provide a valid `match_id` in the URL.")
