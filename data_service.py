"""
Data Services Module for TipsterHeroes.AI
Handles all data operations including Supabase integration, 
memory management, and data processing.
"""

import os
import json
import tempfile
from datetime import datetime
import pandas as pd
import streamlit as st
from mem0 import Memory
from embedchain import App
from supabase import create_client
from qdrant_client import QdrantClient

# Configuration constants
QDRANT_URL = "https://671b6b6a-bad5-48d4-94ad-58cf2f55a279.europe-west3-0.gcp.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.LZahtCo9JyddAJCOBVBIOoTwPonRhx8ZgtFB4AFpk5w"

def init_supabase(supabase_url, supabase_key):
    """Initialize and return Supabase client"""
    try:
        supabase = create_client(supabase_url, supabase_key)
        # Test connection with a simple query
        test_query = supabase.from_("teams").select("team_id").limit(1).execute()
        st.sidebar.success(f"Connected to Supabase successfully")
        return supabase
    except Exception as e:
        st.error(f"Error connecting to Supabase: {str(e)}")
        return None

# Initialize memory system with Qdrant
@st.cache_resource
def initialize_memory(api_key):
    """Initialize the memory system with Qdrant cloud"""
    try:
        # Verify Qdrant connection
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )
        collections = qdrant_client.get_collections()
        st.sidebar.success(f"Connected to Qdrant Cloud: {len(collections.collections)} collections found")
        
        # Configure memory with Qdrant cloud vector store
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": QDRANT_URL,
                    "api_key": QDRANT_API_KEY,
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": api_key,
                }
            },
        }
        return Memory.from_config(config)
    except Exception as e:
        st.sidebar.error(f"Error connecting to Qdrant: {str(e)}")
        raise

# Setup Embedchain with analysis text as context
def setup_embedchain(api_key, analysis_text):
    """Setup Embedchain with analysis text as context"""
    db_path = tempfile.mkdtemp()
    bot = App.from_config(
        config={
            "llm": {"provider": "openai", "config": {"api_key": api_key}},
            "vectordb": {"provider": "chroma", "config": {"dir": db_path}},
            "embedder": {"provider": "openai", "config": {"api_key": api_key}},
        }
    )
    
    # Create a temporary text file with the analysis content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(analysis_text.encode('utf-8'))
        temp_file_path = f.name
    
    # Add the analysis to embedchain
    bot.add(temp_file_path, data_type="text_file")
    
    # Clean up the temporary file
    os.remove(temp_file_path)
    
    return bot

# In data_service.py

