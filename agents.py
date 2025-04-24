"""
AI Agents Module for TipsterHeroes.AI
Contains all agent definitions and related processing functions.
"""

from bs4 import BeautifulSoup
import requests
import streamlit as st
from duckduckgo_search import DDGS
from swarm import Swarm, Agent
from datetime import datetime
from openai import OpenAI
# Initialize Swarm client
# Initialize Swarm client with API key from Streamlit secrets
try:
    client = Swarm(client=OpenAI(api_key=st.secrets["OPENAI_API_KEY"]))
except Exception as e:
    st.error(f"Failed to initialize Swarm client: {str(e)}")
    st.stop()

# Default model for agents
MODEL = "gpt-4o-mini"

def search_news_original(topic):
    """Search for news articles using DuckDuckGo"""
    with DDGS() as ddg:
        print(f"{topic} football match news {datetime.now().strftime('%Y-%m-%d')}" )
        results = ddg.text(f"{topic} football match news {datetime.now().strftime('%Y-%m-%d')}", max_results=5)
        if results:
            news_results = "\n\n".join([
                f"Title: {result['title']}\nURL: {result['href']}\nSummary: {result['body']}" 
                for result in results
            ])

            for result in results:
                st.write(f"result: {result }")
 
            return news_results
        
        print("news_results",news_results)
        return f"No news found for {topic}."



# def search_news(topic):
#     """Search for news articles from a predefined list of websites using DuckDuckGo."""
#     sites = ["https://theanalyst.com/eu", "https://www.reuters.com/sports/soccer/"]
#     try:
#         with DDGS() as ddg:
#             query = f"{topic} football match news {datetime.now().strftime('%Y-%m-%d')}"
#             results = ddg.news(keywords=query,
#                                region="wt-wt",  # Worldwide
#                                safesearch="off",
#                                timelimit="d",    # Search for news from today
#                                max_results=5)

#             if results:
#                 news_results = "\n\n".join([
#                     f"Title: {result['title']}\nURL: {result['url']}\nSummary: {result['body']}"
#                     for result in results
#                 ])

#                 for result in results:
#                     st.write(f"result: {result}")

#                 return news_results
#             else:
#                 return f"No news found for '{topic} football match' on the specified sites today."
#     except Exception as e:
#         print(f"An error occurred during the search: {e}")
#         return f"An error occurred while searching for news on {topic} from the specified sites."


def scrape_article_content(url):
    """Scrapes the main content from a given URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        # --- ADJUST THESE SELECTORS BASED ON THE ACTUAL WEBSITE STRUCTURE ---
        possible_article_containers = [
            'article',
            'main',
            'div.article-body',
            'div.article-content',
            'div.article__body',
            'div#article-body',
            'div#main-content',
            'div.story-content',
            'div.body-text',
            'div.entry-content',
            'div[itemprop="articleBody"]',  # Sometimes articles use microdata
            'div[itemprop="description"]'  # Sometimes articles use microdata
        ]

        article = None
        for selector in possible_article_containers:
            article = soup.select_one(selector)
            if article:
                break

        if article:
            paragraphs = article.find_all('p')
            content = "\n".join([p.text.strip() for p in paragraphs])
            return content
        else:
            return "Could not extract article content."
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {e}"
    except Exception as e:
        return f"Error processing article: {e}"

def search_news(topic):
    """Search for news articles from a predefined list of websites using DuckDuckGo and scrape content."""
    sites = ["https://theanalyst.com/eu", "https://www.reuters.com/sports/soccer/"]
    try:
        with DDGS() as ddg:
            results = ddg.text(f"{topic} football match news {datetime.now().strftime('%Y-%m-%d')}", max_results=3)  # Reduced max_results for demonstration
            if results:
                news_results_with_content = []
                for result in results:
                    st.write(f"result: {result}")
                    url = result['href']
                    content = scrape_article_content(url)
                    news_results_with_content.append({
                        'title': result['title'],
                        'url': url,
                        'summary': result['body'],
                        'full_content': content
                    })
                    
                    st.subheader(f"Article: {result['title']}")
                    st.write(f"URL: {url}")
                    st.write(f"Summary: {result['body']}")
                    st.write("--- Full Content ---")
                    st.write(content)
                    st.write("=" * 50)

                news_results = "\n\n".join([
                    f"Title: {item['title']}\nURL: {item['url']}\nSummary: {item['summary']}\nContent:\n{item['full_content']}"
                    for item in news_results_with_content
                ])

                print("----- Inside search_news -----")
                print("news_results_with_content:", news_results_with_content)  # Print the list
                print("-----------------------------")
                return news_results
            else:
                return f"No news found for '{topic} football match' on the specified sites today."
    except Exception as e:
        print(f"An error occurred during the search: {e}")
        return f"An error occurred while searching for news on {topic} from the specified sites."



# Create search agent
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

# Create synthesis agent
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

# Create summary agent
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

# Create elaboration agent
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

# Create chat agent
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
    6. Use conversation history to maintain context and provide coherent responses
    
    Guidelines:
    - Stay focused on the specific match and teams in the provided context
    - Use precise football terminology while remaining accessible
    - Support your responses with information directly from the analysis
    - Maintain analytical objectivity and betting-focused insights
    - Be concise but thorough in your explanations
    - Reference previous parts of the conversation when appropriate
    
    Your primary goal is to help users better understand the match analysis and make more informed decisions.
    """,
    model=MODEL
)

