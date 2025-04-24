"""
Main application file for TipsterHeroes.AI - Football Match Analysis
Handles UI components and orchestrates the workflow between agents and data services.
"""

import os
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
import json
import traceback

# Import from local modules
import agents
from data_service import (
    add_analysis_message, check_analysis_exists, get_analysis_by_id, init_supabase, initialize_memory, save_analysis_for_wordpress, setup_chat_with_context, setup_embedchain,
    save_chat_to_memory, get_relevant_memories, get_all_memories,
    get_matches, get_team_stats, get_match_by_teams, get_head_to_head,
    get_league_standings 
)

# Load environment variables
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="TipsterHeroes - AI Football Analysis",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ TipsterHeroes.AI - Football Match Analysis")
st.markdown("AI-powered football news analysis for match predictions and betting insights")

# Initialize session states
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "chat_bot" not in st.session_state:
    st.session_state.chat_bot = None

# Function to generate analysis
def generate_analysis(home_team, away_team, league, match_date):
    """Generate analysis for the specified match"""
    try:
        match_details = f"{home_team} vs {away_team}"
        full_query = f"{match_details} {league} {match_date.strftime('%d %B %Y')}"

         # Check if analysis already exists
        if supabase_client:
            exists, analysis_id = check_analysis_exists(supabase_client, home_team, away_team, match_date)
            if exists:
                st.warning(f"Analysis already exists for this match (ID: {analysis_id})")
                # Load existing analysis into session state
                analysis_data = get_analysis_by_id(supabase_client, analysis_id)
                if analysis_data:
                    st.success("Loaded existing analysis")
                    # Convert stored analysis to results format
                    results = {
                        "combined_analysis": analysis_data.get("content", ""),
                        "enhanced_analysis": analysis_data.get("content", ""),
                        "initial_analysis": "Loaded from database",
                        "synthesized_news": "Loaded from database",
                        "raw_news": "Loaded from database"
                    }
                    
                    # Store results in session state
                    st.session_state.results = results
                    st.session_state.match_info = {
                        "match": match_details,
                        "league": league,
                        "date": match_date
                    }
                    return
        
        # Initialize the result container
        results = {}
        
        # Flag to track if we need to run news analysis
        run_news_analysis = use_news
        
        # Flag to track if we need database analysis
        run_db_analysis = use_database and supabase_client
        
        # Database analysis
        db_insights = None
        if run_db_analysis:
            with st.status("Processing database information...", expanded=True) as status:
                status.write("🔍 Retrieving match data...")
                
                # Get match data
                match_data = get_match_by_teams(supabase_client, home_team, away_team, closest_to_date=match_date)
                
                if not match_data:
                    # Create a basic match data structure if not found
                    match_data = {
                        'home_team': home_team,
                        'away_team': away_team,
                        'match_date': match_date.strftime('%Y-%m-%d'),
                        'league_name': league
                    }
                
                # Get team statistics
                status.write("📊 Retrieving team statistics...")
                team1_data = get_team_stats(supabase_client, home_team)
                team2_data = get_team_stats(supabase_client, away_team)
                
                # Get head-to-head data
                status.write("🏆 Retrieving head-to-head history...")
                h2h_data = get_head_to_head(supabase_client, home_team, away_team)
                
                # Get league standings
                status.write("🏆 Retrieving league standings...")
                league_data = get_league_standings(supabase_client, league)
                
                # Generate database insights
                status.write("🧠 Analyzing database information...")
                db_insights = agents.process_database_insights(
                    match_data, 
                    team1_data or {"team_name": home_team, "note": "Limited statistics available"}, 
                    team2_data or {"team_name": away_team, "note": "Limited statistics available"},
                    h2h_data,
                    league_data
                )
                
                status.update(label="Database analysis complete!", state="complete")
        
        # News-based analysis
        if run_news_analysis:
            results = agents.process_football_news(full_query)
        
        # Combine analyses if both are available
        if run_news_analysis and run_db_analysis and db_insights:
            combined_analysis = agents.combine_analysis_with_database(results, db_insights)
            results["combined_analysis"] = combined_analysis
            results["db_insights"] = db_insights
        elif db_insights:
            # Only database analysis available
            results["db_insights"] = db_insights
            results["enhanced_analysis"] = db_insights  # Use db_insights as the main analysis
            results["initial_analysis"] = "Analysis based on database statistics only."
            results["synthesized_news"] = "No news analysis performed."
            results["raw_news"] = "No news search performed."
            results["combined_analysis"] = db_insights
        
        # Store results in session state
        st.session_state.results = results
        st.session_state.match_info = {
            "match": match_details,
            "league": league,
            "date": match_date
        }

        # Save analysis to WordPress format in Supabase if connected
        if supabase_client:
            save_success, blog_id = save_analysis_for_wordpress(supabase_client, st.session_state.match_info, results)
            if save_success:
                st.sidebar.success(f"Analysis saved for WordPress (ID: {blog_id})", icon="✅")
        
        
        # Reset chat history for new analysis
        st.session_state.chat_history = []
        
        # Initialize chat bot if using Embedchain
        if chat_method == "Embedchain" and openai_api_key:
            # Determine which analysis to use for context
            if "combined_analysis" in results:
                analysis_for_context = results["combined_analysis"]
            else:
                analysis_for_context = results.get("enhanced_analysis", "")
            
            # Combine all analysis components for context
            full_analysis = f"""
            MATCH: {full_query}
            
            ANALYSIS:
            {analysis_for_context}
            """
            
            # Add database insights if available
            if "db_insights" in results:
                full_analysis += f"""
                
                DATABASE INSIGHTS:
                {results['db_insights']}
                """
            
            st.session_state.chat_bot = setup_embedchain(openai_api_key, full_analysis)
            st.session_state.chat_context = full_analysis
        else:
            # Determine which analysis to use for context
            if "combined_analysis" in results:
                analysis_for_context = results["combined_analysis"]
            else:
                analysis_for_context = results.get("enhanced_analysis", "")
                
            # Store the analysis context for other approaches
            st.session_state.chat_context = f"""
            MATCH: {full_query}
            
            ANALYSIS:
            {analysis_for_context}
            """
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error(traceback.format_exc())

