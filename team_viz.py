# team_viz.py
import streamlit as st
import streamlit.components.v1 as components
import json

def create_team_stats_dashboard(home_team_stats, away_team_stats):
    """
    Create an interactive team statistics dashboard using React
    
    Args:
        home_team_stats (dict): Statistics for the home team
        away_team_stats (dict): Statistics for the away team
    """
    # Convert Python dicts to JSON strings for our React component
    team_data_json = json.dumps([home_team_stats, away_team_stats])
    
    # Create HTML with the React component
    html_content = f"""
    <html>
    <head>
        <title>Football Team Stats Dashboard</title>
        <script src="https://unpkg.com/react@17/umd/react.production.min.js"></script>
        <script src="https://unpkg.com/react-dom@17/umd/react-dom.production.min.js"></script>
        <script src="https://unpkg.com/recharts@2.1.15/umd/recharts.min.js"></script>
        <link href="https://unpkg.com/tailwindcss@^2/dist/tailwind.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                padding: 0;
                margin: 0;
            }}
            #dashboard-container {{
                width: 100%;
                margin: 0 auto;
            }}
            .tab-button {{
                padding: 8px 16px;
                margin-right: 4px;
                border-radius: 8px 8px 0 0;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            .tab-button.active {{
                background: #3b82f6;
                color: white;
            }}
            .tab-content {{
                padding: 16px;
                background: white;
                border-radius: 0 8px 8px 8px;
                min-height: 300px;
            }}
        </style>
    </head>
    <body>
        <div id="dashboard-container"></div>
        
        <script>
            // Team data passed from Python
            const teamsData = {team_data_json};
            
            // Clean and normalize team data
            const normalizeTeamData = (team) => {{
                // Default values for missing properties
                const defaultValues = {{
                    matches_played: 0,
                    wins: 0, draws: 0, losses: 0,
                    goals_scored: 0, goals_conceded: 0,
                    goals_scored_home: 0, goals_scored_away: 0,
                    goals_conceded_home: 0, goals_conceded_away: 0,
                    clean_sheets: 0,
                    xg_for_avg_overall: 0, xg_against_avg_overall: 0,
                    win_percentage: 0, draw_percentage_overall: 0, loss_percentage_ovearll: 0,
                    btts_percentage: 0, corners_per_match: 0, cards_per_match: 0
                }};
                
                // Map property names to more consistent naming scheme and provide defaults
                return {{
                    name: team.team_name || team.common_name || "Unknown Team",
                    commonName: team.common_name || team.team_name || "Unknown Team",
                    matchesPlayed: parseInt(team.matches_played) || defaultValues.matches_played,
                    wins: parseInt(team.wins) || defaultValues.wins,
                    draws: parseInt(team.draws) || defaultValues.draws,
                    losses: parseInt(team.losses) || defaultValues.losses,
                    goalsScored: parseInt(team.goals_scored) || defaultValues.goals_scored,
                    goalsConceded: parseInt(team.goals_conceded) || defaultValues.goals_conceded,
                    goalsScoredHome: parseInt(team.goals_scored_home) || defaultValues.goals_scored_home,
                    goalsScoredAway: parseInt(team.goals_scored_away) || defaultValues.goals_scored_away,
                    goalsConcededHome: parseInt(team.goals_conceded_home) || defaultValues.goals_conceded_home,
                    goalsConcededAway: parseInt(team.goals_conceded_away) || defaultValues.goals_conceded_away,
                    pointsPerGame: parseFloat(team.points_per_game) || (team.wins * 3 + team.draws) / team.matches_played || 0,
                    winPercentage: parseInt(team.win_percentage) || defaultValues.win_percentage,
                    drawPercentage: parseInt(team.draw_percentage_overall) || defaultValues.draw_percentage_overall,
                    lossPercentage: parseInt(team.loss_percentage_ovearll) || defaultValues.loss_percentage_ovearll,
                    cleanSheets: parseInt(team.clean_sheets) || defaultValues.clean_sheets,
                    xgFor: parseFloat(team.xg_for_avg_overall) || defaultValues.xg_for_avg_overall,
                    xgAgainst: parseFloat(team.xg_against_avg_overall) || defaultValues.xg_against_avg_overall,
                    bttsPercentage: parseInt(team.btts_percentage) || defaultValues.btts_percentage,
                    cornersPerMatch: parseFloat(team.corners_per_match) || defaultValues.corners_per_match,
                    cardsPerMatch: parseFloat(team.cards_per_match) || defaultValues.cards_per_match
                }};
            }};
            
            const teams = teamsData.map(normalizeTeamData);
            
            // React Component
            const {{ useState }} = React;
            const {{ 
                BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
                RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Line, LineChart
            }} = recharts;
            
            const TeamStatsDashboard = () => {{
                const [activeTab, setActiveTab] = useState('overview');
                
                // Prepare data for comparisons
                const overviewData = teams.map(team => ({{
                    name: team.commonName,
                    wins: team.wins,
                    draws: team.draws,
                    losses: team.losses
                }}));
                
                const performanceData = teams.map(team => ({{
                    name: team.commonName,
                    'Points per Game': team.pointsPerGame,
                    'Goals Scored': team.goalsScored,
                    'Goals Conceded': team.goalsConceded
                }}));
                
                const goalData = teams.map(team => [
                    {{ name: 'Home', team: team.commonName, goals: team.goalsScoredHome }},
                    {{ name: 'Away', team: team.commonName, goals: team.goalsScoredAway }}
                ]]).flat();
                
                const resultPercentageData = teams.map(team => ({{
                    name: team.commonName,
                    'Win %': team.winPercentage,
                    'Draw %': team.drawPercentage,
                    'Loss %': team.lossPercentage
                }}));
                
                const defensiveData = teams.map(team => ({{
                    name: team.commonName,
                    'Clean Sheets': team.cleanSheets,
                    'Goals Conceded': team.goalsConceded
                }}));
                
                // Calculate efficiency metrics with safety checks
                const safeDiv = (a, b) => (b && b !== 0) ? a / b : 0;
                
                // Radar data for team comparison
                const teamComparisonData = [
                    {{ stat: 'Win %', [teams[0]?.commonName]: safeDiv(teams[0]?.winPercentage, 100), [teams[1]?.commonName]: safeDiv(teams[1]?.winPercentage, 100) }},
                    {{ stat: 'Points per Game', [teams[0]?.commonName]: safeDiv(teams[0]?.pointsPerGame, 3), [teams[1]?.commonName]: safeDiv(teams[1]?.pointsPerGame, 3) }},
                    {{ stat: 'Clean Sheets %', [teams[0]?.commonName]: safeDiv(teams[0]?.cleanSheets, teams[0]?.matchesPlayed), [teams[1]?.commonName]: safeDiv(teams[1]?.cleanSheets, teams[1]?.matchesPlayed) }},
                    {{ stat: 'Goals per Match', [teams[0]?.commonName]: safeDiv(teams[0]?.goalsScored, teams[0]?.matchesPlayed * 2), [teams[1]?.commonName]: safeDiv(teams[1]?.goalsScored, teams[1]?.matchesPlayed * 2) }},
                    {{ stat: 'Corners per Match', [teams[0]?.commonName]: safeDiv(teams[0]?.cornersPerMatch, 10), [teams[1]?.commonName]: safeDiv(teams[1]?.cornersPerMatch, 10) }}
                ];
                
                return (
                    React.createElement('div', {{ className: 'bg-white rounded-lg shadow-lg p-6 max-w-6xl mx-auto' }},
                        React.createElement('h1', {{ className: 'text-2xl font-bold text-center mb-6 text-blue-800' }}, 'Team Statistics Comparison'),
                        
                        // Team Summary Cards
                        React.createElement('div', {{ className: 'grid grid-cols-1 md:grid-cols-2 gap-6 mb-8' }},
                            teams.map(team => 
                                React.createElement('div', {{ key: team.name, className: 'bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg shadow p-6' }},
                                    React.createElement('h2', {{ className: 'text-xl font-semibold text-blue-800' }}, team.commonName),
                                    React.createElement('div', {{ className: 'mt-4 grid grid-cols-3 gap-4' }},
                                        React.createElement('div', {{ className: 'text-center' }},
                                            React.createElement('p', {{ className: 'text-sm text-gray-600' }}, 'Matches'),
                                            React.createElement('p', {{ className: 'text-2xl font-bold text-blue-800' }}, team.matchesPlayed)
                                        ),
                                        React.createElement('div', {{ className: 'text-center' }},
                                            React.createElement('p', {{ className: 'text-sm text-gray-600' }}, 'Points'),
                                            React.createElement('p', {{ className: 'text-2xl font-bold text-blue-800' }}, team.wins * 3 + team.draws)
                                        ),
                                        React.createElement('div', {{ className: 'text-center' }},
                                            React.createElement('p', {{ className: 'text-sm text-gray-600' }}, 'PPG'),
                                            React.createElement('p', {{ className: 'text-2xl font-bold text-blue-800' }}, team.pointsPerGame.toFixed(2))
                                        ),
                                        React.createElement('div', {{ className: 'text-center' }},
                                            React.createElement('p', {{ className: 'text-sm text-gray-600' }}, 'W-D-L'),
                                            React.createElement('p', {{ className: 'text-lg font-semibold' }}, `${{team.wins}}-${{team.draws}}-${{team.losses}}`)
                                        ),
                                        React.createElement('div', {{ className: 'text-center' }},
                                            React.createElement('p', {{ className: 'text-sm text-gray-600' }}, 'GF-GA'),
                                            React.createElement('p', {{ className: 'text-lg font-semibold' }}, `${{team.goalsScored}}-${{team.goalsConceded}}`)
                                        ),
                                        React.createElement('div', {{ className: 'text-center' }},
                                            React.createElement('p', {{ className: 'text-sm text-gray-600' }}, 'Clean Sheets'),
                                            React.createElement('p', {{ className: 'text-lg font-semibold' }}, team.cleanSheets)
                                        )
                                    )
                                )
                            )
                        ),
                        
                        // Navigation Tabs
                        React.createElement('div', {{ className: 'flex flex-wrap mb-6 border-b' }},
                            React.createElement('button', {{ 
                                className: `tab-button ${{activeTab === 'overview' ? 'active' : ''}}`,
                                onClick: () => setActiveTab('overview') 
                            }}, 'Overview'),
                            React.createElement('button', {{ 
                                className: `tab-button ${{activeTab === 'performance' ? 'active' : ''}}`,
                                onClick: () => setActiveTab('performance') 
                            }}, 'Performance'),
                            React.createElement('button', {{ 
                                className: `tab-button ${{activeTab === 'goals' ? 'active' : ''}}`,
                                onClick: () => setActiveTab('goals') 
                            }}, 'Goals'),
                            React.createElement('button', {{ 
                                className: `tab-button ${{activeTab === 'comparison' ? 'active' : ''}}`,
                                onClick: () => setActiveTab('comparison') 
                            }}, 'Team Comparison')
                        ),
                        
                        // Tab Content
                        React.createElement('div', {{ className: 'tab-content py-4' }},
                            activeTab === 'overview' && React.createElement('div', null,
                                React.createElement('h3', {{ className: 'text-xl font-semibold mb-4' }}, 'Match Results'),
                                React.createElement(ResponsiveContainer, {{ width: '100%', height: 300 }},
                                    React.createElement(BarChart, {{ data: overviewData, layout: 'vertical' }},
                                        React.createElement(CartesianGrid, {{ strokeDasharray: '3 3' }}),
                                        React.createElement(XAxis, {{ type: 'number' }}),
                                        React.createElement(YAxis, {{ dataKey: 'name', type: 'category' }}),
                                        React.createElement(Tooltip),
                                        React.createElement(Legend),
                                        React.createElement(Bar, {{ dataKey: 'wins', fill: '#22c55e', name: 'Wins' }}),
                                        React.createElement(Bar, {{ dataKey: 'draws', fill: '#3b82f6', name: 'Draws' }}),
                                        React.createElement(Bar, {{ dataKey: 'losses', fill: '#ef4444', name: 'Losses' }})
                                    )
                                ),
                                
                                React.createElement('h3', {{ className: 'text-xl font-semibold mt-8 mb-4' }}, 'Result Percentages'),
                                React.createElement(ResponsiveContainer, {{ width: '100%', height: 300 }},
                                    React.createElement(BarChart, {{ data: resultPercentageData }},
                                        React.createElement(CartesianGrid, {{ strokeDasharray: '3 3' }}),
                                        React.createElement(XAxis, {{ dataKey: 'name' }}),
                                        React.createElement(YAxis),
                                        React.createElement(Tooltip, {{ 
                                            formatter: (value) => [`${{value}}%`, 'Percentage'] 
                                        }}),
                                        React.createElement(Legend),
                                        React.createElement(Bar, {{ dataKey: 'Win %', fill: '#22c55e', name: 'Win %' }}),
                                        React.createElement(Bar, {{ dataKey: 'Draw %', fill: '#3b82f6', name: 'Draw %' }}),
                                        React.createElement(Bar, {{ dataKey: 'Loss %', fill: '#ef4444', name: 'Loss %' }})
                                    )
                                )
                            ),
                            
                            activeTab === 'performance' && React.createElement('div', null,
                                React.createElement('h3', {{ className: 'text-xl font-semibold mb-4' }}, 'Team Performance'),
                                React.createElement(ResponsiveContainer, {{ width: '100%', height: 300 }},
                                    React.createElement(BarChart, {{ data: performanceData }},
                                        React.createElement(CartesianGrid, {{ strokeDasharray: '3 3' }}),
                                        React.createElement(XAxis, {{ dataKey: 'name' }}),
                                        React.createElement(YAxis),
                                        React.createElement(Tooltip),
                                        React.createElement(Legend),
                                        React.createElement(Bar, {{ dataKey: 'Points per Game', fill: '#3b82f6', name: 'Points per Game' }}),
                                        React.createElement(Bar, {{ dataKey: 'Goals Scored', fill: '#22c55e', name: 'Goals Scored' }}),
                                        React.createElement(Bar, {{ dataKey: 'Goals Conceded', fill: '#ef4444', name: 'Goals Conceded' }})
                                    )
                                ),
                                
                                React.createElement('h3', {{ className: 'text-xl font-semibold mt-8 mb-4' }}, 'Defensive Performance'),
                                React.createElement(ResponsiveContainer, {{ width: '100%', height: 300 }},
                                    React.createElement(BarChart, {{ data: defensiveData }},
                                        React.createElement(CartesianGrid, {{ strokeDasharray: '3 3' }}),
                                        React.createElement(XAxis, {{ dataKey: 'name' }}),
                                        React.createElement(YAxis),
                                        React.createElement(Tooltip),
                                        React.createElement(Legend),
                                        React.createElement(Bar, {{ dataKey: 'Clean Sheets', fill: '#3b82f6', name: 'Clean Sheets' }}),
                                        React.createElement(Bar, {{ dataKey: 'Goals Conceded', fill: '#ef4444', name: 'Goals Conceded' }})
                                    )
                                )
                            ),
                            
                            activeTab === 'goals' && React.createElement('div', null,
                                React.createElement('h3', {{ className: 'text-xl font-semibold mb-4' }}, 'Goals Scored: Home vs Away'),
                                React.createElement(ResponsiveContainer, {{ width: '100%', height: 300 }},
                                    React.createElement(BarChart, {{ data: goalData }},
                                        React.createElement(CartesianGrid, {{ strokeDasharray: '3 3' }}),
                                        React.createElement(XAxis, {{ dataKey: 'name' }}),
                                        React.createElement(YAxis),
                                        React.createElement(Tooltip),
                                        React.createElement(Legend),
                                        React.createElement(Bar, {{ dataKey: 'goals', fill: '#3b82f6', name: 'Goals' }})
                                    )
                                ),
                                
                                React.createElement('div', {{ className: 'grid grid-cols-1 md:grid-cols-2 gap-6 mt-8' }},
                                    teams.map(team => 
                                        React.createElement('div', {{ key: team.name, className: 'bg-white rounded-lg shadow p-4' }},
                                            React.createElement('h4', {{ className: 'text-lg font-semibold mb-2' }}, `${{team.commonName}} - Goal Analysis`),
                                            React.createElement('div', {{ className: 'space-y-2' }},
                                                React.createElement('p', null, 
                                                    React.createElement('span', {{ className: 'font-medium' }}, 'xG Per Match: '),
                                                    team.xgFor ? team.xgFor.toFixed(2) : 'N/A'
                                                ),
                                                React.createElement('p', null, 
                                                    React.createElement('span', {{ className: 'font-medium' }}, 'Actual Goals Per Match: '),
                                                    team.matchesPlayed ? (team.goalsScored / team.matchesPlayed).toFixed(2) : 'N/A'
                                                ),
                                                React.createElement('p', null, 
                                                    React.createElement('span', {{ className: 'font-medium' }}, 'Goals Scored Home: '),
                                                    team.goalsScoredHome || 'N/A'
                                                ),
                                                React.createElement('p', null, 
                                                    React.createElement('span', {{ className: 'font-medium' }}, 'Goals Scored Away: '),
                                                    team.goalsScoredAway || 'N/A'
                                                ),
                                                React.createElement('p', null, 
                                                    React.createElement('span', {{ className: 'font-medium' }}, 'BTTS Percentage: '),
                                                    `${{team.bttsPercentage || 0}}%`
                                                )
                                            )
                                        )
                                    )
                                )
                            ),
                            
                            activeTab === 'comparison' && React.createElement('div', null,
                                React.createElement('h3', {{ className: 'text-xl font-semibold mb-4' }}, 'Team Comparison'),
                                React.createElement(ResponsiveContainer, {{ width: '100%', height: 400 }},
                                    React.createElement(RadarChart, {{ outerRadius: 150, data: teamComparisonData }},
                                        React.createElement(PolarGrid),
                                        React.createElement(PolarAngleAxis, {{ dataKey: 'stat' }}),
                                        React.createElement(PolarRadiusAxis, {{ angle: 30, domain: [0, 1] }}),
                                        React.createElement(Tooltip, {{ 
                                            formatter: (value) => [value ? value.toFixed(2) : 'N/A', 'Value'] 
                                        }}),
                                        React.createElement(Legend),
                                        teams.map((team, index) => 
                                            React.createElement(Radar, {{ 
                                                key: team.name,
                                                name: team.commonName,
                                                dataKey: team.commonName,
                                                stroke: index === 0 ? '#3b82f6' : '#ef4444',
                                                fill: index === 0 ? '#3b82f6' : '#ef4444',
                                                fillOpacity: 0.5
                                            }})
                                        )
                                    )
                                ),
                                
                                React.createElement('div', {{ className: 'grid grid-cols-1 md:grid-cols-2 gap-6 mt-8' }},
                                    React.createElement('div', {{ className: 'bg-white rounded-lg shadow p-4' }},
                                        React.createElement('h4', {{ className: 'text-lg font-semibold mb-4 text-center' }}, 'Performance Comparison'),
                                        React.createElement('table', {{ className: 'min-w-full' }},
                                            React.createElement('thead', null,
                                                React.createElement('tr', {{ className: 'bg-gray-100' }},
                                                    React.createElement('th', {{ className: 'text-left p-2' }}, 'Metric'),
                                                    teams.map(team => 
                                                        React.createElement('th', {{ key: team.name, className: 'text-center p-2' }}, team.commonName)
                                                    )
                                                )
                                            ),
                                            React.createElement('tbody', null,
                                                React.createElement('tr', null,
                                                    React.createElement('td', {{ className: 'p-2 font-medium' }}, 'Points per Game'),
                                                    teams.map(team => 
                                                        React.createElement('td', {{ key: team.name, className: 'text-center p-2' }}, team.pointsPerGame ? team.pointsPerGame.toFixed(2) : 'N/A')
                                                    )
                                                ),
                                                React.createElement('tr', {{ className: 'bg-gray-50' }},
                                                    React.createElement('td', {{ className: 'p-2 font-medium' }}, 'Win %'),
                                                    teams.map(team => 
                                                        React.createElement('td', {{ key: team.name, className: 'text-center p-2' }}, `${{team.winPercentage || 0}}%`)
                                                    )
                                                ),
                                                React.createElement('tr', null,
                                                    React.createElement('td', {{ className: 'p-2 font-medium' }}, 'Clean Sheets'),
                                                    teams.map(team => 
                                                        React.createElement('td', {{ key: team.name, className: 'text-center p-2' }}, team.cleanSheets || 0)
                                                    )
                                                ),
                                                React.createElement('tr', {{ className: 'bg-gray-50' }},
                                                    React.createElement('td', {{ className: 'p-2 font-medium' }}, 'Goals Scored'),
                                                    teams.map(team => 
                                                        React.createElement('td', {{ key: team.name, className: 'text-center p-2' }}, team.goalsScored || 0)
                                                    )
                                                ),
                                                React.createElement('tr', null,
                                                    React.createElement('td', {{ className: 'p-2 font-medium' }}, 'Goals Conceded'),
                                                    teams.map(team => 
                                                        React.createElement('td', {{ key: team.name, className: 'text-center p-2' }}, team.goalsConceded || 0)
                                                    )
                                                )
                                            )
                                        )
                                    ),
                                    
                                    React.createElement('div', {{ className: 'bg-white rounded-lg shadow p-4' }},
                                        React.createElement('h4', {{ className: 'text-lg font-semibold mb-4 text-center' }}, 'Home vs Away Performance'),
                                        React.createElement('table', {{ className: 'min-w-full' }},
                                            React.createElement('thead', null,
                                                React.createElement('tr', {{ className: 'bg-gray-100' }},
                                                    React.createElement('th', {{ className: 'text-left p-2' }}, 'Team'),
                                                    React.createElement('th', {{ className: 'text-center p-2' }}, 'Home Goals'),
                                                    React.createElement('th', {{ className: 'text-center p-2' }}, 'Away Goals'),
                                                    React.createElement('th', {{ className: 'text-center p-2' }}, 'Home Conceded'),
                                                    React.createElement('th', {{ className: 'text-center p-2' }}, 'Away Conceded')
                                                )
                                            ),
                                            React.createElement('tbody', null,
                                                teams.map(team => 
                                                    React.createElement('tr', {{ key: team.name }},
                                                        React.createElement('td', {{ className: 'p-2 font-medium' }}, team.commonName),
                                                        React.createElement('td', {{ className: 'text-center p-2' }}, team.goalsScoredHome || 0),
                                                        React.createElement('td', {{ className: 'text-center p-2' }}, team.goalsScoredAway || 0),
                                                        React.createElement('td', {{ className: 'text-center p-2' }}, team.goalsConcededHome || 0),
                                                        React.createElement('td', {{ className: 'text-center p-2' }}, team.goalsConcededAway || 0)
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                );
            }};
            
            // Render the React component
            const container = document.getElementById('dashboard-container');
            ReactDOM.render(React.createElement(TeamStatsDashboard), container);
        </script>
    </body>
    </html>
    """
    
    # Display the component with appropriate height
    components.html(html_content, height=1200, scrolling=True)


def team_stats_visualization(home_team_stats, away_team_stats):
    """
    Display team statistics visualization in Streamlit
    
    Args:
        home_team_stats (dict): Home team statistics
        away_team_stats (dict): Away team statistics
    """
    # Create tabs for raw data and visualization
    viz_tab, raw_tab = st.tabs(["📊 Visualization", "📋 Raw Data"])
    
    with viz_tab:
        create_team_stats_dashboard(home_team_stats, away_team_stats)
    
    with raw_tab:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(home_team_stats.get("team_name", "Home Team"))
            st.json(home_team_stats)
        with col2:
            st.subheader(away_team_stats.get("team_name", "Away Team"))
            st.json(away_team_stats)
