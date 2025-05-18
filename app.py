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
    st.session_state.url_params_processed = False # Flag to process URL only once per load

# Initialize analysis state if not exists
if "in_analysis_mode" not in st.session_state:
    st.session_state.in_analysis_mode = False
if "start_analysis" not in st.session_state:
    st.session_state.start_analysis = False # Flag to trigger analysis execution block
if "analysis_in_progress" not in st.session_state:
     st.session_state.analysis_in_progress = False # Flag to show spinner/status
if "analysis_triggered" not in st.session_state:
    st.session_state.analysis_triggered = False # Flag to prevent re-triggering from URL button


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
    get_league_standings, get_country_name_by_id # Added this helper
)

# Load environment variables
load_dotenv()

# Initialize API keys and Supabase connection from secrets
openai_api_key = st.secrets.get("OPENAI_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY")

def get_match_by_id(supabase_client, match_id):
    try:
        response = supabase_client.from_("matches").select("*").eq("match_id", match_id).execute()
        if not response.data:
            return None
        match_data = response.data[0]
        home_team_id = match_data.get("hometeam_id")
        home_team_response = supabase_client.from_("teams").select("team_name").eq("team_id", home_team_id).execute()
        
        if home_team_response.data:
            match_data["home_team"] = home_team_response.data[0].get("team_name")
        else:
            match_data["home_team"] = "Unknown Home Team"

        away_team_id = match_data.get("awayteam_id")
        away_team_response = supabase_client.from_("teams").select("team_name").eq("team_id", away_team_id).execute()
        if away_team_response.data:
            match_data["away_team"] = away_team_response.data[0].get("team_name")
        else:
            match_data["away_team"] = "Unknown Away Team"

        league_id = match_data.get("league_id")
        league_response = supabase_client.from_("leagues").select("league").eq("league_id", league_id).execute()
        if league_response.data:
            match_data["league_name"] = league_response.data[0].get("league")
        return match_data
    except Exception as e:
        st.error(f"Error fetching match by ID: {str(e)}")
        return None

supabase_client = None
if supabase_url and supabase_key:
    try:
        supabase_client = init_supabase(supabase_url, supabase_key)
    except Exception as e:
        st.sidebar.error(f"Failed to connect to Supabase: {e}")

st.title("⚽ TipsterHeroes.AI - Football Match Analysis")
st.markdown("AI-powered football news analysis for match predictions and betting insights")

# Initialize session states for UI components
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "chat_bot" not in st.session_state:
    st.session_state.chat_bot = None

if "match_from_url" not in st.session_state:
    st.session_state.match_from_url = None # To store match data found from URL param

