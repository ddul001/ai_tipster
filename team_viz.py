# team_viz.py - Streamlit Cloud Compatible Version
import streamlit as st
import json
import pandas as pd
import altair as alt
from urllib.parse import quote

def team_stats_visualization(home_team_stats, away_team_stats):
    """
    Display team statistics visualization in Streamlit using native components
    instead of React for better compatibility with Streamlit Cloud
    
    Args:
        home_team_stats (dict): Home team statistics
        away_team_stats (dict): Away team statistics
    """
    # Create tabs for different views
    overview_tab, performance_tab, goals_tab, comparison_tab, raw_tab = st.tabs([
        "📊 Overview", "🏆 Performance", "⚽ Goals", "🔄 Comparison", "📋 Raw Data"
    ])
    
    # Normalize data to ensure all keys exist and handle missing values
    def normalize_team_data(team):
        defaults = {
            "team_name": "Unknown Team",
            "common_name": team.get("team_name", "Unknown Team"),
            "matches_played": 0,
            "wins": 0, 
            "draws": 0, 
            "losses": 0,
            "goals_scored": 0, 
            "goals_conceded": 0,
            "goals_scored_home": 0, 
            "goals_scored_away": 0,
            "goals_conceded_home": 0, 
            "goals_conceded_away": 0,
            "points_per_game": 0,
            "win_percentage": 0, 
            "draw_percentage_overall": 0, 
            "loss_percentage_ovearll": 0,
            "clean_sheets": 0,
            "xg_for_avg_overall": 0, 
            "xg_against_avg_overall": 0,
            "btts_percentage": 0, 
            "corners_per_match": 0, 
            "cards_per_match": 0
        }
        
        # Create a normalized data dictionary
        normalized = {}
        for key, default in defaults.items():
            value = team.get(key, default)
            # Convert to appropriate type
            if key in ["matches_played", "wins", "draws", "losses", "goals_scored", 
                      "goals_conceded", "goals_scored_home", "goals_scored_away", 
                      "goals_conceded_home", "goals_conceded_away", "clean_sheets"]:
                normalized[key] = int(value) if value else 0
            elif key in ["points_per_game", "xg_for_avg_overall", "xg_against_avg_overall", 
                        "corners_per_match", "cards_per_match"]:
                normalized[key] = float(value) if value else 0.0
            elif key in ["win_percentage", "draw_percentage_overall", "loss_percentage_ovearll", "btts_percentage"]:
                normalized[key] = float(value) if value else 0.0
            else:
                normalized[key] = value
        
        # Calculate derived metrics
        normalized["points"] = normalized["wins"] * 3 + normalized["draws"]
        if normalized["matches_played"] > 0:
            normalized["goals_per_match"] = normalized["goals_scored"] / normalized["matches_played"]
            normalized["clean_sheet_percentage"] = normalized["clean_sheets"] / normalized["matches_played"] * 100
        else:
            normalized["goals_per_match"] = 0
            normalized["clean_sheet_percentage"] = 0
            
        return normalized
    
    # Normalize team data
    home_team = normalize_team_data(home_team_stats)
    away_team = normalize_team_data(away_team_stats)
    
    # Create summary cards for both teams
    with overview_tab:
        st.header("Team Statistics Overview")
        
        # Team summary cards
        col1, col2 = st.columns(2)
        
        # Format for metric display
        with col1:
            team_name = home_team["common_name"] or home_team["team_name"]
            st.subheader(f"📊 {team_name}")
            
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            with metrics_col1:
                st.metric("Matches", home_team["matches_played"])
                st.metric("W-D-L", f"{home_team['wins']}-{home_team['draws']}-{home_team['losses']}")
            with metrics_col2:
                st.metric("Points", home_team["points"])
                st.metric("GF-GA", f"{home_team['goals_scored']}-{home_team['goals_conceded']}")
            with metrics_col3:
                st.metric("PPG", f"{home_team['points_per_game']:.2f}")
                st.metric("Clean Sheets", home_team["clean_sheets"])
                
        with col2:
            team_name = away_team["common_name"] or away_team["team_name"]
            st.subheader(f"📊 {team_name}")
            
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            with metrics_col1:
                st.metric("Matches", away_team["matches_played"])
                st.metric("W-D-L", f"{away_team['wins']}-{away_team['draws']}-{away_team['losses']}")
            with metrics_col2:
                st.metric("Points", away_team["points"])
                st.metric("GF-GA", f"{away_team['goals_scored']}-{away_team['goals_conceded']}")
            with metrics_col3:
                st.metric("PPG", f"{away_team['points_per_game']:.2f}")
                st.metric("Clean Sheets", away_team["clean_sheets"])
        
        # Match results visualization
        st.subheader("Match Results")
        
        # Prepare data for the chart
        results_data = []
        for team, label in [(home_team, "Home Team"), (away_team, "Away Team")]:
            results_data.extend([
                {"Team": team["common_name"], "Result": "Wins", "Count": team["wins"]},
                {"Team": team["common_name"], "Result": "Draws", "Count": team["draws"]},
                {"Team": team["common_name"], "Result": "Losses", "Count": team["losses"]}
            ])
        
        results_df = pd.DataFrame(results_data)
        
        # Create a horizontal bar chart
        chart = alt.Chart(results_df).mark_bar().encode(
            y=alt.Y('Team:N', title=None),
            x=alt.X('Count:Q', title='Matches'),
            color=alt.Color('Result:N', scale=alt.Scale(
                domain=['Wins', 'Draws', 'Losses'],
                range=['#22c55e', '#3b82f6', '#ef4444']
            )),
            tooltip=['Team', 'Result', 'Count']
        ).properties(
            height=200
        )
        
        st.altair_chart(chart, use_container_width=True)
        
        # Result percentages
        st.subheader("Result Percentages")
        
        percentage_data = []
        for team in [home_team, away_team]:
            percentage_data.extend([
                {"Team": team["common_name"], "Result": "Win %", "Percentage": team["win_percentage"]},
                {"Team": team["common_name"], "Result": "Draw %", "Percentage": team["draw_percentage_overall"]},
                {"Team": team["common_name"], "Result": "Loss %", "Percentage": team["loss_percentage_ovearll"]}
            ])
        
        percentage_df = pd.DataFrame(percentage_data)
        
        # Create a percentage chart
        percentage_chart = alt.Chart(percentage_df).mark_bar().encode(
            x=alt.X('Team:N', title=None),
            y=alt.Y('Percentage:Q', title='Percentage (%)'),
            color=alt.Color('Result:N', scale=alt.Scale(
                domain=['Win %', 'Draw %', 'Loss %'],
                range=['#22c55e', '#3b82f6', '#ef4444']
            )),
            tooltip=['Team', 'Result', 'Percentage']
        ).properties(
            height=300
        )
        
        st.altair_chart(percentage_chart, use_container_width=True)
    
    # Performance tab
    with performance_tab:
        st.header("Team Performance")
        
        # Team performance metrics
        performance_data = []
        for team in [home_team, away_team]:
            performance_data.extend([
                {"Team": team["common_name"], "Metric": "Points per Game", "Value": team["points_per_game"]},
                {"Team": team["common_name"], "Metric": "Goals Scored", "Value": team["goals_scored"]},
                {"Team": team["common_name"], "Metric": "Goals Conceded", "Value": team["goals_conceded"]}
            ])
        
        performance_df = pd.DataFrame(performance_data)
        
        # Create performance comparison chart
        performance_chart = alt.Chart(performance_df).mark_bar().encode(
            x=alt.X('Team:N', title=None),
            y=alt.Y('Value:Q', title='Value'),
            color=alt.Color('Metric:N', scale=alt.Scale(
                domain=['Points per Game', 'Goals Scored', 'Goals Conceded'],
                range=['#3b82f6', '#22c55e', '#ef4444']
            )),
            tooltip=['Team', 'Metric', 'Value']
        ).properties(
            height=300
        )
        
        st.altair_chart(performance_chart, use_container_width=True)
        
        # Defensive performance
        st.subheader("Defensive Performance")
        
        defensive_data = []
        for team in [home_team, away_team]:
            defensive_data.extend([
                {"Team": team["common_name"], "Metric": "Clean Sheets", "Value": team["clean_sheets"]},
                {"Team": team["common_name"], "Metric": "Goals Conceded", "Value": team["goals_conceded"]}
            ])
        
        defensive_df = pd.DataFrame(defensive_data)
        
        # Create defensive comparison chart
        defensive_chart = alt.Chart(defensive_df).mark_bar().encode(
            x=alt.X('Team:N', title=None),
            y=alt.Y('Value:Q', title='Count'),
            color=alt.Color('Metric:N', scale=alt.Scale(
                domain=['Clean Sheets', 'Goals Conceded'],
                range=['#3b82f6', '#ef4444']
            )),
            tooltip=['Team', 'Metric', 'Value']
        ).properties(
            height=300
        )
        
        st.altair_chart(defensive_chart, use_container_width=True)
    
    # Goals tab
    with goals_tab:
        st.header("Goals Analysis")
        
        # Home vs Away goals
        st.subheader("Goals Scored: Home vs Away")
        
        goals_data = []
        for team in [home_team, away_team]:
            goals_data.extend([
                {"Team": team["common_name"], "Location": "Home", "Goals": team["goals_scored_home"]},
                {"Team": team["common_name"], "Location": "Away", "Goals": team["goals_scored_away"]}
            ])
        
        goals_df = pd.DataFrame(goals_data)
        
        # Create home vs away goals chart
        goals_chart = alt.Chart(goals_df).mark_bar().encode(
            x=alt.X('Location:N', title=None),
            y=alt.Y('Goals:Q', title='Goals'),
            color=alt.Color('Team:N'),
            column='Team:N',
            tooltip=['Team', 'Location', 'Goals']
        ).properties(
            height=300
        )
        
        st.altair_chart(goals_chart, use_container_width=True)
        
        # Goal analysis cards
        col1, col2 = st.columns(2)
        
        with col1:
            team_name = home_team["common_name"]
            st.subheader(f"{team_name} - Goal Analysis")
            
            xg = home_team["xg_for_avg_overall"]
            actual_goals_per_match = home_team["goals_per_match"]
            
            st.write(f"**xG Per Match:** {xg:.2f}")
            st.write(f"**Actual Goals Per Match:** {actual_goals_per_match:.2f}")
            
            if home_team["goals_scored_home"] > 0:
                st.write(f"**Goals Scored Home:** {home_team['goals_scored_home']}")
            else:
                st.write("**Goals Scored Home:** N/A")
                
            if home_team["goals_scored_away"] > 0:
                st.write(f"**Goals Scored Away:** {home_team['goals_scored_away']}")
            else:
                st.write("**Goals Scored Away:** N/A")
                
            st.write(f"**BTTS Percentage:** {home_team['btts_percentage']}%")
            
        with col2:
            team_name = away_team["common_name"]
            st.subheader(f"{team_name} - Goal Analysis")
            
            xg = away_team["xg_for_avg_overall"]
            actual_goals_per_match = away_team["goals_per_match"]
            
            st.write(f"**xG Per Match:** {xg:.2f}")
            st.write(f"**Actual Goals Per Match:** {actual_goals_per_match:.2f}")
            
            if away_team["goals_scored_home"] > 0:
                st.write(f"**Goals Scored Home:** {away_team['goals_scored_home']}")
            else:
                st.write("**Goals Scored Home:** N/A")
                
            if away_team["goals_scored_away"] > 0:
                st.write(f"**Goals Scored Away:** {away_team['goals_scored_away']}")
            else:
                st.write("**Goals Scored Away:** N/A")
                
            st.write(f"**BTTS Percentage:** {away_team['btts_percentage']}%")
    
    # Comparison tab
    with comparison_tab:
        st.header("Team Comparison")
        
        # Create radar chart data
        metrics_to_compare = [
            "Points per Game", "Win %", "Clean Sheet %", 
            "Goals per Match", "xG Performance"
        ]
        
        # Calculate metrics that need normalization for radar chart
        home_win_pct = home_team["win_percentage"] / 100
        away_win_pct = away_team["win_percentage"] / 100
        
        home_ppg_norm = home_team["points_per_game"] / 3
        away_ppg_norm = away_team["points_per_game"] / 3
        
        home_cs_pct = home_team["clean_sheets"] / max(1, home_team["matches_played"])
        away_cs_pct = away_team["clean_sheets"] / max(1, away_team["matches_played"])
        
        home_gpm = home_team["goals_scored"] / max(1, home_team["matches_played"]) / 3
        away_gpm = away_team["goals_scored"] / max(1, away_team["matches_played"]) / 3
        
        home_xg_perf = 0.5
        if home_team["xg_for_avg_overall"] > 0 and home_team["matches_played"] > 0:
            home_xg_perf = min(1, home_team["goals_scored"] / (home_team["xg_for_avg_overall"] * home_team["matches_played"]))
        
        away_xg_perf = 0.5
        if away_team["xg_for_avg_overall"] > 0 and away_team["matches_played"] > 0:
            away_xg_perf = min(1, away_team["goals_scored"] / (away_team["xg_for_avg_overall"] * away_team["matches_played"]))
        
        # Prepare radar data
        radar_data = [
            {"Metric": "Points per Game", home_team["common_name"]: home_ppg_norm, away_team["common_name"]: away_ppg_norm},
            {"Metric": "Win %", home_team["common_name"]: home_win_pct, away_team["common_name"]: away_win_pct},
            {"Metric": "Clean Sheet %", home_team["common_name"]: home_cs_pct, away_team["common_name"]: away_cs_pct},
            {"Metric": "Goals per Match", home_team["common_name"]: home_gpm, away_team["common_name"]: away_gpm},
            {"Metric": "xG Performance", home_team["common_name"]: home_xg_perf, away_team["common_name"]: away_xg_perf}
        ]
        
        # Since we can't easily create radar charts in Altair, we'll use a more direct visualization
        # Create a performance comparison table instead
        st.subheader("Performance Metrics")
        
        comparison_table = pd.DataFrame([
            {"Metric": "Points per Game", home_team["common_name"]: f"{home_team['points_per_game']:.2f}", away_team["common_name"]: f"{away_team['points_per_game']:.2f}"},
            {"Metric": "Win %", home_team["common_name"]: f"{home_team['win_percentage']}%", away_team["common_name"]: f"{away_team['win_percentage']}%"},
            {"Metric": "Clean Sheets", home_team["common_name"]: home_team["clean_sheets"], away_team["common_name"]: away_team["clean_sheets"]},
            {"Metric": "Goals Scored", home_team["common_name"]: home_team["goals_scored"], away_team["common_name"]: away_team["goals_scored"]},
            {"Metric": "Goals Conceded", home_team["common_name"]: home_team["goals_conceded"], away_team["common_name"]: away_team["goals_conceded"]}
        ])
        
        st.table(comparison_table.set_index("Metric"))
        
        # Home vs Away performance
        st.subheader("Home vs Away Performance")
        
        home_away_table = pd.DataFrame([
            {"Team": home_team["common_name"], "Home Goals": home_team["goals_scored_home"], "Away Goals": home_team["goals_scored_away"], 
             "Home Conceded": home_team["goals_conceded_home"], "Away Conceded": home_team["goals_conceded_away"]},
            {"Team": away_team["common_name"], "Home Goals": away_team["goals_scored_home"], "Away Goals": away_team["goals_scored_away"], 
             "Home Conceded": away_team["goals_conceded_home"], "Away Conceded": away_team["goals_conceded_away"]}
        ])
        
        st.table(home_away_table.set_index("Team"))
    
    # Raw data tab
    with raw_tab:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(home_team_stats.get("team_name", "Home Team"))
            st.json(home_team_stats)
        with col2:
            st.subheader(away_team_stats.get("team_name", "Away Team"))
            st.json(away_team_stats)
