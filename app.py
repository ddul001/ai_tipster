"""
Main application file for TipsterHeroes.AI - Football Match Analysis
Handles UI components and orchestrates the workflow between agents and data services.
"""
# THIS MUST BE THE FIRST STREAMLIT COMMAND IN YOUR FILE
import streamlit as st

st.set_page_config(
    page_title="AI Tipster",
    page_icon="⚽",
    initial_sidebar_state="collapsed",  # or "expanded", "auto"
    layout="wide"
)


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
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error(traceback.format_exc())

def generate_analysis_conversational(home_team, away_team, league, match_date):
    """Generate analysis for the specified match using a conversational approach"""
    try:
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

        results = agents.process_football_news(full_query)

        db_insights = None
        if use_database and supabase_client:
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

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error(traceback.format_exc())
        st.session_state.analysis_in_progress = False

# def generate_analysis_conversational(home_team, away_team, league, match_date):
#     """Generate analysis for the specified match using a conversational approach"""
#     try:
#         match_details = f"{home_team} vs {away_team}"
#         full_query = f"{match_details} {league} {match_date.strftime('%d %B %Y')}"

#         print("full_query", full_query)
        
#         # Initialize chat if not present
#         if "analysis_chat" not in st.session_state:
#             st.session_state.analysis_chat = []
            
#         # Set analysis in progress flag
#         st.session_state.analysis_in_progress = True
            
#         # Send welcome message
#         add_analysis_message("assistant", f"I'll analyze the upcoming match between {home_team} and {away_team}. Let me gather the information we need!", animate=True)
        
#         # Set up early chat context with basic match info
#         early_context = f"""
#         MATCH: {match_details}
#         LEAGUE: {league}
#         DATE: {match_date.strftime('%d %B %Y')}
        
#         ANALYSIS: Currently being generated. Basic questions about these teams can be answered.
#         """
        
#         # Initialize chat bot early with limited context
#         st.session_state.chat_context = early_context
#         setup_chat_with_context({"initial_analysis": early_context}, full_query, chat_method, openai_api_key)
        

#         # Check if analysis already exists
#         if supabase_client:
#             add_analysis_message("assistant", "First, let me check if I've already analyzed this match before...")
            
#             exists, analysis_id = check_analysis_exists(supabase_client, home_team, away_team, match_date)
#             if exists:
#                 add_analysis_message("assistant", f"Good news! I've already analyzed this match. Let me load that analysis for you.")
                
#                 analysis_data = get_analysis_by_id(supabase_client, analysis_id)
#                 if analysis_data:
#                     add_analysis_message("assistant", "Analysis loaded successfully! Here's what I found earlier.")
                    
#                     # Use raw_content if available, otherwise parse the HTML content
#                     if "raw_content" in analysis_data and analysis_data["raw_content"]:
#                         try:
#                             # Parse the JSON string into a dictionary
#                             results = json.loads(analysis_data["raw_content"])
#                             parsed_content = results.get("combined_analysis", "")
#                             # If parsed_content is empty, try to extract it from the original HTML
#                             if not parsed_content and "content" in analysis_data:
#                                 parsed_content = parse_wordpress_analysis(analysis_data["content"])
#                                 results["combined_analysis"] = parsed_content
#                         except json.JSONDecodeError:
#                             # Fallback to parsing HTML if JSON parsing fails
#                             content = analysis_data.get("content", "")
#                             parsed_content = parse_wordpress_analysis(content)
                            
#                             # Extract betting insights if available
#                             betting_insights = extract_betting_insights(parsed_content)
                            
#                             # Create results dictionary
#                             results = {
#                                 "combined_analysis": parsed_content,
#                                 "enhanced_analysis": parsed_content,
#                                 "initial_analysis": "Loaded from database",
#                                 "synthesized_news": "Loaded from database",
#                                 "raw_news": "Loaded from database",
#                                 "original_html": content,
#                                 "betting_insights": betting_insights
#                             }
#                     else:
#                         # Fallback to the old method if raw_content is not available
#                         content = analysis_data.get("content", "")
#                         parsed_content = parse_wordpress_analysis(content)
                        
#                         # Extract betting insights if available
#                         betting_insights = extract_betting_insights(parsed_content)
                        
#                         # Convert stored analysis to results format
#                         results = {
#                             "combined_analysis": parsed_content,
#                             "enhanced_analysis": parsed_content,
#                             "initial_analysis": "Loaded from database",
#                             "synthesized_news": "Loaded from database",
#                             "raw_news": "Loaded from database",
#                             "original_html": content,
#                             "betting_insights": betting_insights
#                         }
                    
#                     # Store results in session state
#                     st.session_state.results = results
#                     st.session_state.match_info = {
#                         "match": match_details,
#                         "league": league,
#                         "date": match_date
#                     }
                    
#                     add_analysis_message("assistant", "You can now explore the detailed results in the tabs above, or chat with me if you have any questions about my findings.")
#                     st.session_state.analysis_in_progress = False
#                     # Initialize chatbot for follow-up questions
#                     setup_chat_with_context(results, full_query, chat_method, openai_api_key)