# Function to generate analysis (remains mostly the same, but triggers are external)
def generate_analysis_conversational(home_team, away_team, league, match_date):
    """Generate analysis for the specified match using a conversational approach"""
    try:
        log_debug(f"Starting generate_analysis_conversational for {home_team} vs {away_team}")
        match_details = f"{home_team} vs {away_team}"
        # Ensure league is not None before formatting
        league_display = league if league else "Unknown League"
        full_query = f"{match_details} {league_display} {match_date.strftime('%d %B %Y')}"

        # Check if analysis already exists in DB
        existing_analysis_loaded = False
        if supabase_client:
            exists, analysis_id = check_analysis_exists(supabase_client, home_team, away_team, match_date)
            if exists:
                log_debug(f"Found existing analysis ID: {analysis_id}")
                analysis_data = get_analysis_by_id(supabase_client, analysis_id)
                if analysis_data:
                    parsed_content = parse_wordpress_analysis(analysis_data.get("content", ""))
                    results = {
                        "source_type": "db",
                        "combined_analysis": parsed_content,
                        "original_html": analysis_data.get("content", ""), # Store original HTML
                        "betting_insights": extract_betting_insights(parsed_content) # Extract insights from parsed content
                    }
                    st.session_state.results = results
                    st.session_state.match_info = {"match": match_details, "league": league_display, "date": match_date}
                    st.session_state.analysis_in_progress = False # Mark as complete
                    existing_analysis_loaded = True
                    log_debug(f"Existing analysis loaded for {home_team} vs {away_team}")
                    # Add a message to the chat history indicating analysis loaded
                    add_analysis_message("assistant", f"Analysis loaded successfully for {match_details}!")
                    # No need to rerun here, the UI state updates will cause the display

        if not existing_analysis_loaded:
            # If no existing analysis or not using DB, proceed with news/DB analysis
            st.session_state.analysis_in_progress = True # Set flag while working (handled by status context)

            results = {}
            db_insights = None
            news_results = None

            # Database analysis (if enabled)
            if use_database and supabase_client:
                with st.status("Processing database information...", expanded=True) as status:
                    status.write("🔍 Retrieving match data...")
                    match_data = get_match_with_bets(supabase_client, home_team, away_team, closest_to_date=match_date)

                    if not match_data:
                         # Create a basic match data structure if not found in main query
                         match_data = {
                             'home_team': home_team,
                             'away_team': away_team,
                             'match_date': match_date.strftime('%Y-%m-%d'),
                             'league_name': league_display
                         }
                         log_debug("Match data not found in DB, using provided details.")

                    status.write("📊 Retrieving team statistics...")
                    team1_data = get_team_stats(supabase_client, home_team)
                    team2_data = get_team_stats(supabase_client, away_team)

                    status.write("🏆 Retrieving league standings...")
                    league_data = get_league_standings(supabase_client, league_display)

                    status.write("🧠 Analyzing database information...")
                    db_insights = agents.process_database_insights(
                        match_data=match_data,
                        team1_data=team1_data or {"team_name": home_team, "note": "Limited statistics available"},
                        team2_data=team2_data or {"team_name": away_team, "note": "Limited statistics available"},
                        head_to_head_data=None, # Assuming H2H is not yet fully integrated
                        league_data=league_data
                    )
                    status.update(label="Database analysis complete!", state="complete")
                results["db_insights"] = db_insights

            # News-based analysis (if enabled)
            if use_news:
                with st.status("Searching and analyzing news...", expanded=True) as status:
                     status.write(f"📰 Searching for news about {full_query}...")
                     news_results = agents.process_football_news(full_query)
                     status.update(label="News analysis complete!", state="complete")
                results.update(news_results)


            # Combine analyses if both are available
            if db_insights and news_results:
                with st.status("Combining analysis...", expanded=True) as status:
                    combined_analysis = agents.combine_analysis_with_database(news_results, db_insights)
                    results["combined_analysis"] = combined_analysis
                    status.update(label="Combined analysis complete!", state="complete")
            elif db_insights:
                 # Only database analysis available
                 results["combined_analysis"] = db_insights # Use DB insights as the main analysis if no news
                 results["enhanced_analysis"] = db_insights
                 results["initial_analysis"] = "Analysis based on database statistics only."
                 results["synthesized_news"] = "No news analysis performed."
                 results["raw_news"] = "No news search performed."
            elif news_results:
                 # Only news analysis available (results already contains news_results)
                 results["combined_analysis"] = news_results.get("enhanced_analysis", news_results.get("initial_analysis", "No analysis generated."))

            # Extract betting insights if available (from combined or db insights)
            if "combined_analysis" in results:
                 results["betting_insights"] = extract_betting_insights(results["combined_analysis"])
            elif "db_insights" in results:
                 results["betting_insights"] = extract_betting_insights(results["db_insights"])
            else:
                 results["betting_insights"] = {}


            st.session_state.results = results
            st.session_state.match_info = {"match": match_details, "league": league_display, "date": match_date}

            # Save analysis to WordPress format in Supabase if connected and new analysis was generated
            if supabase_client and (db_insights or news_results):
                save_success, blog_id = save_analysis_for_wordpress(supabase_client, st.session_state.match_info, results)
                if save_success:
                    st.sidebar.success(f"Analysis saved for WordPress (ID: {blog_id})", icon="✅")

            # Initialize chat context
            analysis_for_context = results.get("combined_analysis", results.get("enhanced_analysis", results.get("db_insights", "")))
            st.session_state.chat_context = f"""
            MATCH: {full_query}

            ANALYSIS:
            {analysis_for_context}
            """
            if "db_insights" in results and "combined_analysis" not in results: # Add DB insights specifically if not part of combined
                 st.session_state.chat_context += f"\n\nDATABASE INSIGHTS:\n{results['db_insights']}"

            # Add an initial message to the chat history
            add_analysis_message("assistant", f"Analysis generated successfully for {match_details}!")

            st.session_state.analysis_in_progress = False # Mark analysis as complete

        log_debug(f"Analysis process finished for {home_team} vs {away_team}. Loaded existing: {existing_analysis_loaded}")

    except Exception as e:
        st.error(f"An error occurred during analysis: {str(e)}")
        st.error(traceback.format_exc())
        st.session_state.analysis_in_progress = False
        log_debug(f"Error in generate_analysis_conversational: {str(e)}")
        add_analysis_message("assistant", f"An error occurred while generating the analysis: {e}")


