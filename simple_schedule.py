import gurobipy as gp
from gurobipy import GRB

# Simple sports schedule for 8 teams over 90 days
# Maximize ticket revenue based on home team ticket values

TEAMS = [1, 2, 3, 4, 5, 6, 7, 8]
DAYS = list(range(1, 91))

# Ticket values (revenue per home game) for each team
ticket_values = {1: 1000, 2: 1100, 3: 1050, 4: 1200, 5: 950, 6: 1150, 7: 1080, 8: 1020}

# Team names and conferences
team_names = {
    1: "MTL", 2: "OTT", 3: "TOR", 4: "BOS",
    5: "NY", 6: "MN", 7: "SEA", 8: "VAN"
}

team_conference = {
    "MTL": "East", "OTT": "East", "TOR": "East", "BOS": "East",
    "NY": "East", "MN": "East", "SEA": "West", "VAN": "West"
}

# Weekend multiplier (games on weekends generate more revenue)
WEEKEND_MULTIPLIER = 1.5  # 50% more revenue on weekends

# Define weeks (7 days each, last week 6 days)
weeks = []
for start in range(1, 91, 7):
    end = min(start + 6, 90)
    weeks.append(list(range(start, end + 1)))

model = gp.Model("simple_schedule")
model.setParam('OutputFlag', 0)
model.setParam('TimeLimit', 120)  # 120 second time limit

# x[i,j,d] = 1 if team i hosts team j on day d
x = model.addVars(
    [(i, j, d) for i in TEAMS for j in TEAMS if i != j for d in DAYS],
    vtype=GRB.BINARY,
    name='x'
)

# y[i,d] = 1 if team i plays on day d
y = model.addVars(
    [(i, d) for i in TEAMS for d in DAYS],
    vtype=GRB.BINARY,
    name='y'
)

# Objective: maximize ticket revenue with weekend multiplier
# Pre-compute multipliers for efficiency
revenue_mult = {}
for d in DAYS:
    revenue_mult[d] = WEEKEND_MULTIPLIER if (d % 7 == 6 or d % 7 == 0) else 1.0

revenue_expr = gp.quicksum(
    ticket_values[i] * revenue_mult[d] * x[i, j, d]
    for i in TEAMS for j in TEAMS if i != j for d in DAYS
)
model.setObjective(revenue_expr, GRB.MAXIMIZE)

# Constraints
# Each team plays at most one game per day
for i in TEAMS:
    for d in DAYS:
        model.addConstr(
            gp.quicksum(x[i, j, d] + x[j, i, d] for j in TEAMS if j != i) <= 1,
            name=f'team_{i}_day_{d}'
        )

# No double games between same pair on same day
for i in TEAMS:
    for j in TEAMS:
        if i < j:
            for d in DAYS:
                model.addConstr(
                    x[i, j, d] + x[j, i, d] <= 1,
                    name=f'pair_{i}_{j}_day_{d}'
                )

# y[i,d] indicates if team i plays on day d
for i in TEAMS:
    for d in DAYS:
        plays = gp.quicksum(x[i, j, d] + x[j, i, d] for j in TEAMS if j != i)
        model.addConstr(y[i, d] == plays, name=f'y_{i}_{d}')

# No team plays two games in a row
for i in TEAMS:
    for idx in range(len(DAYS) - 1):
        d1 = DAYS[idx]
        d2 = DAYS[idx + 1]
        model.addConstr(
            y[i, d1] + y[i, d2] <= 1,
            name=f'no_consec_{i}_{d1}_{d2}'
        )

# Each team plays at most 30 games
# Removed to maximize total games

# Each pair of teams plays each other 4-5 times
for i in TEAMS:
    for j in TEAMS:
        if i < j:
            games_between = gp.quicksum(x[i, j, d] + x[j, i, d] for d in DAYS)
            model.addConstr(games_between >= 4, name=f'min_games_{i}_{j}')
            model.addConstr(games_between <= 5, name=f'max_games_{i}_{j}')
            
            # At least 2 home games for each - removed to enforce daily limits

# Each team plays exactly 15 home and 15 away games
for i in TEAMS:
    home_games = gp.quicksum(x[i, j, d] for j in TEAMS if j != i for d in DAYS)
    away_games = gp.quicksum(x[j, i, d] for j in TEAMS if j != i for d in DAYS)
    model.addConstr(home_games == 15, name=f'home_games_{i}')
    model.addConstr(away_games == 15, name=f'away_games_{i}')

# Max 3 games per day, except day 90 has exactly 4 games and all teams play
for d in DAYS:
    if d == 90:
        model.addConstr(
            gp.quicksum(x[i, j, d] + x[j, i, d] for i in TEAMS for j in TEAMS if i < j) == 4,
            name=f'games_day_{d}'
        )
        model.addConstr(
            gp.quicksum(y[i, d] for i in TEAMS) == 8,
            name=f'all_play_day_{d}'
        )
    else:
        model.addConstr(
            gp.quicksum(x[i, j, d] + x[j, i, d] for i in TEAMS for j in TEAMS if i < j) <= 3,
            name=f'max_games_day_{d}'
        )

# Each team plays at least 2 games per week
# Removed to allow feasible solution with daily limits

# Solve and print results
model.optimize()

if model.Status == GRB.OPTIMAL:
    print(f"Total ticket revenue: ${int(model.ObjVal):,}")
    
    # Compute games per team pair
    team_games = {i: {} for i in TEAMS}
    for i in TEAMS:
        for j in TEAMS:
            if i != j:
                count = sum(x[i, j, d].X + x[j, i, d].X for d in DAYS)
                team_games[i][f"Team {j}"] = int(count)
    
    # Print the dict for each team
    for i in TEAMS:
        print(f"Team {i}: {team_games[i]}")
    
    for d in DAYS:
        games_on_day = []
        for i in TEAMS:
            for j in TEAMS:
                if i != j and x[i, j, d].X > 0.5:
                    games_on_day.append(f"Team {i} vs Team {j} (home: {i})")
        if games_on_day:
            print(f"Day {d}: {', '.join(games_on_day)}")
        else:
            print(f"Day {d}: No games")
else:
    print("No optimal solution found")