#                     return
                    
#             else:
#                 add_analysis_message("assistant", "This looks like a new analysis! Let me get started.")
        
#         # Initialize the result container
#         results = {}
        
#         # Flag to track if we need to run news analysis
#         run_news_analysis = use_news
        
#         # Flag to track if we need database analysis
#         run_db_analysis = use_database and supabase_client
        
#         # Database analysis
#         db_insights = None
#         if run_db_analysis:
#             add_analysis_message("assistant", f"I'll first look at the statistics for both teams...")
            
#             # Get match data
#             add_analysis_message("assistant", f"Searching for previous matches between these teams...")
#             match_data = get_match_with_bets(supabase_client, home_team, away_team, closest_to_date=match_date)
            
#             if match_data:
#                 add_analysis_message("assistant", f"Found {home_team} vs {away_team} match history! Let me analyze that data.")
#             else:
#                 add_analysis_message("assistant", f"These teams don't appear to have played each other recently. I'll focus on their individual performances.")
#                 # Create a basic match data structure
#                 match_data = {
#                     'home_team': home_team,
#                     'away_team': away_team,
#                     'match_date': match_date.strftime('%Y-%m-%d'),
#                     'league_name': league
#                 }
            
#             # Get team statistics with conversational updates
#             add_analysis_message("assistant", f"Now checking {home_team}'s recent form and statistics...")
#             team1_data = get_team_stats(supabase_client, home_team)
#             if team1_data:
#                 # Extract a meaningful stat to comment on
#                 wins = team1_data.get("wins", "several")
#                 goals = team1_data.get("goals_scored", "a number of")
#                 add_analysis_message("assistant", f"{home_team} has won {wins} matches recently, scoring {goals} goals. Let me dig deeper into their performance metrics.")
            
#             add_analysis_message("assistant", f"Looking at {away_team}'s performance now...")
#             team2_data = get_team_stats(supabase_client, away_team)
#             if team2_data:
#                 # Extract a meaningful stat to comment on
#                 away_form = team2_data.get("wins_away", "decent")
#                 goals_conceded = team2_data.get("goals_conceded_away", "some")
#                 add_analysis_message("assistant", f"{away_team} has shown {away_form} away form. They've conceded {goals_conceded} goals on the road.")
            
#             # # Get head-to-head data with conversational comment
#             # add_analysis_message("assistant", f"Analyzing head-to-head matches between these teams...")
#             # h2h_data = get_head_to_head(supabase_client, home_team, away_team)
#             # if not h2h_data.empty:
#             #     h2h_count = len(h2h_data)
#             #     add_analysis_message("assistant", f"Found {h2h_count} previous encounters between these teams. This will provide valuable context!")
#             # else:
#             #     add_analysis_message("assistant", "I couldn't find many direct matches between these teams, but that's fine. I'll focus on their individual performances.")
            
#             # Get league standings with a conversational comment
#             add_analysis_message("assistant", f"Checking the {league} table to see where both teams stand...")
#             league_data = get_league_standings(supabase_client, league)
#             if not league_data.empty:
#                 add_analysis_message("assistant", f"Got the current standings! This will help us understand the importance of this match in the {league} context.")
            
#             # Generate database insights with conversational update
#             add_analysis_message("assistant", "Now I'll analyze all this statistical data to find key insights...")
#             db_insights = agents.process_database_insights(
#                 match_data, 
#                 team1_data or {"team_name": home_team, "note": "Limited statistics available"}, 
#                 team2_data or {"team_name": away_team, "note": "Limited statistics available"},
#                 #h2h_data,
#                 league_data
#             )
            
#             add_analysis_message("assistant", "Statistical analysis complete! I've found some interesting patterns.")
        
#         # News-based analysis with conversational updates
#         if run_news_analysis:
#             add_analysis_message("assistant", "Now I'll search for the latest news about this match. This will help us catch any recent developments...")
            
#             add_analysis_message("assistant", f"Searching for news about {match_details}...")
#             results = agents.process_football_news(full_query)
            
#             add_analysis_message("assistant", "Found some relevant news articles! I'm processing them to extract the most important information.")
        
#         # Combine analyses if both are available
#         if run_news_analysis and run_db_analysis and db_insights:
#             add_analysis_message("assistant", "I'm now combining statistical insights with the latest news to create a comprehensive analysis...")
#             combined_analysis = agents.combine_analysis_with_database(results, db_insights)
#             results["combined_analysis"] = combined_analysis
#             results["db_insights"] = db_insights
            
#             add_analysis_message("assistant", "Analysis complete! I've created a detailed report that combines statistical data with the latest news and expert insights.")
#         elif db_insights:
#             # Only database analysis available
#             add_analysis_message("assistant", "Based on the statistical data, I've prepared a comprehensive analysis...")
#             results["db_insights"] = db_insights
#             results["enhanced_analysis"] = db_insights  # Use db_insights as the main analysis
#             results["initial_analysis"] = "Analysis based on database statistics only."
#             results["synthesized_news"] = "No news analysis performed."
#             results["raw_news"] = "No news search performed."
#             results["combined_analysis"] = db_insights
        