# Create agent for database insights
data_insights_agent = Agent(
    name="Football Database Insights",
    instructions="""
    You are a football data specialist who analyzes structured match data and statistics.
    
    Your task is to:
    1. Analyze football match data provided in structured format (team stats, player data, match history)
    2. Identify key patterns, trends, and insights from historical data
    3. Create a detailed but concise analysis that complements news-based information
    4. Provide statistical context that can inform betting decisions
    5. Highlight data-driven insights about team form, player performance, and tactical tendencies
    6. Format your response with appropriate sections and bullet points for clarity
    7. When relevant data is missing, acknowledge limitations but provide analysis based on available information
    
    Your insights should be objective, data-driven, and directly relevant to the upcoming match. 
    Focus on information that would be valuable for betting or match prediction purposes.
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

        status.write(f"🔍 found recent news {raw_news}")
        
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
                
                Latest News:
                {raw_news}
                
                INITIAL ANALYSIS:
                {initial_analysis}


                Please enhance this match analysis with additional statistics, betting context, 
                and deeper insights to help bettors make more informed decisions.
                """
            }]
        )
        enhanced_analysis = elaboration_response.messages[-1]["content"]
        
        status.update(label="Analysis complete!", state="complete")

        news_articles = search_news(match_details)  # Get the scraped data

        raw_news_formatted = news_articles

        scraped_content = news_articles   # Handle empty results

        print("----- Inside process_football_news -----")
        print("raw_news:", raw_news_formatted)
        print("scraped_content:", scraped_content)
        print("---------------------------------------")
                
        return {
            "raw_news": raw_news,
            "scraped_content": scraped_content,  # Pass the dictionary
            "synthesized_news": synthesized_news,
            "initial_analysis": initial_analysis,
            "enhanced_analysis": enhanced_analysis
        }

def process_database_insights(match_data, team1_data, team2_data, head_to_head_data=None, league_data=None):
    """
    Process and analyze database data using the insights agent
    
    Parameters:
    - match_data: Dict with match details
    - team1_data: Dict with first team's statistics
    - team2_data: Dict with second team's statistics
    - head_to_head_data: DataFrame with head-to-head history
    - league_data: DataFrame with league standings
    
    Returns:
    - String with database insights analysis
    """
    # Prepare data in a structured format
    data_formatted = f"""
    MATCH DATA:
    {match_data}
    
    {match_data['home_team']} STATISTICS:
    {team1_data}
    
    {match_data['away_team']} STATISTICS:
    {team2_data}
    """
    
    # Add head to head data if available
    if head_to_head_data is not None and not head_to_head_data.empty:
        data_formatted += f"""
        HEAD-TO-HEAD HISTORY:
        {head_to_head_data.to_string()}
        """
    
    # Add league data if available
    if league_data is not None and not league_data.empty:
        data_formatted += f"""
        LEAGUE STANDINGS:
        {league_data.to_string()}
        """
    
    # Get insights from the data agent
    insights_response = client.run(
        agent=data_insights_agent,
        messages=[{
            "role": "user",
            "content": f"""
            Please analyze this football match data and provide insights relevant for betting and match prediction:
            
            {data_formatted}
            
            Focus on key statistical patterns, form trends, and tactical matchups that could influence the match outcome.
            """
        }]
    )
    
    return insights_response.messages[-1]["content"]

# def chat_with_analysis(query, analysis_context, chat_history=None):
#     """Use the chat agent to respond to queries about the analysis with conversation context"""
#     # If no chat history is provided, create an empty list
#     if chat_history is None:
#         chat_history = []
    
#     # Create conversation history as messages
#     messages = [
#         {
#             "role": "system", 
#             "content": f"Use the following football match analysis as context for answering user questions:\n\n{analysis_context}"
#         }
#     ]
    
#     # Add conversation history to messages
#     for msg in chat_history:
#         messages.append({"role": msg["role"], "content": msg["content"]})
    
#     # Add the current query
#     messages.append({"role": "user", "content": query})
    
#     # Get response from chat agent
#     chat_response = client.run(
#         agent=chat_agent,
#         messages=messages
#     )
    
#     return chat_response.messages[-1]["content"]





def chat_with_analysis(query, analysis_context, scraped_content, chat_history):
    """Use the chat agent to respond to queries with analysis and scraped content context."""
    if chat_history is None:
        chat_history = []

    system_content = f"Use the following football match analysis as context:\n\n{analysis_context}"



    if scraped_content:
        system_content += "\n\nScraped Content from News Articles:\n"
        if scraped_content:
            system_content += f"Content:\n{scraped_content}\n---\n"

    messages = [
        {"role": "system", "content": system_content}
    ]

    print("system_content", system_content)

    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    chat_response = client.run(
        agent=chat_agent,
        messages=messages
    )

    return chat_response.messages[-1]["content"]

def combine_analysis_with_database(news_analysis, db_insights):
    """
    Combine news-based analysis with database insights into a comprehensive report
    
    Parameters:
    - news_analysis: Dictionary with news-based analysis results
    - db_insights: String with database insights analysis
    
    Returns:
    - String with combined comprehensive analysis
    """
    combined_prompt = f"""
    NEWS-BASED ANALYSIS:
    {news_analysis['enhanced_analysis']}
    
    DATABASE INSIGHTS:
    {db_insights}
    
    Please combine these two analyses into a comprehensive report that integrates news information with statistical data.
    The report should be well-structured with clear sections and maintain a focus on actionable betting insights.
    """
    
    combined_response = client.run(
        agent=elaboration_agent,
        messages=[{"role": "user", "content": combined_prompt}]
    )
    
    return combined_response.messages[-1]["content"]

analysis_conversation_agent = Agent(
    name="Analysis Guide",
    instructions="""
    You are an engaging football analysis assistant that guides users through the analysis process.
    Your job is to make the waiting time feel interactive by providing insights during each step
    of the analysis generation. Be conversational, enthusiastic about football, and provide
    genuine insights based on the data being retrieved. 
    
    Structure your responses as brief, engaging messages that maintain user interest
    while the system processes data in the background.
    """,
    model=MODEL
)