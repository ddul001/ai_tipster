"""
Main application file for TipsterHeroes.AI - Football Match Analysis
Handles UI components and orchestrates the workflow between agents and data services.
"""
# THIS MUST BE THE FIRST STREAMLIT COMMAND IN YOUR FILE
import streamlit as st
from urllib.parse import parse_qs

st.set_page_config(
    page_title="AI Tipster",
    page_icon="⚽",
    initial_sidebar_state="collapsed",  # or "expanded", "auto"
    layout="wide"
)

# Debug logging helper
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

def log_debug(message):
    """Add a timestamped debug message to the session log"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.debug_logs.append(f"{timestamp}: {message}")
    if len(st.session_state.debug_logs) > 100:
        st.session_state.debug_logs = st.session_state.debug_logs[-100:]
    print(f"DEBUG: {timestamp}: {message}")  # Also print to console for server logs

# Get URL parameters (if any)
query_params = st.query_params
match_id_param = query_params.get("match_id", [None])[0]
auto_analyze = query_params.get("analyze", ["false"])[0].lower() == "true"

# Initialize session state for URL parameters if not exists
if "url_match_id" not in st.session_state:
    st.session_state.url_match_id = match_id_param
    st.session_state.url_auto_analyze = auto_analyze
    st.session_state.url_params_processed = False

# Initialize analysis state if not exists
if "in_analysis_mode" not in st.session_state:
    st.session_state.in_analysis_mode = False

import os
from datetime import datetime
from dotenv import load_dotenv
import json
import traceback

# Import from local modules
import agents
from data_service import (
    add_analysis_message, check_analysis_exists, extract_betting_insights, get_analysis_by_id, get_match_with_bets, init_supabase, initialize_memory, parse_wordpress_analysis, save_analysis_for_wordpress, setup_chat_with_context, setup_embedchain,
    save_chat_to_memory, get_relevant_memories, get_all_memories,
    get_matches, get_team_stats, get_match_by_teams, get_head_to_head,
    get_league_standings 
)

# Load environment variables
load_dotenv()



 

st.title("⚽ TipsterHeroes.AI - Football Match Analysis")
st.markdown("AI-powered football news analysis for match predictions and betting insights")

# Initialize session states
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "chat_bot" not in st.session_state:
    st.session_state.chat_bot = None

def get_match_by_id(supabase_client, match_id):
    """Fetch a match by its ID from the database and include team names"""
    try:
        # Get match data
        response = supabase_client.from_("matches").select("*").eq("match_id", match_id).execute()
        if not response.data:
            return None
            
        match_data = response.data[0]
        
        # Get home team name
        home_team_id = match_data.get("hometeam_id")
        home_team_response = supabase_client.from_("teams").select("team_name").eq("team_id", home_team_id).execute()
        if home_team_response.data:
            match_data["home_team"] = home_team_response.data[0].get("team_name")
        else:
            match_data["home_team"] = "Unknown Home Team"
            
        # Get away team name
        away_team_id = match_data.get("awayteam_id")
        away_team_response = supabase_client.from_("teams").select("team_name").eq("team_id", away_team_id).execute()
        if away_team_response.data:
            match_data["away_team"] = away_team_response.data[0].get("team_name")
        else:
            match_data["away_team"] = "Unknown Away Team"
            
        # Get league name if needed
        league_id = match_data.get("league_id")
        league_response = supabase_client.from_("leagues").select("league").eq("league_id", league_id).execute()
        if league_response.data:
            match_data["league_name"] = league_response.data[0].get("league")
            
        return match_data
    except Exception as e:
        st.error(f"Error fetching match by ID: {str(e)}")
        return None

def get_leagues(supabase_client):
    response = supabase_client.from_("leagues").select("league").execute()
    # Check if error
    if hasattr(response, 'error') and response.error:
        st.error("Failed to load leagues: " + str(response.error))
        return []

    # Build list
    return [item["league"] for item in response.data]

def summarize_analysis(text, max_length=300):
    """Summarize analysis text to a specified character length"""
    if len(text) <= max_length:
        return text
        
    # Simple approach: take the first couple of sentences
    sentences = text.split('.')
    summary = ""
    for sentence in sentences:
        if len(summary) + len(sentence) + 1 <= max_length:
            summary += sentence + "."
        else:
            break
    return summary


# Function to generate analysis
def generate_analysis(home_team, away_team, league, match_date):
    """Generate analysis for the specified match"""
    try:
        log_debug(f"Starting generate_analysis for {home_team} vs {away_team}")
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
                    add_analysis_message("assistant", "Analysis loaded successfully! Here's what I found earlier.")
    
                    # Parse the content if it's in WordPress HTML format
                    content = analysis_data.get("content", "")
                    parsed_content = parse_wordpress_analysis(content)
                    
                    # Extract betting insights if available
                    betting_insights = extract_betting_insights(parsed_content)
                    
                    # Convert stored analysis to results format
                    results = {
                        "combined_analysis": parsed_content,
                        "enhanced_analysis": parsed_content,
                        "initial_analysis": "Loaded from database",
                        "synthesized_news": "Loaded from database",
                        "raw_news": "Loaded from database",
                        "original_html": content,  # Store the original HTML for reference
                        "betting_insights": betting_insights  # Store extracted betting insights
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
                match_data = get_match_with_bets(supabase_client, home_team, away_team, closest_to_date=match_date)
                
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

                if match_data:
                    # Extract country_id directly from match data
                    country_id = match_data.get("country_id")
                    league_id = match_data.get("league_id")
                    
                    # Store for later use
                    st.session_state.from_url_country_id = country_id
                    st.session_state.from_url_league_id = league_id
                    
                    # Get the country name for this ID
                    country_response = supabase_client.from_("countries").select("country").eq("country_id", country_id).execute()
                    if country_response.data:
                        st.session_state.from_url_country = country_response.data[0].get("country")
                
                # Get head-to-head data
                # status.write("🏆 Retrieving head-to-head history...")
                # h2h_data = get_head_to_head(supabase_client, home_team, away_team)
                
                # Get league standings
                status.write("🏆 Retrieving league standings...")
                league_data = get_league_standings(supabase_client, league)
                
                # Generate database insights
                status.write("🧠 Analyzing database information...")
                db_insights = agents.process_database_insights(
                    match_data, 
                    team1_data or {"team_name": home_team, "note": "Limited statistics available"}, 
                    team2_data or {"team_name": away_team, "note": "Limited statistics available"},
                    #h2h_data,
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
        
        # Mark analysis as complete
        st.session_state.analysis_in_progress = False
        log_debug(f"Analysis completed for {home_team} vs {away_team}")
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error(traceback.format_exc())
        st.session_state.analysis_in_progress = False
        log_debug(f"Error in generate_analysis: {str(e)}")

def generate_analysis_conversational(home_team, away_team, league, match_date):
    """Generate analysis for the specified match using a conversational approach"""
    try:
        log_debug(f"Starting generate_analysis_conversational for {home_team} vs {away_team}")
        match_details = f"{home_team} vs {away_team}"
        full_query = f"{match_details} {league or 'Unknown League'} {match_date.strftime('%d %B %Y')}"

        if "analysis_chat" not in st.session_state:
            st.session_state.analysis_chat = []
        st.session_state.analysis_in_progress = True

        early_context = f"MATCH: {match_details}\nLEAGUE: {league}\nDATE: {match_date.strftime('%d %B %Y')}"
        st.session_state.chat_context = early_context

        if supabase_client:
            exists, analysis_id = check_analysis_exists(supabase_client, home_team, away_team, match_date)
            if exists:
                log_debug(f"Found existing analysis ID: {analysis_id}")
                analysis_data = get_analysis_by_id(supabase_client, analysis_id)
                if analysis_data:
                    parsed_content = parse_wordpress_analysis(analysis_data.get("content", ""))
                    results = {
                        "source_type": "db",
                        "combined_analysis": parsed_content
                    }
                    st.session_state.results = results
                    st.session_state.match_info = {"match": match_details, "league": league, "date": match_date}
                    st.session_state.analysis_in_progress = False
                    return

        log_debug("Processing news analysis")
        results = agents.process_football_news(full_query)

        db_insights = None
        if use_database and supabase_client:
            log_debug("Processing database insights")
            db_insights = agents.process_database_insights(
                match_data={
                    'home_team': home_team,
                    'away_team': away_team,
                    'match_date': match_date.strftime('%Y-%m-%d'),
                    'league_name': league or "Unknown"
                },
                team1_data=get_team_stats(supabase_client, home_team),
                team2_data=get_team_stats(supabase_client, away_team),
                head_to_head_data=None,
                league_data=get_league_standings(supabase_client, league)
            )

            results = {
                **results,
                "source_type": "news+db",
                "db_insights": db_insights,
                "combined_analysis": agents.combine_analysis_with_database(results, db_insights)
            }

        st.session_state.results = results
        st.session_state.match_info = {"match": match_details, "league": league, "date": match_date}
        st.session_state.analysis_in_progress = False
        log_debug(f"Analysis conversational completed for {home_team} vs {away_team}")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error(traceback.format_exc())
        st.session_state.analysis_in_progress = False
        log_debug(f"Error in generate_analysis_conversational: {str(e)}")






# Main State Initialization
# Log initial state for debugging
log_debug(f"Initial State - in_analysis_mode: {st.session_state.get('in_analysis_mode', False)}, " + 
          f"start_analysis: {st.session_state.get('start_analysis', False)}, " +
          f"analysis_in_progress: {st.session_state.get('analysis_in_progress', False)}")

# Process URL parameters first (if not already processed)
if supabase_client and st.session_state.url_match_id and not st.session_state.get("url_params_processed", False):
    log_debug(f"Processing URL parameter match_id: {st.session_state.url_match_id}")
    match_data = get_match_by_id(supabase_client, st.session_state.url_match_id)
    
    # Mark params as processed
    st.session_state.url_params_processed = True
    
    if match_data:
        # Extract match data
        home_team = match_data.get("home_team")
        away_team = match_data.get("away_team")
        match_date_str = match_data.get("match_date")
        league = match_data.get("league_name") or "Unknown League"
        
        # Parse date
        try:
            match_date = datetime.strptime(match_date_str, '%Y-%m-%d').date()
        except:
            match_date = datetime.now().date()
        
        # Auto-analyze if requested in URL
        if st.session_state.url_auto_analyze and not st.session_state.get("analysis_triggered", False):
            log_debug(f"Auto-analyzing from URL: {home_team} vs {away_team}")
            st.session_state.match_to_analyze = {
                "home_team": home_team,
                "away_team": away_team, 
                "league": league,
                "match_date": match_date,
                "from_url": True
            }
            st.session_state.in_analysis_mode = True
            st.session_state.start_analysis = True
            st.session_state.analysis_triggered = True
            # Don't call rerun here, let the next check handle it

# Check if we should start analysis based on session state
if st.session_state.get("start_analysis", False) and "match_to_analyze" in st.session_state:
    match_info = st.session_state.match_to_analyze
    log_debug(f"Starting analysis from session state for {match_info.get('home_team')} vs {match_info.get('away_team')}")
    
    # Clear the flag
    st.session_state.start_analysis = False
    
    # Prepare analysis environment
    st.session_state.chat_history = []
    st.session_state.analysis_in_progress = True
    st.session_state.analysis_chat = []
    st.session_state.first_load = True
    
    # Store the URL origin if it was from URL
    if match_info.get("from_url", False):
        st.session_state.from_url_analysis = True
    
    # Start the analysis - this is critical
    generate_analysis_conversational(
        match_info["home_team"], 
        match_info["away_team"], 
        match_info["league"], 
        match_info["match_date"]
    )




# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("Configure your match analysis parameters")
    
    # API keys
    openai_api_key = st.secrets["OPENAI_API_KEY"]
    supabase_url = "https://qbwevimrcpljiryhgxqv.supabase.co"
    supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFid2V2aW1yY3BsamlyeWhneHF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQxMzY1NDUsImV4cCI6MjA1OTcxMjU0NX0.H01VSMaBNn3PZ5LEy1AldeIi1lNQL2njzNv2tvFxRsM"
    
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
    use_database = st.checkbox("Include Database Statistics", value=True, 
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
    enable_memory = st.checkbox("Enable Persistent Memory", value=False)
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
    
    # Debug log viewer 
    if st.checkbox("Show Debug Log"):
        st.subheader("Debug Log")
        for log in st.session_state.debug_logs:
            st.text(log)
        if st.button("Clear Debug Log"):
            st.session_state.debug_logs = []
            
        # Also show session state
        with st.expander("Session State"):
            # Filter out large objects
            filtered_state = {}
            for key, value in st.session_state.items():
                if key in ['debug_logs', 'results', 'chat_history', 'chat_context']:
                    filtered_state[key] = f"[{type(value).__name__} - too large to display]"
                else:
                    filtered_state[key] = value
            st.json(filtered_state)



# Main content area
col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Match Details")
    
    # First, check if we're already in analysis mode - make this check stronger
    in_analysis = st.session_state.get("in_analysis_mode", False) or st.session_state.get("analysis_in_progress", False)
    log_debug(f"Rendering main UI - in_analysis: {in_analysis}")
    
    if in_analysis:
        # Display current analysis info
        if "match_info" in st.session_state:
            match_info = st.session_state.match_info
            st.success("Analysis in progress...")
            st.markdown(f"### {match_info.get('match')}")
            st.write(f"**League:** {match_info.get('league')}")
            st.write(f"**Date:** {match_info.get('date').strftime('%d %B %Y')}")
            
            # Add button to exit analysis mode
            if st.button("Select Different Match", type="secondary"):
                # Reset all analysis-related state
                st.session_state.in_analysis_mode = False
                st.session_state.from_url_analysis = False
                st.session_state.analysis_in_progress = False
                st.session_state.start_analysis = False
                # Force page reload
                st.rerun()
        else:
            st.info("Preparing analysis...")
    else:
        # Not in analysis mode - show selection UI
        if supabase_client and use_database:
            st.write("📊 Select from Database or Enter Manually")
            
            # Handle URL parameter match if not in analysis mode
            if supabase_client and st.session_state.url_match_id and not st.session_state.get("url_params_processed", False):
                match_data = get_match_by_id(supabase_client, st.session_state.url_match_id)
                
                # Debug output
                st.sidebar.subheader("Debug: Match Data from URL Parameter")
                st.sidebar.write(f"Requested match_id: {st.session_state.url_match_id}")
                st.sidebar.json(match_data)
                
                # Mark params as processed
                st.session_state.url_params_processed = True
                
                if match_data:
                    # Extract match data
                    home_team = match_data.get("home_team")
                    away_team = match_data.get("away_team")
                    match_date_str = match_data.get("match_date")
                    league = match_data.get("league_name") or "Unknown League"
                    country_id = match_data.get("country_id")
                    
                    # Get country name
                    country_name = "Unknown Country"
                    if country_id:
                        country_response = supabase_client.from_("countries").select("country").eq("country_id", country_id).execute()
                        if country_response.data:
                            country_name = country_response.data[0].get("country")
                    
                    # Parse date
                    try:
                        match_date = datetime.strptime(match_date_str, '%Y-%m-%d').date()
                    except:
                        match_date = datetime.now().date()
                    
                    # Show match details
                    st.success("Match found from URL parameter!")
                    st.markdown(f"### {home_team} vs {away_team}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Country:** {country_name}")
                        st.write(f"**League:** {league}")
                    with col_b:
                        st.write(f"**Date:** {match_date.strftime('%d %B %Y')}")
                    
                    # Add analyze button
                    if st.button("Analyze This Match", type="primary", use_container_width=True):
                        log_debug(f"Analyze This Match button clicked for {home_team} vs {away_team}")
                        # Store match info in session state
                        st.session_state.match_to_analyze = {
                            "home_team": home_team,
                            "away_team": away_team, 
                            "league": league,
                            "match_date": match_date,
                            "from_url": True
                        }
                        # Set analysis mode flags
                        st.session_state.in_analysis_mode = True
                        st.session_state.start_analysis = True
                        st.session_state.analysis_triggered = True
                        
                        # Start analysis directly before rerun to ensure it begins
                        log_debug("Starting analysis immediately before rerun")
                        generate_analysis_conversational(
                            home_team, away_team, league, match_date
                        )
                        
                        # Force reload to update UI
                        st.rerun()
                    
                    # Auto-analyze if requested
                    if st.session_state.url_auto_analyze and not st.session_state.get("analysis_triggered", False):
                        log_debug(f"Auto-analyze triggered for {home_team} vs {away_team}")
                        st.session_state.match_to_analyze = {
                            "home_team": home_team,
                            "away_team": away_team, 
                            "league": league,
                            "match_date": match_date,
                            "from_url": True
                        }
                        st.session_state.in_analysis_mode = True
                        st.session_state.start_analysis = True
                        st.session_state.analysis_triggered = True
                        
                        # Start analysis directly before rerun
                        log_debug("Starting analysis immediately from auto-analyze trigger")
                        generate_analysis_conversational(
                            home_team, away_team, league, match_date
                        )
                        st.rerun()
                    
                    # Don't show normal selection UI
                    show_normal_ui = False
                else:
                    st.warning(f"No match found with ID: {st.session_state.url_match_id}")
                    show_normal_ui = True
            else:
                show_normal_ui = True
                
            # Show normal match selection UI
            if show_normal_ui:
                # Country selection
                countries_data = supabase_client.from_("countries").select("country_id, country").execute()
                country_dict = {c["country_id"]: c["country"] for c in countries_data.data if c.get("country_id")}
                
                if country_dict:
                    selected_country_name = st.selectbox("Filter by Country", sorted(country_dict.values()))
                    selected_country_id = [k for k, v in country_dict.items() if v == selected_country_name]
                    if selected_country_id:
                        selected_country_id = selected_country_id[0]
        
                        # League selection
                        leagues_data = supabase_client.from_("leagues").select("league_id, league").eq("country_id", selected_country_id).execute()
                        league_options = {"All Leagues": None}
                        league_options.update({f"{item['league']}": item['league_id'] for item in leagues_data.data})
                        selected_league_display = st.selectbox("Filter by League", list(league_options.keys()))
                        league_filter_value = league_options[selected_league_display]
        
                        # Get matches for the selected league
                        try:
                            matches_df = get_matches(supabase_client, league=league_filter_value)
                            
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
                                            selected_league = league_filter_value or "Premier League"
                                    else:
                                        selected_league = league_filter_value or "Premier League"
                                    
                                    # Set match date
                                    try:
                                        match_date = datetime.strptime(match_date_str, '%Y-%m-%d').date()
                                    except:
                                        match_date = datetime.now().date()
                                    
                                    # Display form with pre-filled values
                                    with st.form("match_details_form"):
                                        st.write(f"Selected: **{home_team} vs {away_team}**")
                                        league = selected_league
                                        match_date = st.date_input("Match Date", value=match_date)
                                        
                                        # Submit button
                                        submit_button = st.form_submit_button("Start Chat", type="primary", use_container_width=True)
                                        
                                        if submit_button:
                                            log_debug(f"Form submitted for {home_team} vs {away_team}")
                                            # Store analysis parameters in session state
                                            st.session_state.match_to_analyze = {
                                                "home_team": home_team,
                                                "away_team": away_team, 
                                                "league": league,
                                                "match_date": match_date
                                            }
                                            # Set flag to trigger analysis on next rerun
                                            st.session_state.in_analysis_mode = True
                                            st.session_state.start_analysis = True
                                            st.session_state.analysis_triggered = True
                                            
                                            # Start analysis directly
                                            log_debug("Starting analysis from form submission")
                                            generate_analysis_conversational(
                                                home_team, away_team, league, match_date
                                            )
                                            st.rerun()
                            else:
                                st.info("No matches found in database. Enter match details manually.")
                                manual_input = True
                        except Exception as e:
                            st.error(f"Error loading matches: {str(e)}")
                            manual_input = True
        else:
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
                    if " vs " in match_details:
                        teams = match_details.split(" vs ")
                        home_team = teams[0].strip()
                        away_team = teams[1].strip()
                        
                        log_debug(f"Generate Analysis button clicked for {home_team} vs {away_team}")
                        # Store analysis parameters
                        st.session_state.match_to_analyze = {
                            "home_team": home_team,
                            "away_team": away_team, 
                            "league": league,
                            "match_date": match_date
                        }
                        # Set analysis mode and trigger
                        st.session_state.in_analysis_mode = True
                        st.session_state.start_analysis = True
                        st.session_state.analysis_triggered = True
                        
                        # Start analysis directly
                        log_debug("Starting analysis from manual input")
                        generate_analysis_conversational(
                            home_team, away_team, league, match_date
                        )
                        st.rerun()
                    else:
                        st.error("Please enter match details in the format 'Team A vs Team B'")
                else:
                    st.error("Please enter match details!")

# Results area
# This is the modified section for the right column (col2)
# Replace your current col2 section with this code

# Results area
with col2:
    if "analysis_chat" in st.session_state:
        st.subheader("⚽ Match Analysis Chat")

        # Only set match_info if it's not already in session state
        if "match_info" not in st.session_state:
            # Initialize with default values in case we're coming from a different flow
            # (The real values will be set in generate_analysis_conversational)
            st.session_state.match_info = {
                "match": "Upcoming Match",
                "league": "League",
                "date": datetime.now().date()
            }
        
        # Check if we have results and match info
        if "results" in st.session_state and "match_info" in st.session_state:
            match_info = st.session_state.match_info
            st.caption(f"{match_info['match']} | {match_info['league']} | {match_info['date'].strftime('%d %B %Y')}")
        
            if "results" in st.session_state:
                tab1, tab2, tab3 = st.tabs(["Chat", "Analysis", "Betting"])
                
                with tab1:
                    # Chat tab remains empty as the chat interface is displayed outside the tabs
                    pass
                
                with tab2:
                    st.subheader("Full Match Analysis")
                    
                    # Display the most comprehensive analysis available
                    # Check if we have original HTML content (from WordPress)
                    if "original_html" in st.session_state.results:
                        # Create sub-tabs for different view options
                        analysis_tab1, analysis_tab2 = st.tabs(["Formatted", "Original HTML"])
                        
                        with analysis_tab1:
                            # Display the nicely formatted parsed content
                            if "combined_analysis" in st.session_state.results:
                                st.markdown(st.session_state.results["combined_analysis"])
                            elif "enhanced_analysis" in st.session_state.results:
                                st.markdown(st.session_state.results["enhanced_analysis"])
                            else:
                                st.info("No formatted analysis available.")
                                
                        with analysis_tab2:
                            # Give option to view the original HTML
                            with st.expander("View Original HTML"):
                                st.code(st.session_state.results["original_html"], language="html")
                    else:
                        # Display the most comprehensive analysis available - no HTML version
                        if "combined_analysis" in st.session_state.results:
                            st.markdown(st.session_state.results["combined_analysis"])
                        elif "enhanced_analysis" in st.session_state.results:
                            st.markdown(st.session_state.results["enhanced_analysis"])
                        elif "db_insights" in st.session_state.results:
                            st.markdown(st.session_state.results["db_insights"])
                        elif "initial_analysis" in st.session_state.results:
                            st.markdown(st.session_state.results["initial_analysis"])
                        else:
                            st.info("No detailed analysis available yet.")
                
                with tab3:
                    st.subheader("Available Bets")
                    # Extract teams from match
                    if "match" in match_info:
                        teams = match_info["match"].split(" vs ")
                        if len(teams) == 2:
                            home_team = teams[0].strip()
                            away_team = teams[1].strip()
                            
                            # Try to get and display bets
                            if supabase_client:
                                match_with_bets = get_match_with_bets(supabase_client, home_team, away_team, 
                                                            closest_to_date=match_info["date"])
                                
                                if match_with_bets and match_with_bets.get("has_bets", False):
                                    # Format bets data for display
                                    import pandas as pd
                                    bet_data = []
                                    for bet_type, bet_info in match_with_bets.get("bets", {}).items():
                                        bet_data.append({
                                            "Bet Type": bet_type,
                                            "Odds": bet_info.get("odds", "-"),
                                            "Consensus": bet_info.get('consensus', 0),
                                            "EV": bet_info.get('ev', 0), 
                                            "Tier": bet_info.get("tier", "-")
                                        })
                                    
                                    if bet_data:
                                        # Sort by tier (if available) and then by expected value
                                        if any(bd.get("Tier") for bd in bet_data):
                                            # Convert tier to numeric for sorting (A=1, B=2, etc.)
                                            tier_map = {"A": 1, "B": 2, "C": 3, "D": 4}
                                            for bd in bet_data:
                                                if bd.get("Tier") in tier_map:
                                                    bd["tier_sort"] = tier_map[bd["Tier"]]
                                                else:
                                                    bd["tier_sort"] = 10  # Unknown tiers at the end
                                            
                                            bet_df = pd.DataFrame(bet_data)
                                            if "tier_sort" in bet_df.columns:
                                                bet_df = bet_df.sort_values("tier_sort")
                                                bet_df = bet_df.drop("tier_sort", axis=1)
                                        else:
                                            bet_df = pd.DataFrame(bet_data)
                                        
                                        st.dataframe(bet_df, use_container_width=True)
                                        
                                        # Display top recommendations
                                        top_bets = [b for b in bet_data if b.get("Tier") in ["A", "B"]]
                                        if top_bets:
                                            st.subheader("Top Recommended Bets")
                                            for i, bet in enumerate(top_bets[:3]):  # Show top 3
                                                with st.container():
                                                    st.markdown(f"### {i+1}. {bet['Bet Type']}")
                                                    cols = st.columns(3)
                                                    with cols[0]:
                                                        st.metric("Odds", bet["Odds"])
                                                    with cols[1]:
                                                        st.metric("Expected Value", bet["EV"])
                                                    with cols[2]:
                                                        st.metric("Tier", bet["Tier"])
                                    else:
                                        st.info("No bets found for this match.")
                                else:
                                    st.info("No betting data available for this match.")
                            else:
                                st.warning("Connect to Supabase to view betting information.")
                                # Display progress indicator while analysis is running
        if "analysis_in_progress" in st.session_state and st.session_state.analysis_in_progress:
            st.info("Analysis in progress... Please wait.")
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input - only show if analysis is complete
        if "analysis_in_progress" not in st.session_state or not st.session_state.analysis_in_progress:
            if chat_prompt := st.chat_input("Ask about the match analysis..."):
                # Add user message to chat history
                st.session_state.chat_history.append({"role": "user", "content": chat_prompt})
                
                # Display user message
                with st.chat_message("user"):
                    st.write(chat_prompt)
                
                # Generate and display response
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        if chat_method == "Embedchain" and "chat_bot" in st.session_state and st.session_state.chat_bot:
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
                                scraped_content=st.session_state.results.get("scraped_content", {}), # Pass scraped content
                                chat_history=st.session_state.chat_history[:-1] # Keyword argument
                            )
                            
                            # Save interaction to memory
                            memory_saved = save_chat_to_memory(memory, user_id, match_info, chat_prompt, response)
                            if memory_saved:
                                st.sidebar.success("Interaction saved to memory", icon="✅")
                        elif chat_method == "Direct Agent" and "chat_context" in st.session_state:
                            response = agents.chat_with_analysis(
                                chat_prompt, 
                                st.session_state.chat_context,
                                scraped_content=st.session_state.results.get("scraped_content", {}), # Pass scraped content
                                chat_history=st.session_state.chat_history[:-1] # Keyword argument
                            )
                        else:
                            response = "Please generate an analysis first and ensure API key is provided if using Embedchain or Memory-Enhanced modes."
                        
                        st.write(response)
                        
                # Add assistant response to chat history
                st.session_state.chat_history.append({"role": "assistant", "content": response})
    else:
        st.info("Enter match details and start the chat to see results here.")

    # Clear chat button
    if "chat_history" in st.session_state and len(st.session_state.chat_history) > 0:
        if st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()

# Footer
st.markdown("---")
st.markdown("ⓒ TipsterHeroes.AI - Powered by data. Sharpened by edge.")