#         # Store results in session state
#         st.session_state.results = results
#         st.session_state.match_info = {
#             "match": match_details,
#             "league": league,
#             "date": match_date
#         }

#         # Save analysis to WordPress with conversational update
#         if supabase_client:
#             add_analysis_message("assistant", "I'm saving this analysis to our database in WordPress-ready format...")
#             save_success, blog_id = save_analysis_for_wordpress(supabase_client, st.session_state.match_info, results)
#             if save_success:
#                 add_analysis_message("assistant", f"Analysis saved successfully! It's ready to be published to your WordPress site.")
        
#         st.session_state.analysis_in_progress = False

#         add_analysis_message("assistant", "Analysis complete! Here's what I found:")

#         # Add a summary of each analysis component as a separate message
#         if "combined_analysis" in results:
#             summary = summarize_analysis(results["combined_analysis"], 300)  # Limit to ~300 chars
#             add_analysis_message("assistant", f"**Combined Analysis**\n{summary}\n\n*Ask me for more details about this analysis.*")

#         if "db_insights" in results and results["db_insights"] != results.get("combined_analysis", ""):
#             summary = summarize_analysis(results["db_insights"], 300)
#             add_analysis_message("assistant", f"**Statistical Data**\n{summary}\n\n*Ask me about specific statistics or trends.*")

#         if "synthesized_news" in results and results["synthesized_news"] != "No news analysis performed.":
#             summary = summarize_analysis(results["synthesized_news"], 300)
#             add_analysis_message("assistant", f"**News Analysis**\n{summary}\n\n*Ask me about recent news and developments.*")

#         # Add a prompt for the user
#         add_analysis_message("assistant", "You can ask me specific questions about this match. For example:\n- What are the key players to watch?\n- How do their recent forms compare?\n- What betting angles look promising?\n- What's your prediction for the final score?")

#         # Initialize chatbot for follow-up questions
#         setup_chat_with_context(results, full_query, chat_method, openai_api_key)
    
#     except Exception as e:
#         st.error(f"An error occurred: {str(e)}")
#         st.error(traceback.format_exc())
#         add_analysis_message("assistant", "I encountered an error while generating the analysis. Please try again or check the error message for details.")

#         st.session_state.analysis_in_progress = False



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
    use_database = st.checkbox("Include Database Statistics", value=False, 
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

# Main content area
col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Match Details")
    
    # Option to select match from database if Supabase is connected
    if supabase_client and use_database:
        st.write("📊 Select from Database or Enter Manually")
        
        # Fetch distinct countries from 'countries' table
        countries_data = supabase_client.from_("countries").select("country_id, country").execute()
        country_dict = {c["country_id"]: c["country"] for c in countries_data.data if c.get("country_id")}
        
        if country_dict:
            selected_country_name = st.selectbox("Filter by Country", sorted(country_dict.values()))
            selected_country_id = [k for k, v in country_dict.items() if v == selected_country_name]
            if selected_country_id:
                selected_country_id = selected_country_id[0]

                # Replace these lines
                # Use the correct column names (league_id, league, country_id)
                leagues_data = supabase_client.from_("leagues").select("league_id, league").eq("country_id", selected_country_id).execute()

                # Create options dictionary with the correct column names
                league_options = {"All Leagues": None}
                league_options.update({f"{item['league']} (ID: {item['league_id']})": item['league_id'] for item in leagues_data.data})
                selected_league_display = st.selectbox("Filter by League", list(league_options.keys()))
                league_filter_value = league_options[selected_league_display]

        
        # Get matches from database
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
                        league = league_filter_value
                        # league = st.selectbox(
                        #     "League",
                        #     ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"],
                        #     index=["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"].index(selected_league)
                        #     if selected_league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "Other"] else 0
                        # )
                        match_date = st.date_input("Match Date", value=match_date)
                        
                        # Submit button
                        submit_button = st.form_submit_button("Start Chat", type="primary", use_container_width=True)
                        
                        if submit_button:
                            # Process the analysis
                            # Initialize chat history for the new analysis
                            st.session_state.chat_history = []
                            st.session_state.analysis_in_progress = True
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
                    st.session_state.analysis_in_progress = False
                    
                    # Call conversational analysis function
                    generate_analysis_conversational(home_team, away_team, league, match_date)


                else:
                    st.error("Please enter match details in the format 'Team A vs Team B'")
            else:
                st.error("Please enter match details!")

# Results area
# This is the modified section for the right column (col2)
# Replace your current col2 section with this code

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
                            
                            
                            print("----- Before chat_with_analysis call -----")
                            print("query:", chat_prompt)
                            print("analysis_context:", enhanced_context)
                            print("scraped_content:", st.session_state.results.get("scraped_content", {}))
                            print("chat_history:", st.session_state.chat_history[:-1])
                            print("---------------------------------------")


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