def generate_analysis_conversational(home_team, away_team, league, match_date):
    """Generate analysis for the specified match using a conversational approach"""
    try:
        match_details = f"{home_team} vs {away_team}"
        full_query = f"{match_details} {league} {match_date.strftime('%d %B %Y')}"
        
        # Initialize chat if not present
        if "analysis_chat" not in st.session_state:
            st.session_state.analysis_chat = []
            
        # Set analysis in progress flag
        st.session_state.analysis_in_progress = True
            
        # Send welcome message
        add_analysis_message("assistant", f"I'll analyze the upcoming match between {home_team} and {away_team}. Let me gather the information we need!", animate=True)
        
        # Set up early chat context with basic match info
        early_context = f"""
        MATCH: {match_details}
        LEAGUE: {league}
        DATE: {match_date.strftime('%d %B %Y')}
        
        ANALYSIS: Currently being generated. Basic questions about these teams can be answered.
        """
        
        # Initialize chat bot early with limited context
        st.session_state.chat_context = early_context
        setup_chat_with_context({"initial_analysis": early_context}, full_query, chat_method, openai_api_key)
        

        # Check if analysis already exists
        if supabase_client:
            add_analysis_message("assistant", "First, let me check if I've already analyzed this match before...")
            
            exists, analysis_id = check_analysis_exists(supabase_client, home_team, away_team, match_date)
            if exists:
                add_analysis_message("assistant", f"Good news! I've already analyzed this match. Let me load that analysis for you.")
                
                analysis_data = get_analysis_by_id(supabase_client, analysis_id)
                if analysis_data:
                    add_analysis_message("assistant", "Analysis loaded successfully! Here's what I found earlier.")
                    # Convert stored analysis to results format
                    results = {
                        "combined_analysis": analysis_data.get("content", ""),
                        "enhanced_analysis": analysis_data.get("content", ""),
                        "initial_analysis": "Loaded from database",
                        "synthesized_news": "Loaded from database",
                        "raw_news": "Loaded from database"
                    }
                    
                    # Store results in session state
                    st.session_state.results = results
                    st.session_state.match_info = {
                        "match": match_details,
                        "league": league,
                        "date": match_date
                    }

                    # Don't return here! Instead, set up the chat context first
                    
                    add_analysis_message("assistant", "You can now explore the detailed results in the tabs above, or chat with me if you have any questions about my findings.")
                    st.session_state.analysis_in_progress = False
                    # Initialize chatbot for follow-up questions
                    setup_chat_with_context(results, full_query, chat_method, openai_api_key)

                    return
                    
            else:
                add_analysis_message("assistant", "This looks like a new analysis! Let me get started.")
        
        # Initialize the result container
        results = {}
        
        # Flag to track if we need to run news analysis
        run_news_analysis = use_news
        
        # Flag to track if we need database analysis
        run_db_analysis = use_database and supabase_client
        
        # Database analysis
        db_insights = None
        if run_db_analysis:
            add_analysis_message("assistant", f"I'll first look at the statistics for both teams...")
            
            # Get match data
            add_analysis_message("assistant", f"Searching for previous matches between these teams...")
            match_data = get_match_by_teams(supabase_client, home_team, away_team, closest_to_date=match_date)
            
            if match_data:
                add_analysis_message("assistant", f"Found {home_team} vs {away_team} match history! Let me analyze that data.")
            else:
                add_analysis_message("assistant", f"These teams don't appear to have played each other recently. I'll focus on their individual performances.")
                # Create a basic match data structure
                match_data = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'match_date': match_date.strftime('%Y-%m-%d'),
                    'league_name': league
                }
            
            # Get team statistics with conversational updates
            add_analysis_message("assistant", f"Now checking {home_team}'s recent form and statistics...")
            team1_data = get_team_stats(supabase_client, home_team)
            if team1_data:
                # Extract a meaningful stat to comment on
                wins = team1_data.get("wins", "several")
                goals = team1_data.get("goals_scored", "a number of")
                add_analysis_message("assistant", f"{home_team} has won {wins} matches recently, scoring {goals} goals. Let me dig deeper into their performance metrics.")
            
            add_analysis_message("assistant", f"Looking at {away_team}'s performance now...")
            team2_data = get_team_stats(supabase_client, away_team)
            if team2_data:
                # Extract a meaningful stat to comment on
                away_form = team2_data.get("wins_away", "decent")
                goals_conceded = team2_data.get("goals_conceded_away", "some")
                add_analysis_message("assistant", f"{away_team} has shown {away_form} away form. They've conceded {goals_conceded} goals on the road.")
            
            # Get head-to-head data with conversational comment
            add_analysis_message("assistant", f"Analyzing head-to-head matches between these teams...")
            h2h_data = get_head_to_head(supabase_client, home_team, away_team)
            if not h2h_data.empty:
                h2h_count = len(h2h_data)
                add_analysis_message("assistant", f"Found {h2h_count} previous encounters between these teams. This will provide valuable context!")
            else:
                add_analysis_message("assistant", "I couldn't find many direct matches between these teams, but that's fine. I'll focus on their individual performances.")
            
            # Get league standings with a conversational comment
            add_analysis_message("assistant", f"Checking the {league} table to see where both teams stand...")
            league_data = get_league_standings(supabase_client, league)
            if not league_data.empty:
                add_analysis_message("assistant", f"Got the current standings! This will help us understand the importance of this match in the {league} context.")
            
            # Generate database insights with conversational update
            add_analysis_message("assistant", "Now I'll analyze all this statistical data to find key insights...")
            db_insights = agents.process_database_insights(
                match_data, 
                team1_data or {"team_name": home_team, "note": "Limited statistics available"}, 
                team2_data or {"team_name": away_team, "note": "Limited statistics available"},
                h2h_data,
                league_data
            )
            
            add_analysis_message("assistant", "Statistical analysis complete! I've found some interesting patterns.")
        
        # News-based analysis with conversational updates
        if run_news_analysis:
            add_analysis_message("assistant", "Now I'll search for the latest news about this match. This will help us catch any recent developments...")
            
            add_analysis_message("assistant", f"Searching for news about {match_details}...")
            results = agents.process_football_news(full_query)
            
            add_analysis_message("assistant", "Found some relevant news articles! I'm processing them to extract the most important information.")
        
        # Combine analyses if both are available
        if run_news_analysis and run_db_analysis and db_insights:
            add_analysis_message("assistant", "I'm now combining statistical insights with the latest news to create a comprehensive analysis...")
            combined_analysis = agents.combine_analysis_with_database(results, db_insights)
            results["combined_analysis"] = combined_analysis
            results["db_insights"] = db_insights
            
            add_analysis_message("assistant", "Analysis complete! I've created a detailed report that combines statistical data with the latest news and expert insights.")
        elif db_insights:
            # Only database analysis available
            add_analysis_message("assistant", "Based on the statistical data, I've prepared a comprehensive analysis...")
            results["db_insights"] = db_insights
            results["enhanced_analysis"] = db_insights  # Use db_insights as the main analysis
            results["initial_analysis"] = "Analysis based on database statistics only."
            results["synthesized_news"] = "No news analysis performed."
            results["raw_news"] = "No news search performed."
            results["combined_analysis"] = db_insights
        
        # Store results in session state
        st.session_state.results = results
        st.session_state.match_info = {
            "match": match_details,
            "league": league,
            "date": match_date
        }

        # Save analysis to WordPress with conversational update
        if supabase_client:
            add_analysis_message("assistant", "I'm saving this analysis to our database in WordPress-ready format...")
            save_success, blog_id = save_analysis_for_wordpress(supabase_client, st.session_state.match_info, results)
            if save_success:
                add_analysis_message("assistant", f"Analysis saved successfully! It's ready to be published to your WordPress site.")
        
        st.session_state.analysis_in_progress = False

        add_analysis_message("assistant", "Analysis complete! You can now explore the detailed results in the tabs above, or chat with me if you have any questions about my findings.")
        
        # Initialize chatbot for follow-up questions
        setup_chat_with_context(results, full_query, chat_method, openai_api_key)
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error(traceback.format_exc())
        add_analysis_message("assistant", "I encountered an error while generating the analysis. Please try again or check the error message for details.")

        st.session_state.analysis_in_progress = False
        
# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("Configure your match analysis parameters")
    
    # API keys
    openai_api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    supabase_url = st.text_input("Supabase URL", type="password", value="https://qbwevimrcpljiryhgxqv.supabase.co")
    supabase_key = st.text_input("Supabase Key", type="password", value="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFid2V2aW1yY3BsamlyeWhneHF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxMzY1NDUsImV4cCI6MjA1OTcxMjU0NX0.H01VSMaBNn3PZ5LEy1AldeIi1lNQL2njzNv2tvFxRsM")
    
    # Initialize Supabase if credentials are provided
    supabase_client = None
    if supabase_url and supabase_key:
        supabase_client = init_supabase(supabase_url, supabase_key)
        if supabase_client:
            st.sidebar.success("Connected to Supabase")
    
    # User ID for memory
    user_id = st.text_input("Username (for personalized memory)", value="default_user")
    
    # Data source selection
    st.subheader("Data Sources")
    use_news = st.checkbox("Include News Analysis", value=True)
    use_database = st.checkbox("Include Database Statistics", value=supabase_client is not None, 
                              help="Uses match data from Supabase database",
                              disabled=supabase_client is None)
    if use_database and supabase_client is None:
        st.warning("Supabase connection required for database statistics")
    
    # Additional analysis options
    st.subheader("Analysis Focus")
    include_betting = st.checkbox("Include Betting Insights", value=True)
    include_stats = st.checkbox("Include Detailed Statistics", value=True)
    include_lineup = st.checkbox("Include Expected Lineups", value=True)
    
    # Chat method selection
    st.subheader("Chat Method")
    chat_method = st.radio(
        "Choose chat implementation:",
        ["Direct Agent", "Embedchain", "Memory-Enhanced"],
        help="Direct Agent uses the analysis directly, Embedchain uses vector embeddings, Memory-Enhanced uses persistent memory"
    )
    
    # Memory options
    st.subheader("Memory Options")
    enable_memory = st.checkbox("Enable Persistent Memory", value=True)
    if enable_memory and openai_api_key:
        memory = initialize_memory(openai_api_key)
        
        # View memory option
        if st.button("View My Memory"):
            try:
                memories = get_all_memories(memory, user_id)
                if memories and "results" in memories and memories["results"]:
                    st.write(f"Memory history for **{user_id}**:")
                    for i, mem in enumerate(memories["results"]):
                        if "memory" in mem:
                            try:
                                memory_dict = json.loads(mem["memory"])
                                st.write(f"**Memory {i+1}**: {memory_dict.get('match', 'Unknown match')}")
                                st.write(f"- Query: {memory_dict.get('query', '')}")
                                st.write(f"- Date: {memory_dict.get('date', '')}")
                                with st.expander("Full Memory"):
                                    st.json(memory_dict)
                            except Exception as e:
                                st.write(f"- {mem['memory']}")
                else:
                    st.info("No memory history found for this user ID.")
            except Exception as e:
                st.error(f"Error retrieving memories: {str(e)}")
    elif enable_memory and not openai_api_key:
        st.warning("API key required for persistent memory.")

