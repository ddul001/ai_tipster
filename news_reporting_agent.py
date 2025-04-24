import streamlit as st
from duckduckgo_search import DDGS
from swarm import Swarm, Agent
from datetime import datetime
from dotenv import load_dotenv
import os
import tempfile
from embedchain import App

load_dotenv()
MODEL = "gpt-4o-mini"
client = Swarm()

# Set page configuration
st.set_page_config(
    page_title="TipsterHeroes - AI Football Analysis",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ TipsterHeroes.AI - Football Match Analysis")
st.markdown("AI-powered football news analysis for match predictions and betting insights")

def search_news(topic):
    """Search for news articles using DuckDuckGo"""
    with DDGS() as ddg:
        results = ddg.text(f"{topic} football match news {datetime.now().strftime('%Y-%m')}", max_results=5)
        if results:
            news_results = "\n\n".join([
                f"Title: {result['title']}\nURL: {result['href']}\nSummary: {result['body']}" 
                for result in results
            ])
            return news_results
        return f"No news found for {topic}."

# Create specialized agents
search_agent = Agent(
    name="Football News Searcher",
    instructions="""
    You are a football news search specialist. Your task is to:
    1. Search for the most relevant and recent news about football matches, teams, players, and competitions
    2. Focus on news related to upcoming matches, team performance, injuries, transfers, and tactical analyses
    3. Ensure the results are from reputable sports news sources and official team channels
    4. Prioritize information that provides context for match predictions and betting insights
    5. Return the raw search results in a structured format
    6. Include team statistics, recent form, and head-to-head data when available
    """,
    functions=[search_news],
    model=MODEL
)

synthesis_agent = Agent(
    name="Football News Synthesizer",
    instructions="""
    You are a football news synthesis expert. Your task is to:
    1. Analyze the raw football news articles provided
    2. Identify key information relevant to upcoming matches, including:
       - Team news and injury updates
       - Tactical approaches and formations
       - Manager statements and team morale
       - Recent performance trends and statistics
       - Transfer news that may impact team composition
    3. Combine information from multiple sources to create a complete picture
    4. Highlight information that could influence match outcomes and betting opportunities
    5. Create a comprehensive but concise synthesis focused on actionable insights
    6. Maintain objectivity while providing expert context
    Provide a 2-3 paragraph synthesis that a football betting analyst would find valuable.
    """,
    model=MODEL
)

summary_agent = Agent(
    name="Football News Summarizer",
    instructions="""
    You are an expert football news summarizer combining sports journalism clarity with analytical insight.

    Your task:
    1. Core Match Information:
       - Lead with the most relevant team and match developments
       - Include key player status, injuries, and expected lineups
       - Add critical performance data and statistics
       - Explain how this information impacts upcoming matches
       - Highlight betting-relevant insights

    2. Style Guidelines:
       - Use precise football terminology and concepts
       - Support points with specific statistical evidence
       - Maintain analytical objectivity
       - Contextualize information for prediction purposes
       - Balance team news with tactical analysis

    Format: Create a single paragraph of 250-400 words that provides essential context for match analysis and predictions.
    Pattern: [Key Team News] + [Performance Data/Stats] + [Tactical Insights] + [Implications for Match Outcome]

    Focus on answering: What's happening with these teams? How might it affect the upcoming match? What factors should be considered for predictions?

    IMPORTANT: Provide ONLY the contextual summary paragraph. Include only information that would be valuable for making informed match predictions and understanding betting opportunities. Start directly with the football content.
    """,
    model=MODEL
)

elaboration_agent = Agent(
    name="Football Analysis Elaborator",
    instructions="""
    You are an expert football analysis enhancer specializing in betting context elaboration.

    When given a football match analysis:
    1. Analyze the content and identify areas that could benefit from additional context
    2. Enhance the analysis by:
       - Adding detailed statistical comparisons between the teams
       - Including historical betting patterns and outcomes for similar matchups
       - Expanding on key tactical matchups with specific player comparisons
       - Adding relevant league context and table implications
       - Incorporating recent team form analysis with detailed metrics
       - Suggesting specific betting markets that might offer value based on the analysis
       - Highlighting any situational factors (weather, pitch conditions, referee tendencies)
    3. Maintain analytical objectivity and betting-focused insights
    4. Structure the elaboration with clear sections and data-backed points
    5. Ensure all additions provide actionable betting insights

    Your output should transform a basic match summary into a comprehensive match analysis that 
    helps bettors make informed decisions. Focus on enhancing the predictive value of the analysis
    rather than simply adding more general information.
    """,
    model=MODEL
)

chat_agent = Agent(
    name="Football Chat Assistant",
    instructions="""
    You are a football analysis chat assistant specialized in answering queries about specific matches.
    
    Your capabilities:
    1. Answer questions based on the provided match analysis context
    2. Explain betting insights, tactical perspectives, and match predictions
    3. Provide statistical context and interpretations when asked
    4. Clarify information from the analysis in conversational language
    5. Acknowledge limitations when information is not available in the context
    
    Guidelines:
    - Stay focused on the specific match and teams in the provided context
    - Use precise football terminology while remaining accessible
    - Support your responses with information directly from the analysis
    - Maintain analytical objectivity and betting-focused insights
    - Be concise but thorough in your explanations
    
    Your primary goal is to help users better understand the match analysis and make more informed decisions.
    """,
    model=MODEL
)

def process_football_news(match_details):
    """Run the football news processing workflow with elaboration"""
    with st.status("Processing football match analysis...", expanded=True) as status:
        # Search Phase
        status.write("🔍 Searching for football news...")
        search_response = client.run(
            agent=search_agent,
            messages=[{"role": "user", "content": f"Find recent news about {match_details}"}]
        )
        raw_news = search_response.messages[-1]["content"]
        
        # Synthesis Phase
        status.write("🔄 Synthesizing information...")
        synthesis_response = client.run(
            agent=synthesis_agent,
            messages=[{"role": "user", "content": f"Synthesize these football news articles:\n{raw_news}"}]
        )
        synthesized_news = synthesis_response.messages[-1]["content"]
        
        # Summary Phase
        status.write("📝 Creating initial match analysis...")
        summary_response = client.run(
            agent=summary_agent,
            messages=[{"role": "user", "content": f"Summarize this football synthesis for betting context:\n{synthesized_news}"}]
        )
        initial_analysis = summary_response.messages[-1]["content"]
        
        # Elaboration Phase
        status.write("🔍 Enhancing analysis with additional context...")
        elaboration_response = client.run(
            agent=elaboration_agent,
            messages=[{
                "role": "user", 
                "content": f"""
                MATCH: {match_details}
                
                INITIAL ANALYSIS:
                {initial_analysis}
                
                Please enhance this match analysis with additional statistics, betting context, 
                and deeper insights to help bettors make more informed decisions.
                """
            }]
        )
        enhanced_analysis = elaboration_response.messages[-1]["content"]
        
        status.update(label="Analysis complete!", state="complete")
        
        return {
            "raw_news": raw_news,
            "synthesized_news": synthesized_news,
            "initial_analysis": initial_analysis,
            "enhanced_analysis": enhanced_analysis
        }

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

def chat_with_analysis(query, analysis_context):
    """Use the chat agent to respond to queries about the analysis"""
    chat_response = client.run(
        agent=chat_agent,
        messages=[{
            "role": "system", 
            "content": f"Use the following football match analysis as context for answering user questions:\n\n{analysis_context}"
        },
        {
            "role": "user",
            "content": query
        }]
    )
    return chat_response.messages[-1]["content"]

# Main UI
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("Configure your match analysis parameters")
    
    # Simple API key input if needed
    api_key = st.text_input("API Key (if required)", type="password")
    
    # Additional analysis options
    st.subheader("Analysis Focus")
    include_betting = st.checkbox("Include Betting Insights", value=True)
    include_stats = st.checkbox("Include Detailed Statistics", value=True)
    include_lineup = st.checkbox("Include Expected Lineups", value=True)
    
    # Chat method selection
    st.subheader("Chat Method")
    chat_method = st.radio(
        "Choose chat implementation:",
        ["Direct Agent", "Embedchain"],
        help="Direct Agent uses the analysis directly, Embedchain uses vector embeddings"
    )

# Initialize session state for chat history if it doesn't exist
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Initialize chat bot in session state if using Embedchain
if "chat_bot" not in st.session_state:
    st.session_state.chat_bot = None

# Main content area
col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("Match Details")
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
            try:
                # Process the news with all agents
                full_query = f"{match_details} {league} {match_date.strftime('%d %B %Y')}"
                results = process_football_news(full_query)
                
                # Store results in session state to display in tabs
                st.session_state.results = results
                st.session_state.match_info = {
                    "match": match_details,
                    "league": league,
                    "date": match_date
                }
                
                # If using Embedchain, initialize the chat bot with the analysis
                if chat_method == "Embedchain" and api_key:
                    # Combine all analysis components for context
                    full_analysis = f"""
                    MATCH: {full_query}
                    
                    ENHANCED ANALYSIS:
                    {results['enhanced_analysis']}
                    
                    INITIAL ANALYSIS:
                    {results['initial_analysis']}
                    
                    SYNTHESIZED NEWS:
                    {results['synthesized_news']}
                    """
                    st.session_state.chat_bot = setup_embedchain(api_key, full_analysis)
                    st.session_state.chat_context = full_analysis
                elif chat_method == "Direct Agent":
                    # Store the analysis context for the direct agent approach
                    st.session_state.chat_context = f"""
                    MATCH: {full_query}
                    
                    ENHANCED ANALYSIS:
                    {results['enhanced_analysis']}
                    
                    INITIAL ANALYSIS:
                    {results['initial_analysis']}
                    """
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
        else:
            st.error("Please enter match details!")

# Results area
with col2:
    if "results" in st.session_state:
        results = st.session_state.results
        match_info = st.session_state.match_info
        
        st.subheader(f"Match Analysis: {match_info['match']}")
        st.caption(f"{match_info['league']} | {match_info['date'].strftime('%d %B %Y')}")
        
        # Create tabs for different analysis views and chat
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Enhanced Analysis", "Initial Summary", "News Synthesis", "Raw Sources", "Chat"
        ])
        
        with tab1:
            st.markdown("### 📊 Enhanced Match Analysis")
            st.markdown(results["enhanced_analysis"])
            st.download_button(
                "Download Enhanced Analysis",
                results["enhanced_analysis"],
                file_name=f"{match_info['match'].replace(' ', '_')}_enhanced_analysis.md",
                mime="text/markdown"
            )
            
        with tab2:
            st.markdown("### 📝 Initial Match Summary")
            st.markdown(results["initial_analysis"])
            
        with tab3:
            st.markdown("### 🔄 News Synthesis")
            st.markdown(results["synthesized_news"])
            
        with tab4:
            st.markdown("### 🔍 Raw News Sources")
            st.text_area("Sources", results["raw_news"], height=400)
            
        with tab5:
            st.markdown("### 💬 Chat with Analysis")
            
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
                        elif chat_method == "Direct Agent" and "chat_context" in st.session_state:
                            response = chat_with_analysis(chat_prompt, st.session_state.chat_context)
                        else:
                            response = "Please generate an analysis first and ensure API key is provided if using Embedchain."
                        
                        st.write(response)
                        
                # Add assistant response to chat history
                st.session_state.chat_history.append({"role": "assistant", "content": response})
    else:
        st.info("Enter match details and generate an analysis to see results here.")

# Footer
st.markdown("---")
st.markdown("ⓒ TipsterHeroes.AI - Powered by AI for football betting insights")