# --- Analysis Execution Block ---
# This block runs AT THE TOP of the script on every rerun
# It checks the 'start_analysis' flag and performs the analysis if needed.
if st.session_state.get("start_analysis", False) and "match_to_analyze" in st.session_state and not st.session_state.get("analysis_in_progress", False):
    log_debug(f"Analysis trigger detected. state: {st.session_state.start_analysis}, match: {st.session_state.match_to_analyze.get('home_team')} vs {st.session_state.match_to_analyze.get('away_team')}")

    match_info = st.session_state.match_to_analyze

    # Clear the flag *before* starting the potentially long analysis
    st.session_state.start_analysis = False

    # Prepare analysis environment
    st.session_state.chat_history = [] # Clear chat for new analysis
    st.session_state.analysis_in_progress = True # Set flag that analysis is running
    st.session_state.analysis_chat = [] # Clear internal analysis chat messages if used
    st.session_state.results = None # Clear previous results
    st.session_state.match_info = None # Clear previous match info
    # The function itself will populate match_info and results when done

    # Store the URL origin if it was from URL
    if match_info.get("from_url", False):
        st.session_state.from_url_analysis = True

    # Start the analysis
    generate_analysis_conversational(
        match_info["home_team"],
        match_info["away_team"],
        match_info["league"],
        match_info["match_date"]
    )

    # Rerun is handled implicitly by st.status or at the end of the script execution
    # Adding an explicit rerun here might cause infinite loops if the analysis
    # function doesn't clear the flag properly. Let's rely on the flag and the
    # natural Streamlit render cycle after the function completes.
    # If issues persist, re-add st.rerun() here.

# --- URL Parameter Processing Block ---
# This block runs after the analysis trigger block but before rendering UI.
# It fetches match data from URL if present and not processed, and may set
# 'start_analysis' if auto_analyze is true.
if supabase_client and st.session_state.url_match_id and not st.session_state.get("url_params_processed", False):
    log_debug(f"Processing URL parameter match_id: {st.session_state.url_match_id}")
    match_data = get_match_by_id(supabase_client, st.session_state.url_match_id)

    # Mark params as processed regardless of whether match was found
    st.session_state.url_params_processed = True

    if match_data:
        log_debug(f"Match found from URL ID {st.session_state.url_match_id}: {match_data.get('home_team')} vs {match_data.get('away_team')}")
        # Store the match data found from the URL
        st.session_state.match_from_url = match_data

        # Auto-analyze if requested in URL and analysis hasn't been triggered yet
        if st.session_state.url_auto_analyze and not st.session_state.get("analysis_triggered", False):
            log_debug(f"Auto-analyze triggered from URL for {match_data.get('home_team')} vs {match_data.get('away_team')}")
            st.session_state.match_to_analyze = st.session_state.match_from_url # Use the pre-fetched data
            st.session_state.in_analysis_mode = True
            st.session_state.start_analysis = True # Set the flag for the analysis execution block
            st.session_state.analysis_triggered = True # Prevent re-triggering from URL params
            # NO direct call to generate_analysis_conversational here
            st.rerun() # Trigger the analysis execution block
        # If auto_analyze is False, match_from_url is set, and the UI will handle displaying it with a button.

    else:
        st.sidebar.warning(f"No match found in database with ID: {st.session_state.url_match_id}")


# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("Configure your match analysis parameters")

    if supabase_client:
        st.sidebar.success("Connected to Supabase")
    else:
        st.sidebar.error("Not connected to Supabase. Database features disabled.")

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

    # Additional analysis options (Currently just for display/future use in prompt)
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
    memory = None
    if openai_api_key:
        st.subheader("Memory Options")
        enable_memory = st.checkbox("Enable Persistent Memory", value=False, help="Requires OpenAI API Key")
        if enable_memory:
            try:
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
                                    except Exception as e_parse:
                                        st.write(f"- {mem['memory']}")
                                        st.write(f"(Error parsing memory: {e_parse})")
                                else:
                                     st.write(f"- Raw Memory: {mem}")
                        else:
                            st.info("No memory history found for this user ID.")
                    except Exception as e:
                        st.error(f"Error retrieving memories: {str(e)}")
            except Exception as e:
                 st.warning(f"Failed to initialize memory: {e}")
                 enable_memory = False # Disable memory if initialization failed
        elif chat_method == "Memory-Enhanced":
             st.warning("Memory-Enhanced chat requires Persistent Memory to be enabled and a valid API key.")
             chat_method = "Direct Agent" # Fallback

    elif chat_method in ["Embedchain", "Memory-Enhanced"]:
         st.warning(f"Chat method '{chat_method}' requires an OpenAI API Key.")
         chat_method = "Direct Agent" # Fallback

    # Debug log viewer
    if st.checkbox("Show Debug Log"):
        st.subheader("Debug Log")
        for log in st.session_state.debug_logs:
            st.text(log)
        if st.button("Clear Debug Log"):
            st.session_state.debug_logs = []

        # Also show session state (filtered)
        with st.expander("Session State"):
            filtered_state = {}
            for key, value in st.session_state.items():
                if key in ['debug_logs', 'results', 'chat_history', 'chat_context', 'chat_bot', 'analysis_chat']:
                    # Attempt to represent large objects without dumping everything
                    if isinstance(value, list):
                        filtered_state[key] = f"[{type(value).__name__} - {len(value)} items]"
                    elif isinstance(value, dict):
                         filtered_state[key] = f"[{type(value).__name__} - {len(value)} keys]"
                    else:
                         filtered_state[key] = f"[{type(value).__name__} - object too large?]"

                else:
                    filtered_state[key] = value
            st.json(filtered_state)