# Main content area
col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Match Details")
    
    # Option to select match from database if Supabase is connected
    if supabase_client and use_database:
        st.write("📊 Select from Database or Enter Manually")
        
        # Get leagues from database for filtering
        leagues_tab = st.expander("Filter by League")
        with leagues_tab:
            all_leagues = ["All Leagues", "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League"]
            selected_league = st.selectbox("League", all_leagues)
            league_filter = None if selected_league == "All Leagues" else selected_league
        
        # Get matches from database
        try:
            matches_df = get_matches(supabase_client, league=league_filter)
            
            if not matches_df.empty:
                # Format matches for selection
                match_options = ["Select a match..."] + [
                    f"{row['home_team']} vs {row['away_team']} ({row['match_date']})"
                    for _, row in matches_df.iterrows()
                ]
                
                selected_match = st.selectbox("Select Match from Database", match_options)
                
                # If a match is selected from database
                if selected_match != "Select a match...":
                    # Extract teams and date from selection
                    parts = selected_match.split(' vs ')
                    home_team = parts[0]
                    remaining = parts[1].split(' (')
                    away_team = remaining[0]
                    match_date_str = remaining[1].rstrip(')')
                    
                    # Get league from dataframe
                    match_row = matches_df[
                        (matches_df['home_team'] == home_team) & 
                        (matches_df['away_team'] == away_team)
                    ]
                    
                    if not match_row.empty:
                        # Get league_name or fall back to league_name if available, otherwise use filter or default
                        if 'league_name' in match_row.columns:
                            selected_league = match_row['league_name'].values[0]
                        else:
                            selected_league = league_filter or "Premier League"
                    else:
                        selected_league = league_filter or "Premier League"
                    
                    # Set match date
                    try:
                        match_date = datetime.strptime(match_date_str, '%Y-%m-%d').date()
                    except:
                        match_date = datetime.now().date()
                    
                    # Display form with pre-filled values
                    with st.form("match_details_form"):
                        st.write(f"Selected: **{home_team} vs {away_team}**")
                        league = st.selectbox(
                            "League",
                            ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"],
                            index=["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"].index(selected_league)
                            if selected_league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"] else 0
                        )
                        match_date = st.date_input("Match Date", value=match_date)
                        
                        # Submit button
                        submit_button = st.form_submit_button("Start Chat", type="primary", use_container_width=True)
                        
                        if submit_button:
                            # Process the analysis
                            # Initialize chat history for the new analysis
                            st.session_state.chat_history = []
                            st.session_state.analysis_chat = []
                            st.session_state.first_load = True
                            generate_analysis_conversational(home_team, away_team, league, match_date)
            else:
                st.info("No matches found in database. Enter match details manually.")
                manual_input = True
        except Exception as e:
            st.error(f"Error loading matches: {str(e)}")
            manual_input = True
    else:
        # Manual input mode
        manual_input = True
    
    # Manual input mode
    if not supabase_client or not use_database or ('manual_input' in locals() and manual_input):
        match_details = st.text_input(
            "Enter match details:",
            value="Manchester United vs Liverpool",
            help="Enter team names or specific match (e.g., Arsenal vs Chelsea)"
        )
        
        league = st.selectbox(
            "League",
            ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"]
        )
        
        match_date = st.date_input("Match Date")
        
        if st.button("Generate Analysis", type="primary", use_container_width=True):
            if match_details:
                # Parse teams from match details
                if " vs " in match_details:
                    teams = match_details.split(" vs ")
                    home_team = teams[0].strip()
                    away_team = teams[1].strip()
                    #generate_analysis(home_team, away_team, league, match_date)
                    # Initialize or clear analysis chat
                    st.session_state.analysis_chat = []
                    
                    # Call conversational analysis function
                    generate_analysis_conversational(home_team, away_team, league, match_date)


                else:
                    st.error("Please enter match details in the format 'Team A vs Team B'")
            else:
                st.error("Please enter match details!")

