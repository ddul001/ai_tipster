import streamlit as st
from duckduckgo_search import DDGS
from swarm import Swarm, Agent
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
MODEL = "gpt-4o-mini"
client = Swarm()

st.set_page_config(page_title="TipsterHeroes - AI Football News Processor", page_icon="📰")
st.title("📰 TipsterHeroes.AI - Football News Processor Agent")

def search_news(topic):
    """Search for news articles using DuckDuckGo"""
    with DDGS() as ddg:
        results = ddg.text(f"{topic} news {datetime.now().strftime('%Y-%m')}", max_results=3)
        if results:
            news_results = "\n\n".join([
                f"Title: {result['title']}\nURL: {result['href']}\nSummary: {result['body']}" 
                for result in results
            ])
            return news_results
        return f"No news found for {topic}."

# Create specialized agents
search_agent = Agent(
    name="News Searcher",
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
    name="News Synthesizer",
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
    name="News Summarizer",
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

def process_news(topic):
    """Run the news processing workflow"""
    with st.status("Processing football news...", expanded=True) as status:
        # Search
        status.write("🔍 Searching for football news...")
        search_response = client.run(
            agent=search_agent,
            messages=[{"role": "user", "content": f"Find recent news about {topic}"}]
        )
        raw_news = search_response.messages[-1]["content"]
        
        # Synthesize
        status.write("🔄 Synthesizing information...")
        synthesis_response = client.run(
            agent=synthesis_agent,
            messages=[{"role": "user", "content": f"Synthesize these news articles:\n{raw_news}"}]
        )
        synthesized_news = synthesis_response.messages[-1]["content"]
        
        # Summarize
        status.write("📝 Creating summary...")
        summary_response = client.run(
            agent=summary_agent,
            messages=[{"role": "user", "content": f"Summarize this synthesis:\n{synthesized_news}"}]
        )
        return raw_news, synthesized_news, summary_response.messages[-1]["content"]

# User Interface
topic = st.text_input("Enter match details:", value="Nancy vs Châteauroux")
if st.button("Activate TipsterHeroes AGENT", type="primary"):
    if topic:
        try:
            raw_news, synthesized_news, final_summary = process_news(topic)
            st.header(f"📝 Football News Summary: {topic}")
            st.markdown(final_summary)
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
    else:
        st.error("Please enter a topic!")