def get_match_by_id(supabase, match_id):
    resp = (
        supabase
        .from_("matches")
        .select(
            "*, "
            "home:teams!hometeam_id(team_name), "
            "away:teams!awayteam_id(team_name), "
            "league:leagues!league_id(league), "
            "countries!country_id(country)"
        )
        .eq("match_id", match_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    m = resp.data[0]
    return {
        "match_id": match_id,
        "home_team": m["home"]["team_name"],
        "away_team": m["away"]["team_name"],
        "league_name": m["league"]["league"],
        "match_date": m["date"],           # string YYYY-MM-DD
        "country": m.get("country", "Unknown")
    }



# Memory operations
def save_chat_to_memory(memory, user_id, match_info, query, response):
    """Save chat interaction to persistent memory"""
    try:
        # Create a memory entry with metadata
        memory_entry = {
            "query": query,
            "response": response,
            "match": match_info["match"],
            "league": match_info["league"],
            "date": str(match_info["date"]),
            "timestamp": datetime.now().isoformat()
        }
        
        # Convert to string for storage
        memory_str = json.dumps(memory_entry)
        
        # Add to memory with user_id
        add_result = memory.add(memory_str, user_id=user_id)
        return True
    except Exception as e:
        st.error(f"Error saving to memory: {str(e)}")
        return False

def get_relevant_memories(memory, user_id, query, match_info=None):
    """Retrieve relevant memories for the current chat"""
    try:
        # If match_info is provided, enhance the query with match details
        search_query = query
        if match_info:
            search_query = f"{query} {match_info['match']} {match_info['league']}"
        
        # Search memory
        relevant_memories = memory.search(query=search_query, user_id=user_id, limit=5)
        
        # Process and return memories
        memories_list = []
        if relevant_memories and "results" in relevant_memories:
            for mem in relevant_memories["results"]:
                if "memory" in mem:
                    try:
                        # Parse the JSON string back to a dictionary
                        memory_dict = json.loads(mem["memory"])
                        memories_list.append(memory_dict)
                    except json.JSONDecodeError:
                        # Handle case where memory is not in expected JSON format
                        memories_list.append({"raw_memory": mem["memory"]})
        
        return memories_list
    except Exception as e:
        st.warning(f"Error retrieving memories: {str(e)}")
        return []

def get_all_memories(memory, user_id, limit=20):
    """Get all memories for a user"""
    try:
        memories = memory.get_all(user_id=user_id, limit=limit)
        return memories
    except Exception as e:
        st.error(f"Error retrieving memories: {str(e)}")
        return {"results": []}

# Supabase data operations

# --- New function to get country name by ID ---
def get_country_name_by_id(supabase, country_id):
    """Get country name from country_id"""
    if not supabase or country_id is None:
        return "Unknown Country"
    try:
        response = supabase.from_("countries").select("country").eq("country_id", country_id).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["country"]
        return "Unknown Country" # Return default if not found
    except Exception as e:
        # print(f"Error finding country name: {str(e)}") # Use app's logging
        return "Unknown Country" # Return default on error
# --- End of new function ---

def get_team_id_by_name(supabase, team_name):
    """Get team_id from team_name"""
    try:
        response = supabase.from_("teams").select("team_id").eq("team_name", team_name).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["team_id"]
        
        # Try common name if team_name doesn't match
        response = supabase.from_("teams").select("team_id").eq("common_name", team_name).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["team_id"]
            
        return None
    except Exception as e:
        st.error(f"Error finding team ID: {str(e)}")
        return None

def get_league_id_by_name(supabase, league_name):
    """Get league_id from league name"""
    try:
        response = supabase.from_("leagues").select("league_id").eq("league", league_name).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["league_id"]
        return None
    except Exception as e:
        st.error(f"Error finding league ID: {str(e)}")
        return None

def get_matches(supabase, league=None, team=None, limit=50):
    """
    Get matches from Supabase database with optional filters.
    """
    try:
        query = supabase.from_("matches").select(
            "*, home:teams!hometeam_id(team_name), away:teams!awayteam_id(team_name), league:leagues!league_id(league)"
        )
        
        # Apply league filter if provided - use league directly as the ID
        if league:
            # The league parameter is already the ID from your UI selection
            query = query.eq("league_id", league)

        # Apply team filter if provided
        if team:
            team_id = get_team_id_by_name(supabase, team)
            if team_id:
                # Use OR filter for either home or away team matching
                query = query.or_(f"hometeam_id.eq.{team_id},awayteam_id.eq.{team_id}")

        # Order by date, most recent first
        response = query.order("date", desc=True).limit(limit).execute()

        if response.data:
            matches_df = pd.DataFrame(response.data)
            # Extract nested info to user-friendly columns
            matches_df["home_team"] = matches_df["home"].apply(lambda x: x.get("team_name") if x else None)
            matches_df["away_team"] = matches_df["away"].apply(lambda x: x.get("team_name") if x else None)
            matches_df["league_name"] = matches_df["league"].apply(lambda x: x.get("league") if x else None)
            matches_df["match_date"] = matches_df["date"]

            # Select relevant columns
            result_df = matches_df[["match_id", "home_team", "away_team", "match_date", "league_name"]]
            return result_df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error retrieving matches: {str(e)}")
        return pd.DataFrame()
    
    
def get_team_stats(supabase, team_name):
    """Get team statistics from Supabase"""
    try:
        # First get the team_id
        team_id = get_team_id_by_name(supabase, team_name)
        if not team_id:
            st.warning(f"Team not found: {team_name}")
            return None
            
        # Get team stats using team_id
        response = supabase.from_("teams").select("*").eq("team_id", team_id).execute()
        
        if response.data and len(response.data) > 0:
            team_data = response.data[0]
            return team_data
        else:
            return None
    except Exception as e:
        st.error(f"Error retrieving team stats from Supabase: {str(e)}")
        return None

def get_player_stats(supabase, team_name):
    """Get player statistics for a team from Supabase"""
    # Note: As there's no players table in the provided schema, this is a placeholder
    # You would need to add the players table to your database
    st.warning("Player statistics functionality requires a players table in your database")
    return pd.DataFrame()

def get_match_by_teams(supabase, home_team, away_team, closest_to_date=None):
    """
    Get specific match details by home and away team names
    Optionally finds the match closest to a specific date
    """
    try:
        # Get team IDs
        home_team_id = get_team_id_by_name(supabase, home_team)
        away_team_id = get_team_id_by_name(supabase, away_team)
        
        if not home_team_id or not away_team_id:
            st.warning(f"Could not find IDs for teams: {home_team} and/or {away_team}")
            return None
            
        # Build query with joined team and league information
        query = supabase.from_("matches").select(
            "*, home:teams!hometeam_id(team_name), away:teams!awayteam_id(team_name), league:leagues!league_id(league)"
        ).eq("hometeam_id", home_team_id).eq("awayteam_id", away_team_id)
        
        response = query.execute()
        
        if response.data:
            matches_df = pd.DataFrame(response.data)
            
            # If a date is provided, find the closest match
            if closest_to_date:
                # Convert date strings to datetime objects
                matches_df["date"] = pd.to_datetime(matches_df["date"])
                closest_to_date = pd.to_datetime(closest_to_date)
                
                # Calculate the absolute difference in days
                matches_df["date_diff"] = (matches_df["date"] - closest_to_date).abs()
                
                # Sort by the date difference and get the first row
                closest_match = matches_df.sort_values("date_diff").iloc[0]
                
                # Format result with readable names
                result = closest_match.to_dict()
                if "home" in result and result["home"]:
                    result["home_team"] = result["home"]["team_name"]
                if "away" in result and result["away"]:
                    result["away_team"] = result["away"]["team_name"]
                if "league" in result and result["league"]:
                    result["league_name"] = result["league"]["league"]
                    
                return result
            else:
                # Return the most recent match
                match_data = matches_df.iloc[0].to_dict()
                
                # Format result with readable names
                if "home" in match_data and match_data["home"]:
                    match_data["home_team"] = match_data["home"]["team_name"]
                if "away" in match_data and match_data["away"]:
                    match_data["away_team"] = match_data["away"]["team_name"]
                if "league" in match_data and match_data["league"]:
                    match_data["league_name"] = match_data["league"]["league"]
                    
                return match_data
        else:
            return None
    except Exception as e:
        st.error(f"Error retrieving match details from Supabase: {str(e)}")
        return None

def get_head_to_head(supabase, team1, team2, limit=10):
    """Get head to head record between two teams"""
    try:
        # Get team IDs
        team1_id = get_team_id_by_name(supabase, team1)
        team2_id = get_team_id_by_name(supabase, team2)
        
        if not team1_id or not team2_id:
            st.warning(f"Could not find IDs for teams: {team1} and/or {team2}")
            return pd.DataFrame()
            
        # Query matches where either team plays against the other
        query = supabase.from_("matches").select(
            "*, home:teams!hometeam_id(team_name), away:teams!awayteam_id(team_name), league:leagues!league_id(league)"
        ).or_(
            f"and(hometeam_id.eq.{team1_id},awayteam_id.eq.{team2_id}),and(hometeam_id.eq.{team2_id},awayteam_id.eq.{team1_id})"
        )
        
        response = query.order("date", desc=True).limit(limit).execute()
        
        if response.data:
            # Convert to DataFrame
            h2h_df = pd.DataFrame(response.data)
            
            # Add readable team names
            h2h_df["home_team"] = h2h_df["home"].apply(lambda x: x["team_name"] if x else None)
            h2h_df["away_team"] = h2h_df["away"].apply(lambda x: x["team_name"] if x else None)
            h2h_df["league_name"] = h2h_df["league"].apply(lambda x: x["league"] if x else None)
            h2h_df["match_date"] = h2h_df["date"]
            
            # Select useful columns
            result_df = h2h_df[["match_id", "home_team", "away_team", "match_date", "league_name"]]
            return result_df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error retrieving head-to-head records from Supabase: {str(e)}")
        return pd.DataFrame()

def get_league_standings(supabase, league_name):
    """Get current league standings from Supabase"""
    try:
        # Get league ID
        league_id = get_league_id_by_name(supabase, league_name)
        
        if not league_id:
            st.warning(f"League not found: {league_name}")
            return pd.DataFrame()
            
        # Get all teams in this league
        # Note: This assumes teams have a league_id field or we can determine which teams are in a league
        # Since the schema doesn't show this relationship clearly, we'll use matches to determine teams in a league
        
        # Get matches for this league
        matches_query = supabase.from_("matches").select("hometeam_id, awayteam_id").eq("league_id", league_id).execute()
        
        if not matches_query.data:
            return pd.DataFrame()
            
        # Extract unique team IDs
        team_ids = set()
        for match in matches_query.data:
            team_ids.add(match["hometeam_id"])
            team_ids.add(match["awayteam_id"])
        
        # Get team details and stats
        teams_data = []
        for team_id in team_ids:
            team_query = supabase.from_("teams").select("*").eq("team_id", team_id).execute()
            if team_query.data:
                teams_data.append(team_query.data[0])
        
        if not teams_data:
            return pd.DataFrame()
            
        # Create DataFrame and sort by points
        standings_df = pd.DataFrame(teams_data)
        
        # Sort by points, goal difference
        if "points_per_game" in standings_df.columns and "goal_difference" in standings_df.columns:
            standings_df = standings_df.sort_values(
                by=["points_per_game", "goal_difference"], 
                ascending=[False, False]
            )
            
            # Select relevant columns
            columns_to_select = [
                "team_id", "team_name", "matches_played", "wins", "draws", "losses",
                "goals_scored", "goals_conceded", "goal_difference", "points_per_game"
            ]
            
            # Only include columns that exist
            available_columns = [col for col in columns_to_select if col in standings_df.columns]
            return standings_df[available_columns]
        
        return standings_df
    except Exception as e:
        st.error(f"Error retrieving league standings from Supabase: {str(e)}")
        return pd.DataFrame()
    
def save_analysis_for_wordpress(supabase, match_info, results, status="draft"):
    """
    Save the generated analysis in formats suitable for WordPress and raw display
    
    Parameters:
    - supabase: Supabase client
    - match_info: Dictionary with match details
    - results: Dictionary with analysis results
    - status: Publication status ("draft", "publish", "pending", etc.)
    
    Returns:
    - Success status and ID of the saved record
    """
    try:
        # Get team IDs
        home_team, away_team = match_info["match"].split(" vs ")
        home_team_id = get_team_id_by_name(supabase, home_team.strip())
        away_team_id = get_team_id_by_name(supabase, away_team.strip())
        
        # Get league ID
        league_id = get_league_id_by_name(supabase, match_info["league"])
        
        # Create a URL-friendly slug
        match_slug = match_info["match"].lower().replace(" vs ", "-vs-").replace(" ", "-")
        date_slug = match_info["date"].strftime("%Y-%m-%d")
        slug = f"{match_slug}-{date_slug}-analysis"
        
        # Generate SEO-friendly title
        title = f"{match_info['match']} Match Analysis and Prediction - {match_info['date'].strftime('%d %B %Y')}"
        
        # Format the content for WordPress with proper HTML
        wp_content = format_content_for_wordpress(match_info, results)
        
        # Store the raw, unformatted content as well
        raw_content = json.dumps(results)
        
        # Create SEO description
        seo_description = f"Expert analysis and prediction for the {match_info['league']} match between {match_info['match']} on {match_info['date'].strftime('%d %B %Y')}. Get betting insights and tactical breakdown."
        
        # Generate relevant tags
        tags = [home_team.strip(), away_team.strip(), match_info["league"], "Match Analysis", "Football Prediction", "Betting Tips"]
        
        # Find match_id if available
        match_id = None
        if home_team_id and away_team_id:
            match_query = supabase.from_("matches").select("match_id").eq("hometeam_id", home_team_id).eq("awayteam_id", away_team_id).limit(1).execute()
            if match_query.data and len(match_query.data) > 0:
                match_id = match_query.data[0]["match_id"]
        
        # Prepare data for insertion
        analysis_data = {
            "title": title,
            "slug": slug,
            "content": wp_content,
            "raw_content": raw_content,  # Add the raw content field
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "league_id": league_id,
            "match_date": match_info["date"].strftime('%Y-%m-%d'),
            "analysis_date": datetime.now().isoformat(),
            "status": status,
            "seo_title": title,
            "seo_description": seo_description,
            "tags": tags,
            "categories": ["Football Analysis", match_info["league"], "Match Predictions"]
        }
        
        if match_id:
            analysis_data["match_id"] = match_id
        
        # Insert into database
        response = supabase.from_("blog_analyses").insert(analysis_data).execute()
        
        if response.data:
            saved_id = response.data[0]["id"]
            return True, saved_id
        else:
            return False, None
    
    except Exception as e:
        st.error(f"Error saving analysis for WordPress: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return False, None

def format_content_for_wordpress(match_info, results):
    """Format the analysis results into WordPress-friendly HTML content"""
    
    # Get the best available analysis content
    if "combined_analysis" in results:
        main_analysis = results["combined_analysis"]
    elif "enhanced_analysis" in results:
        main_analysis = results["enhanced_analysis"]
    elif "db_insights" in results:
        main_analysis = results["db_insights"]
    else:
        main_analysis = results.get("initial_analysis", "Analysis not available.")
    
    # Convert markdown to HTML (simple approach)
    # For production, you might want to use a proper markdown to HTML converter
    html_content = main_analysis.replace("\n\n", "</p><p>").replace("\n", "<br>")
    html_content = f"<p>{html_content}</p>"
    
    # Add heading styles
    html_content = html_content.replace("<p>###", "<h3>").replace("###</p>", "</h3>")
    html_content = html_content.replace("<p>##", "<h2>").replace("##</p>", "</h2>")
    html_content = html_content.replace("<p>#", "<h1>").replace("#</p>", "</h1>")
    
    # Create header section
    header = f"""
    <h1>{match_info['match']} - Match Analysis</h1>
    <p class="match-info">{match_info['league']} | {match_info['date'].strftime('%d %B %Y')}</p>
    <div class="match-banner">
        <div class="team home-team">{match_info['match'].split(' vs ')[0]}</div>
        <div class="vs">VS</div>
        <div class="team away-team">{match_info['match'].split(' vs ')[1]}</div>
    </div>
    """
    
    # Create introduction
    intro = """
    <p class="intro">
        Welcome to our in-depth match analysis and prediction. In this article, we'll break down the key factors 
        that could influence the outcome of this match, including team form, key players, tactics, and historical 
        head-to-head records. Our AI-powered analysis combines the latest news, statistical data, and expert insights 
        to provide you with the most comprehensive match preview available.
    </p>
    <div class="divider"></div>
    """
    
    # Create sections for different types of analysis
    sections = ["<h2>Match Analysis</h2>", html_content]
    
    # Add database insights if available
    if "db_insights" in results and results["db_insights"] != main_analysis:
        db_insights_html = results["db_insights"].replace("\n\n", "</p><p>").replace("\n", "<br>")
        db_insights_html = f"<p>{db_insights_html}</p>"
        sections.append("<h2>Statistical Insights</h2>")
        sections.append(db_insights_html)
    
    # Add conclusion
    conclusion = """
    <div class="divider"></div>
    <h2>Conclusion</h2>
    <p>
        This analysis has been generated by TipsterHeroes.AI, combining cutting-edge artificial intelligence with comprehensive 
        football data. While we strive for accuracy in our analysis and predictions, football remains inherently unpredictable. 
        Always gamble responsibly and use this information as just one of many resources when making betting decisions.
    </p>
    <p class="disclaimer">
        <strong>Disclaimer:</strong> This content is for informational purposes only. Betting involves risk and you should never 
        bet more than you can afford to lose.
    </p>
    """
    
    # Combine everything
    full_content = header + intro + "".join(sections) + conclusion
    
    # Add WordPress-friendly styling
    styled_content = f"""
    <!-- wp:html -->
    <style>
        .match-info {{
            text-align: center;
            font-size: 1.2em;
            color: #666;
            margin-bottom: 2em;
        }}
        .match-banner {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #f5f5f5;
            padding: 2em;
            border-radius: 10px;
            margin: 2em 0;
        }}
        .team {{
            font-size: 1.5em;
            font-weight: bold;
            flex: 1;
        }}
        .home-team {{
            text-align: right;
        }}
        .away-team {{
            text-align: left;
        }}
        .vs {{
            font-size: 1.2em;
            padding: 0 2em;
            color: #999;
        }}
        .intro {{
            font-size: 1.1em;
            line-height: 1.6;
        }}
        .divider {{
            height: 1px;
            background: #ddd;
            margin: 2em 0;
        }}
        .disclaimer {{
            background: #f8f8f8;
            padding: 1em;
            border-left: 4px solid #d44;
            margin: 2em 0;
        }}
    </style>
    {full_content}
    <!-- /wp:html -->
    """
    
    return styled_content

def check_analysis_exists(supabase, home_team, away_team, match_date):
    """Check if an analysis already exists for this match"""
    try:
        # Get team IDs
        home_team_id = get_team_id_by_name(supabase, home_team)
        away_team_id = get_team_id_by_name(supabase, away_team)
        
        date_str = match_date.strftime('%Y-%m-%d')
        
        # Query the blog_analyses table
        response = supabase.from_("blog_analyses").select("id") \
            .eq("home_team_id", home_team_id) \
            .eq("away_team_id", away_team_id) \
            .eq("match_date", date_str) \
            .limit(1) \
            .execute()
            
        # Return True if an analysis exists
        return len(response.data) > 0, response.data[0]["id"] if response.data else None
    except Exception as e:
        print(f"Error checking for existing analysis: {str(e)}")
        return False, None
    
def get_analysis_by_id(supabase, analysis_id):
    """Get analysis content by ID"""
    try:
        response = supabase.from_("blog_analyses").select("*").eq("id", analysis_id).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error retrieving analysis: {str(e)}")
        return None

def add_analysis_message(role, content, animate=False, delay=0.05):
    """Add a message to the analysis chat without displaying it immediately"""
    import time
    
    # Initialize chat history if not present
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Store in analysis_chat for state tracking 
    if "analysis_chat" not in st.session_state:
        st.session_state.analysis_chat = []
    
    # Add to both trackers
    st.session_state.analysis_chat.append({"role": role, "content": content})
    st.session_state.chat_history.append({"role": role, "content": content})
    
    # Only display in the UI if we're specifically in the chat section
    # This relies on the UI code in the right column handling the display
    # DON'T render the message directly here

def setup_chat_with_context(results, full_query, chat_method, api_key):
    """Set up the chat bot with the analysis context"""
    # Reset chat history for new analysis
    st.session_state.chat_history = []
    
    # Determine which analysis to use for context
    if "combined_analysis" in results:
        analysis_for_context = results["combined_analysis"]
    else:
        analysis_for_context = results.get("enhanced_analysis", "")
        
    # Create context
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
    
    # Initialize appropriate chat method
    if chat_method == "Embedchain" and api_key:
        st.session_state.chat_bot = setup_embedchain(api_key, full_analysis)
    
    # Store the analysis context for all approaches
    st.session_state.chat_context = full_analysis

def get_match_bets(supabase, match_id):
    """
    Get all available bets for a specific match
    
    Parameters:
    - supabase: Supabase client
    - match_id: ID of the match to get bets for
    
    Returns:
    - DataFrame with bet data including bet types
    """
    try:
        # Query bets with bet type information joined
        query = supabase.from_("bets").select(
            "*, bet_type:bettypes!betype_id(bet_type)"
        ).eq("match_id", match_id)
        
        response = query.execute()
        
        if response.data:
            # Convert to DataFrame
            bets_df = pd.DataFrame(response.data)
            
            # Create more user-friendly column names
            if "bet_type" in bets_df.columns:
                # Extract nested bet type value
                bets_df["bet_name"] = bets_df["bet_type"].apply(lambda x: x["bet_type"] if x else None)
                
                # Select columns in a nice order
                result_columns = [
                    "bet_id", "bet_name", "odds", "consensus", 
                    "ev", "tier", "model1", "model2", "model3"
                ]
                # Only include columns that exist in the dataframe
                available_columns = [col for col in result_columns if col in bets_df.columns]
                result_df = bets_df[available_columns]
                return result_df
            
            return bets_df
        else:
            return pd.DataFrame()  # Return empty DataFrame if no bets found
    except Exception as e:
        st.error(f"Error retrieving bets from Supabase: {str(e)}")
        return pd.DataFrame()
    
def display_match_bets(supabase, match_id=None, home_team=None, away_team=None):
    """
    Display all bets for a selected match
    
    Parameters:
    - supabase: Supabase client
    - match_id: ID of the match (if known)
    - home_team: Home team name (alternative to match_id)
    - away_team: Away team name (alternative to match_id)
    
    Returns:
    - DataFrame with formatted bet data for display
    """
    try:
        # If match_id is not provided, try to find it using team names
        if not match_id and home_team and away_team:
            home_team_id = get_team_id_by_name(supabase, home_team)
            away_team_id = get_team_id_by_name(supabase, away_team)
            
            if not home_team_id or not away_team_id:
                st.warning(f"Could not find IDs for teams: {home_team} and/or {away_team}")
                return pd.DataFrame()
                
            # Find the match
            match_query = supabase.from_("matches").select("match_id") \
                .eq("hometeam_id", home_team_id) \
                .eq("awayteam_id", away_team_id) \
                .limit(1).execute()
                
            if match_query.data and len(match_query.data) > 0:
                match_id = match_query.data[0]["match_id"]
            else:
                st.warning(f"No match found between {home_team} and {away_team}")
                return pd.DataFrame()
        
        # Get bets for this match
        bets_df = get_match_bets(supabase, match_id)
        
        if bets_df.empty:
            st.info("No bets found for this match")
            return pd.DataFrame()
            
        # Format the display of the dataframe
        display_df = bets_df.copy()
        
        # Format odds as decimal with 2 places
        if "odds" in display_df.columns:
            display_df["odds"] = display_df["odds"].apply(lambda x: f"{x:.2f}" if x is not None else "-")
        
        # Format consensus and EV as percentages
        for col in ["consensus", "ev"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%" if x is not None else "-")
        
        # Format model results as percentages
        for col in ["model1", "model2", "model3"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%" if x is not None else "-")
                
        # Rename columns for better display
        column_mapping = {
            "bet_name": "Bet Type",
            "odds": "Odds",
            "consensus": "Consensus",
            "ev": "Expected Value",
            "tier": "Tier",
            "model1": "Model 1",
            "model2": "Model 2", 
            "model3": "Model 3"
        }
        
        # Only rename columns that exist in the dataframe
        rename_cols = {k: v for k, v in column_mapping.items() if k in display_df.columns}
        display_df = display_df.rename(columns=rename_cols)
        
        # Display in Streamlit
        st.subheader("Available Bets")
        st.dataframe(display_df, use_container_width=True)
        
        # Add conditional formatting for tiers if available
        if "Tier" in display_df.columns:
            # Count bets by tier
            tier_counts = display_df["Tier"].value_counts()
            
            # Display summary
            st.write("Bet Summary:")
            cols = st.columns(len(tier_counts))
            
            for i, (tier, count) in enumerate(tier_counts.items()):
                tier_color = {
                    "A": "green",
                    "B": "blue",
                    "C": "orange",
                    "D": "red"
                }.get(tier, "gray")
                
                cols[i].metric(f"Tier {tier} Bets", count)
        
        return display_df
        
    except Exception as e:
        st.error(f"Error displaying match bets: {str(e)}")
        return pd.DataFrame()
    
def get_match_with_bets(supabase, home_team, away_team, closest_to_date=None):
    """
    Get specific match details by home and away team names with associated bets
    Optionally finds the match closest to a specific date
    
    Returns combined dictionary with match details and bets
    """
    try:
        # First get the match details using the existing function
        match_details = get_match_by_teams(supabase, home_team, away_team, closest_to_date)
        
        if not match_details:
            return None
            
        # Get bets for this match
        bets_df = get_match_bets(supabase, match_details["match_id"])
        
        # Convert bets to a dictionary format that's easy to work with
        bets_by_type = {}
        
        if not bets_df.empty and "bet_name" in bets_df.columns:
            for _, bet in bets_df.iterrows():
                bet_type = bet.get("bet_name", "Unknown")
                bet_dict = bet.to_dict()
                bets_by_type[bet_type] = bet_dict
        
        # Add bets to the match details
        match_details["bets"] = bets_by_type
        match_details["has_bets"] = not bets_df.empty
        
        return match_details
    except Exception as e:
        st.error(f"Error retrieving match details with bets: {str(e)}")
        return None    

import re
from bs4 import BeautifulSoup

def parse_wordpress_analysis(html_content):
    """Parse WordPress HTML content to extract clean analysis text"""
    try:
        # Create a BeautifulSoup object
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove style tags
        for style in soup.find_all('style'):
            style.decompose()
            
        # Extract text content
        output = ""
        
        # Find all relevant elements
        for elem in soup.find_all(['h1', 'h2', 'p', 'div']):
            # Skip empty elements or those with specific classes to ignore
            if not elem.text.strip() or (elem.get('class') and any(c in ['match-banner', 'divider', 'disclaimer'] for c in elem.get('class'))):
                continue
                
            # Format according to tag type
            text = elem.text.strip()
            if elem.name == 'h1':
                output += f"{text}\n\n"
            elif elem.name == 'h2':
                output += f"{text}\n\n"
            else:
                # Treat everything else as paragraph text
                output += f"{text}\n\n"
        
        return output
    except Exception:
        # Return original content if parsing fails
        return html_content


    

def extract_betting_insights(analysis_content):
    """Extract betting insights from analysis content"""
    try:
        betting_insights = {}
        
        # Look for betting sections using regex
        betting_section_regex = r'(?:Betting|Suggested Betting Markets).*?\n(.*?)(?=\n#|\Z)'
        match = re.search(betting_section_regex, analysis_content, re.DOTALL | re.IGNORECASE)
        
        if match:
            betting_section = match.group(1).strip()
            betting_insights["section"] = betting_section
            
            # Extract specific bet recommendations
            bet_types = []
            
            # Look for patterns like:
            # - **Match Result:** Bet on Newcastle to win, with odds likely around **1.85**.
            bet_pattern = r'-\s+\*\*(.*?):\*\*\s+(.*?)(?:;\s+(?:odds|value).*?\*\*([\d\.]+)\*\*)?'
            for bet_match in re.finditer(bet_pattern, betting_section):
                bet_type = bet_match.group(1).strip()
                bet_pick = bet_match.group(2).strip()
                bet_odds = bet_match.group(3) if len(bet_match.groups()) > 2 else None
                
                bet_types.append({
                    "type": bet_type,
                    "pick": bet_pick,
                    "odds": bet_odds
                })
            
            betting_insights["recommendations"] = bet_types
        
        return betting_insights
    
    except Exception as e:
        print(f"Error extracting betting insights: {str(e)}")
        return {}