# Results area
with col2:
    if "analysis_chat" in st.session_state and st.session_state.analysis_chat:
        if "results" in st.session_state and "match_info" in st.session_state:
            results = st.session_state.results
            match_info = st.session_state.match_info
            
            st.subheader(f"Match Analysis: {match_info['match']}")
            st.caption(f"{match_info['league']} | {match_info['date'].strftime('%d %B %Y')}")
            
            # Create tabs based on available analyses
            tabs = []
            if "combined_analysis" in results:
                tabs.append("Combined Analysis")
            
            if "enhanced_analysis" in results:
                tabs.append("Enhanced Analysis")
                
            if "db_insights" in results:
                tabs.append("Database Insights")
                
            if "initial_analysis" in results:
                tabs.append("Initial Summary")
                
            if "synthesized_news" in results:
                tabs.append("News Synthesis")
                
            if "raw_news" in results:
                tabs.append("Raw Sources")
                
            tabs.append("Chat")
            
            # Create the tabs
            all_tabs = st.tabs(tabs)
            
            # Set the active tab to the chat tab (which is the last one)
            active_tab_index = len(tabs) - 1  # Index of the Chat tab

            # Store the results first, then force a rerun to show the chat tab
            if "first_load" not in st.session_state or st.session_state.first_load:
                st.session_state.first_load = False
                st.rerun()

            # Fill each tab with appropriate content
            tab_index = 0
            
            # Combined Analysis Tab
            if "combined_analysis" in results:
                with all_tabs[tab_index]:
                    st.markdown("### 📊 Combined Analysis")
                    st.markdown(results["combined_analysis"])
                    st.download_button(
                        "Download Combined Analysis",
                        results["combined_analysis"],
                        file_name=f"{match_info['match'].replace(' ', '_')}_combined_analysis.md",
                        mime="text/markdown"
                    )
                tab_index += 1
            
            # Enhanced Analysis Tab
            if "enhanced_analysis" in results:
                with all_tabs[tab_index]:
                    st.markdown("### 📊 Enhanced Analysis")
                    st.markdown(results["enhanced_analysis"])
                    st.download_button(
                        "Download Enhanced Analysis",
                        results["enhanced_analysis"],
                        file_name=f"{match_info['match'].replace(' ', '_')}_enhanced_analysis.md",
                        mime="text/markdown"
                    )
                tab_index += 1
                
            # Database Insights Tab
            if "db_insights" in results:
                with all_tabs[tab_index]:
                    st.markdown("### 🗃️ Database Insights")
                    st.markdown(results["db_insights"])
                    st.download_button(
                        "Download Database Insights",
                        results["db_insights"],
                        file_name=f"{match_info['match'].replace(' ', '_')}_database_insights.md",
                        mime="text/markdown"
                    )
                tab_index += 1
            
            # Initial Summary Tab
            if "initial_analysis" in results:
                with all_tabs[tab_index]:
                    st.markdown("### 📝 Initial Match Summary")
                    st.markdown(results["initial_analysis"])
                tab_index += 1
            
            # News Synthesis Tab
            if "synthesized_news" in results:
                with all_tabs[tab_index]:
                    st.markdown("### 🔄 News Synthesis")
                    st.markdown(results["synthesized_news"])
                tab_index += 1
            
            # Raw Sources Tab
            if "raw_news" in results:
                with all_tabs[tab_index]:
                    st.markdown("### 🔍 Raw News Sources")
                    st.text_area("Sources", results["raw_news"], height=400)
                tab_index += 1
            
            # Chat Tab (always present)
            with all_tabs[tab_index]:
                st.markdown("### 💬 Chat with TipsterHeroes.AI")
                
                # Display chat history
                for message in st.session_state.chat_history:
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
                
                # Chat input
                if chat_prompt := st.chat_input("Ask about the match analysis..."):
                    # Add user message to chat history
                    st.session_state.chat_history.append({"role": "user", "content": chat_prompt})
                    
                    # Display user message
                    with st.chat_message("user"):
                        st.write(chat_prompt)
                    
                    # Generate and display response
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            if chat_method == "Embedchain" and st.session_state.chat_bot:
                                response = st.session_state.chat_bot.chat(chat_prompt)
                            elif chat_method == "Memory-Enhanced" and enable_memory and openai_api_key:
                                # Get relevant memories
                                relevant_memories = get_relevant_memories(memory, user_id, chat_prompt, match_info)
                                
                                # Create memory context
                                memory_context = ""
                                if relevant_memories:
                                    memory_context = "Based on our previous conversations:\n"
                                    for i, mem in enumerate(relevant_memories[:3]):  # Limit to top 3 memories
                                        memory_context += f"- {mem.get('query', '')}: {mem.get('response', '')}\n"
                                
                                # Enhanced analysis context with memory
                                enhanced_context = f"{st.session_state.chat_context}\n\nMEMORY CONTEXT:\n{memory_context}"
                                
                                # Get response with memory-enhanced context
                                response = agents.chat_with_analysis(
                                    chat_prompt, 
                                    enhanced_context,
                                    st.session_state.chat_history[:-1]  # Exclude current query
                                )
                                
                                # Save interaction to memory
                                memory_saved = save_chat_to_memory(memory, user_id, match_info, chat_prompt, response)
                                if memory_saved:
                                    st.sidebar.success("Interaction saved to memory", icon="✅")
                            elif chat_method == "Direct Agent" and "chat_context" in st.session_state:
                                response = agents.chat_with_analysis(
                                    chat_prompt, 
                                    st.session_state.chat_context,
                                    st.session_state.chat_history[:-1]  # Exclude current query
                                )
                            else:
                                response = "Please generate an analysis first and ensure API key is provided if using Embedchain or Memory-Enhanced modes."
                            
                            st.write(response)
                            
                    # Add assistant response to chat history
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
    else:
        st.info("Enter match details and generate an analysis to see results here.")

# Clear chat button
if "chat_history" in st.session_state and len(st.session_state.chat_history) > 0:
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("ⓒ TipsterHeroes.AI - Powered by data. Sharpened by edge.")