# Main content area
col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Match Details")

    in_analysis = st.session_state.get("in_analysis_mode", False)
    log_debug(f"Rendering col1 - in_analysis: {in_analysis}")

    if in_analysis:
        # Display current analysis info
        if "match_info" in st.session_state and st.session_state.get("analysis_in_progress", False):
             # Show spinner/status only while analysis is truly in progress
             st.info("Analysis in progress... Please wait.")
             match_info = st.session_state.match_info
             st.markdown(f"### {match_info.get('match')}")
             st.write(f"**League:** {match_info.get('league')}")
             st.write(f"**Date:** {match_info.get('date').strftime('%d %B %Y')}")

        elif "match_info" in st.session_state and not st.session_state.get("analysis_in_progress", False):
            # Analysis complete, show info and button to select new match
            match_info = st.session_state.match_info
            st.success("Analysis complete!")
            st.markdown(f"### {match_info.get('match')}")
            st.write(f"**League:** {match_info.get('league')}")
            st.write(f"**Date:** {match_info.get('date').strftime('%d %B %Y')}")

            if st.button("Select Different Match", type="secondary", use_container_width=True):
                log_debug("Select Different Match button clicked")
                # Reset all analysis-related state
                st.session_state.in_analysis_mode = False
                st.session_state.from_url_analysis = False
                st.session_state.analysis_in_progress = False
                st.session_state.start_analysis = False
                st.session_state.analysis_triggered = False
                st.session_state.match_to_analyze = None
                st.session_state.results = None
                st.session_state.match_info = None
                st.session_state.chat_history = [] # Clear chat on new selection
                st.session_state.chat_context = None
                st.session_state.match_from_url = None # Clear URL match info
                # Re-process URL parameters on rerun to handle back button/re-opening same URL
                st.session_state.url_params_processed = False
                st.rerun() # Force page reload

        else:
             st.info("Waiting for analysis to start...") # Should not happen often if state is correct

    else: # Not in analysis mode - show selection UI

        # --- Handle and display match from URL if available and not yet analyzed ---
        # Check if match_from_url exists AND we haven't triggered analysis for it yet
        if supabase_client and st.session_state.get("match_from_url") and not st.session_state.get("analysis_triggered", False):
            match_data_url = st.session_state.match_from_url

            st.success("Match found from URL parameter!")
            st.markdown(f"### {match_data_url.get('home_team', 'Unknown')} vs {match_data_url.get('away_team', 'Unknown')}")
            col_a, col_b = st.columns(2)
            with col_a:
                 # Use get_country_name_by_id helper if available
                 country_name = get_country_name_by_id(supabase_client, match_data_url.get("country_id")) if supabase_client else "Unknown"
                 st.write(f"**Country:** {country_name}")
                 st.write(f"**League:** {match_data_url.get('league_name', 'Unknown League')}")
            with col_b:
                 # Ensure match_date is a date object before formatting
                 match_date_obj = match_data_url.get('match_date')
                 if isinstance(match_date_obj, str):
                      try:
                           match_date_obj = datetime.strptime(match_date_obj, '%Y-%m-%d').date()
                      except:
                           match_date_obj = datetime.now().date()

                 if isinstance(match_date_obj, datetime) or isinstance(match_date_obj, datetime.date):
                      st.write(f"**Date:** {match_date_obj.strftime('%d %B %Y')}")
                 else:
                      st.write(f"**Date:** Unknown")

            # Button to trigger analysis for the URL match
            if st.button("Analyze This Match", type="primary", use_container_width=True, key="analyze_url_match_button"):
                log_debug(f"Analyze This Match button (from URL) clicked for {match_data_url.get('home_team')} vs {match_data_url.get('away_team')}")
                # Store match info to analyze
                st.session_state.match_to_analyze = match_data_url # Use the data already fetched
                st.session_state.in_analysis_mode = True
                st.session_state.start_analysis = True # Set the flag for the analysis trigger block
                st.session_state.analysis_triggered = True # Mark as triggered for this URL match
                st.rerun() # Trigger analysis on next run

        else: # Show normal selection (database or manual)
            log_debug("Showing normal selection UI")
            # --- Database Selection (if enabled and connected) ---
            if supabase_client and use_database:
                st.write("📊 Select from Database or Enter Manually")

                try:
                    countries_data = supabase_client.from_("countries").select("country_id, country").execute()
                    country_dict = {c["country_id"]: c["country"] for c in countries_data.data if c.get("country_id")}

                    if country_dict:
                        selected_country_name = st.selectbox("Filter by Country", sorted(country_dict.values()), key="country_select")
                        selected_country_id = [k for k, v in country_dict.items() if v == selected_country_name][0] # Assuming unique names

                        leagues_data = supabase_client.from_("leagues").select("league_id, league").eq("country_id", selected_country_id).execute()
                        league_options = {"All Leagues": None}
                        league_options.update({f"{item['league']}": item['league_id'] for item in leagues_data.data})
                        selected_league_display = st.selectbox("Filter by League", list(league_options.keys()), key="league_select")
                        league_filter_value = league_options[selected_league_display]

                        matches_df = get_matches(supabase_client, league=league_filter_value)

                        if not matches_df.empty:
                            match_options = ["Select a match..."] + [
                                f"{row['home_team']} vs {row['away_team']} ({row['match_date']})"
                                for _, row in matches_df.iterrows()
                            ]

                            selected_match_display = st.selectbox("Select Match from Database", match_options, key="match_select_db")

                            # If a match is selected from database dropdown
                            if selected_match_display != "Select a match...":
                                # Find the selected row in the dataframe
                                selected_match_row = matches_df[matches_df.apply(lambda row: f"{row['home_team']} vs {row['away_team']} ({row['match_date']})" == selected_match_display, axis=1)].iloc[0]

                                home_team_db = selected_match_row['home_team']
                                away_team_db = selected_match_row['away_team']
                                match_date_str_db = selected_match_row['match_date']
                                league_name_db = selected_match_row.get('league_name', selected_league_display) # Prefer league_name if available

                                try:
                                    match_date_db = datetime.strptime(match_date_str_db, '%Y-%m-%d').date()
                                except:
                                     match_date_db = datetime.now().date() # Fallback

                                # Display form with pre-filled values
                                with st.form("db_match_details_form"): # Use a unique key for the form
                                    st.write(f"Selected: **{home_team_db} vs {away_team_db}**")
                                    #league = selected_league_display # Keep league from dropdown
                                    match_date_input_db = st.date_input("Match Date", value=match_date_db, key="date_input_db") # Allow date override

                                    submit_button_db = st.form_submit_button("Start Analysis", type="primary", use_container_width=True)

                                    if submit_button_db:
                                        log_debug(f"Database selection form submitted for {home_team_db} vs {away_team_db}")
                                        # Store analysis parameters in session state
                                        st.session_state.match_to_analyze = {
                                            "home_team": home_team_db,
                                            "away_team": away_team_db,
                                            "league": league_name_db, # Use league name
                                            "match_date": match_date_input_db # Use date from input
                                        }
                                        # Set flags to trigger analysis on next rerun
                                        st.session_state.in_analysis_mode = True
                                        st.session_state.start_analysis = True
                                        st.session_state.analysis_triggered = True # Mark as triggered
                                        st.rerun()

                        else:
                             st.info(f"No matches found for '{selected_league_display}' in {selected_country_name}. Enter match details manually.")
                             manual_input_fallback = True
                    else:
                        st.warning("No countries available in the database.")
                        manual_input_fallback = True
                except Exception as e:
                    st.error(f"Error loading data from database: {str(e)}")
                    st.error(traceback.format_exc())
                    manual_input_fallback = True

            # --- Manual Input Mode (fallback if DB is off or fails) ---
            # Only show manual input if database is not used or failed, AND we are not showing the URL match details.
            if not use_database or supabase_client is None or ('manual_input_fallback' in locals() and manual_input_fallback):
                st.write("✍️ Enter Match Details Manually")
                match_details = st.text_input(
                    "Enter team names (e.g., 'Team A vs Team B'):",
                    value="Manchester United vs Liverpool",
                    help="Enter team names in 'Home Team vs Away Team' format.",
                    key="manual_match_details"
                )

                league = st.selectbox(
                    "League",
                    ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"],
                    key="manual_league"
                )

                match_date = st.date_input("Match Date", key="manual_date")

                if st.button("Generate Analysis", type="primary", use_container_width=True):
                    if match_details and " vs " in match_details:
                        teams = match_details.split(" vs ")
                        if len(teams) == 2:
                            home_team_manual = teams[0].strip()
                            away_team_manual = teams[1].strip()

                            log_debug(f"Manual input button clicked for {home_team_manual} vs {away_team_manual}")
                            # Store analysis parameters
                            st.session_state.match_to_analyze = {
                                "home_team": home_team_manual,
                                "away_team": away_team_manual,
                                "league": league,
                                "match_date": match_date
                            }
                            # Set flags to trigger analysis on next rerun
                            st.session_state.in_analysis_mode = True
                            st.session_state.start_analysis = True
                            st.session_state.analysis_triggered = True # Mark as triggered
                            st.rerun()
                        else:
                            st.error("Please enter match details in the format 'Home Team vs Away Team'")
                    else:
                        st.error("Please enter match details in the format 'Home Team vs Away Team'!")


# Results area
with col2:
    # The chat and results display logic should only appear if we are in analysis mode
    if st.session_state.get("in_analysis_mode", False):
        st.subheader("⚽ Match Analysis Chat")

        # Display match info caption once analysis info is available
        if "match_info" in st.session_state:
            match_info = st.session_state.match_info
            st.caption(f"{match_info['match']} | {match_info['league']} | {match_info['date'].strftime('%d %B %Y')}")

        # Use tabs for Analysis and Betting, but keep Chat outside the tabs
        if "results" in st.session_state and not st.session_state.get("analysis_in_progress", False):
             # Only show tabs when analysis is complete and results are available
            tab2, tab3 = st.tabs(["Analysis", "Betting"]) # Removed Chat tab as it's below

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
                if "results" in st.session_state and "betting_insights" in st.session_state.results:
                     betting_insights = st.session_state.results["betting_insights"]
                     if betting_insights:
                          import pandas as pd
                          # Convert dict to list of dicts for DataFrame
                          bet_data = []
                          for bet_type, bet_info in betting_insights.items():
                              bet_data.append({
                                   "Bet Type": bet_type,
                                   "Odds": bet_info.get("odds", "-"),
                                   "Consensus": bet_info.get('consensus', 0),
                                   "EV": bet_info.get('ev', 0),
                                   "Tier": bet_info.get("tier", "-")
                              })

                          if bet_data:
                               # Sort by tier and then EV (descending for EV)
                               tier_map = {"A": 1, "B": 2, "C": 3, "D": 4}
                               for bd in bet_data:
                                    bd["tier_sort"] = tier_map.get(bd.get("Tier"), 10) # Unknown tiers at the end

                               bet_df = pd.DataFrame(bet_data)
                               bet_df = bet_df.sort_values(by=["tier_sort", "EV"], ascending=[True, False])
                               bet_df = bet_df.drop("tier_sort", axis=1)

                               st.dataframe(bet_df, use_container_width=True)

                               # Display top recommendations separately
                               top_bets = [b for b in bet_data if b.get("Tier") in ["A", "B"]]
                               if top_bets:
                                    st.subheader("Top Recommended Bets")
                                    # Sort top bets again for consistent display
                                    top_bets_sorted = sorted(top_bets, key=lambda x: (tier_map.get(x.get("Tier"), 10), -x.get("EV", 0)))
                                    for i, bet in enumerate(top_bets_sorted[:3]): # Show top 3
                                        with st.container(border=True):
                                             st.markdown(f"### {i+1}. {bet['Bet Type']}")
                                             cols = st.columns(3)
                                             with cols[0]:
                                                  st.metric("Odds", bet["Odds"])
                                             with cols[1]:
                                                  st.metric("Expected Value", f"{bet['EV']:.2f}") # Format EV
                                             with cols[2]:
                                                  st.metric("Tier", bet["Tier"])
                               else:
                                    st.info("No A or B tier bets found for this match.")

                          else:
                               st.info("No betting data available in the analysis.")
                     else:
                         st.info("No betting insights were extracted from the analysis.")
                elif supabase_client and use_database and "match_info" in st.session_state:
                     # Fallback: if analysis didn't extract bets, try fetching directly if DB is available
                     st.info("Attempting to fetch direct betting data from database...")
                     match_info = st.session_state.match_info
                     if "match" in match_info:
                         teams = match_info["match"].split(" vs ")
                         if len(teams) == 2:
                             home_team_f = teams[0].strip()
                             away_team_f = teams[1].strip()
                             try:
                                 match_with_bets = get_match_with_bets(supabase_client, home_team_f, away_team_f,
                                                                   closest_to_date=match_info["date"])
                                 if match_with_bets and match_with_bets.get("has_bets", False):
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
                                          tier_map = {"A": 1, "B": 2, "C": 3, "D": 4}
                                          for bd in bet_data:
                                               bd["tier_sort"] = tier_map.get(bd.get("Tier"), 10) # Unknown tiers at the end

                                          bet_df = pd.DataFrame(bet_data)
                                          bet_df = bet_df.sort_values(by=["tier_sort", "EV"], ascending=[True, False])
                                          bet_df = bet_df.drop("tier_sort", axis=1)
                                          st.dataframe(bet_df, use_container_width=True)

                                          top_bets = [b for b in bet_data if b.get("Tier") in ["A", "B"]]
                                          if top_bets:
                                               st.subheader("Top Recommended Bets")
                                               top_bets_sorted = sorted(top_bets, key=lambda x: (tier_map.get(x.get("Tier"), 10), -x.get("EV", 0)))
                                               for i, bet in enumerate(top_bets_sorted[:3]):
                                                   with st.container(border=True):
                                                       st.markdown(f"### {i+1}. {bet['Bet Type']}")
                                                       cols = st.columns(3)
                                                       with cols[0]:
                                                            st.metric("Odds", bet["Odds"])
                                                       with cols[1]:
                                                            st.metric("Expected Value", f"{bet['EV']:.2f}")
                                                       with cols[2]:
                                                            st.metric("Tier", bet["Tier"])
                                          else:
                                               st.info("No A or B tier bets found for this match.")
                                      else:
                                           st.info("No betting data found in the database for this match.")
                                 else:
                                     st.info("No betting data available for this match in the database.")
                             except Exception as e:
                                 st.error(f"Error fetching betting data from DB: {e}")

                         else:
                             st.warning("Could not parse team names to fetch betting data.")
                else:
                    st.info("Connect to Supabase and include database statistics to view betting information.")


        # --- Chat Interface ---
        # Display chat messages
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input - only show if analysis is complete and not in progress
        if not st.session_state.get("analysis_in_progress", False):
            if chat_prompt := st.chat_input("Ask about the match analysis..."):
                # Add user message to chat history
                st.session_state.chat_history.append({"role": "user", "content": chat_prompt})

                # Display user message
                with st.chat_message("user"):
                    st.write(chat_prompt)

                # Generate and display response
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        response = "Sorry, I cannot process that request right now. Please try again later." # Default response in case of issues

                        if chat_method == "Embedchain" and "chat_bot" in st.session_state and st.session_state.chat_bot:
                            try:
                                response = st.session_state.chat_bot.chat(chat_prompt)
                            except Exception as e:
                                response = f"Error using Embedchain: {e}"
                                log_debug(f"Embedchain chat error: {e}")

                        elif chat_method == "Memory-Enhanced" and memory and openai_api_key and "chat_context" in st.session_state:
                            try:
                                # Get relevant memories
                                relevant_memories = get_relevant_memories(memory, user_id, chat_prompt, st.session_state.get("match_info", {}))

                                # Create memory context string
                                memory_context = ""
                                if relevant_memories:
                                    memory_context = "Based on our previous conversations:\n"
                                    # Limit to top 3 memories for prompt length management
                                    for i, mem in enumerate(relevant_memories[:3]):
                                        mem_content = json.loads(mem.get('memory', '{}')).get('response', mem.get('response', '')) # Get response from memory JSON or directly
                                        memory_context += f"- User asked about '{json.loads(mem.get('memory', '{}')).get('query', mem.get('query', ''))}': Assistant replied '{mem_content[:100]}...'\n" # Truncate memory content for context

                                # Enhanced analysis context with memory
                                enhanced_context = f"{st.session_state.chat_context}\n\nMEMORY CONTEXT:\n{memory_context}"

                                # Get response with memory-enhanced context
                                response = agents.chat_with_analysis(
                                    chat_prompt,
                                    enhanced_context,
                                    # Pass relevant parts of results if needed by agent
                                    scraped_content=st.session_state.results.get("scraped_content", {}),
                                    db_insights=st.session_state.results.get("db_insights", ""),
                                    betting_insights=st.session_state.results.get("betting_insights", {}),
                                    chat_history=st.session_state.chat_history[:-1] # Pass conversation history excluding current user prompt
                                )

                                # Save interaction to memory (only if successful and memory is enabled)
                                if memory and user_id != "default_user": # Don't save for default user
                                     memory_saved = save_chat_to_memory(memory, user_id, st.session_state.get("match_info", {}), chat_prompt, response)
                                     if memory_saved:
                                          st.sidebar.success("Interaction saved to memory", icon="✅")
                                     else:
                                          st.sidebar.warning("Failed to save interaction to memory.")

                            except Exception as e:
                                response = f"Error using Memory-Enhanced chat: {e}"
                                log_debug(f"Memory-Enhanced chat error: {e}")
                                st.error(f"Memory chat error: {e}")
                                st.error(traceback.format_exc())


                        elif chat_method == "Direct Agent" and "chat_context" in st.session_state:
                             try:
                                 response = agents.chat_with_analysis(
                                     chat_prompt,
                                     st.session_state.chat_context,
                                     # Pass relevant parts of results if needed by agent
                                     scraped_content=st.session_state.results.get("scraped_content", {}),
                                     db_insights=st.session_state.results.get("db_insights", ""),
                                     betting_insights=st.session_state.results.get("betting_insights", {}),
                                     chat_history=st.session_state.chat_history[:-1] # Pass conversation history
                                 )
                             except Exception as e:
                                 response = f"Error using Direct Agent chat: {e}"
                                 log_debug(f"Direct Agent chat error: {e}")
                                 st.error(f"Direct chat error: {e}")
                                 st.error(traceback.format_exc())

                        else:
                            response = "Please generate an analysis first to start the chat."
                            if (chat_method == "Embedchain" or chat_method == "Memory-Enhanced") and not openai_api_key:
                                response += " Also ensure API key is provided for Embedchain or Memory-Enhanced modes."

                    st.write(response)

                # Add assistant response to chat history
                st.session_state.chat_history.append({"role": "assistant", "content": response})
        elif st.session_state.get("analysis_in_progress", False):
            st.info("Analysis is currently in progress. Chat will be available once it's complete.")
        else:
             st.info("Enter match details and click 'Generate Analysis' or 'Start Analysis' to see results and start the chat here.")


        # Clear chat button (only show if there's chat history)
        if "chat_history" in st.session_state and len(st.session_state.chat_history) > 0:
            if st.button("Clear Chat History"):
                log_debug("Clear Chat History button clicked")
                st.session_state.chat_history = []
                # Keep analysis results, just clear conversation
                st.rerun()

    else:
        st.info("Select a match on the left to start the analysis.")


# Footer
st.markdown("---")
st.markdown("ⓒ TipsterHeroes.AI - Powered by data. Sharpened by edge.")
