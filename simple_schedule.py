import os
os.environ['GRB_LICENSE_FILE'] = "/Users/zachcohen/Desktop/CO370 files/gurobi.lic"

import csv
import webbrowser
from html import escape

import gurobipy as gp
from gurobipy import GRB

# Simple sports schedule for 8 teams over 90 days
# Maximize ticket revenue based on home team ticket values

TEAMS = [1, 2, 3, 4, 5, 6, 7, 8]
DAYS = list(range(1, 91))
DAYS0 = [0] + DAYS
LOCATIONS = TEAMS
home_location = {i: i for i in TEAMS}

# Ticket values (revenue per home game) for each team
ticket_values = {1: 863202, 2: 466804, 3: 673548, 4: 334732, 5: 188024, 6: 520715, 7: 916369, 8: 545760}

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

# Distance matrix (km) between cities
# Teams: 1=MTL, 2=OTT, 3=TOR, 4=BOS, 5=NY, 6=MN, 7=SEA, 8=VAN
# Distances cut in half for busses
distances = {
    (1, 1): 0,    (1, 2): 67,  (1, 3): 122,  (1, 4): 160,  (1, 5): 611,  (1, 6): 1998, (1, 7): 4341, (1, 8): 4551,
    (2, 1): 67,  (2, 2): 0,    (2, 3): 152,  (2, 4): 910,  (2, 5): 695,  (2, 6): 1390, (2, 7): 4071, (2, 8): 4282,
    (3, 1): 122,  (3, 2): 152,  (3, 3): 0,    (3, 4): 887,  (3, 5): 739,  (3, 6): 1461, (3, 7): 4142, (3, 8): 4352,
    (4, 1): 160,  (4, 2): 910,  (4, 3): 887,  (4, 4): 0,    (4, 5): 184,  (4, 6): 2227, (4, 7): 4908, (4, 8): 5124,
    (5, 1): 611,  (5, 2): 695,  (5, 3): 739,  (5, 4): 184,  (5, 5): 0,    (5, 6): 1897, (5, 7): 4579, (5, 8): 4792,
    (6, 1): 1998, (6, 2): 1390, (6, 3): 1461, (6, 4): 2227, (6, 5): 1897, (6, 6): 0,    (6, 7): 2684, (6, 8): 2899,
    (7, 1): 4341, (7, 2): 4071, (7, 3): 4142, (7, 4): 4908, (7, 5): 4579, (7, 6): 2684, (7, 7): 0,    (7, 8): 76,
    (8, 1): 4551, (8, 2): 4282, (8, 3): 4352, (8, 4): 5124, (8, 5): 4792, (8, 6): 2899, (8, 7): 76,  (8, 8): 0
}

# Travel cost = distance (km) * $12/km
COST_PER_KM = 12
travel_cost = {(l1, l2): distances[(l1, l2)] * COST_PER_KM for l1 in LOCATIONS for l2 in LOCATIONS}

# TV slot revenue
TV_SLOT_REVENUE = 25_000  # $25,000 per filled TV slot

# Create mapping from team number to conference
team_by_number = {
    1: "East", 2: "East", 3: "East", 4: "East",
    5: "East", 6: "East", 7: "West", 8: "West"
}

# Weekdays are Monday-Friday (d % 7 in {1,2,3,4,5}, not 0 or 6)
WEEKDAYS = [d for d in DAYS if d % 7 not in [0, 6]]

# Weekends are Saturday and Sunday (d % 7 in {0, 6})
WEEKENDS = [d for d in DAYS if d % 7 in [0, 6]]

# Define weeks (7 days each, last week 6 days)
weeks = []
for start in range(1, 91, 7):
    end = min(start + 6, 90)
    weeks.append(list(range(start, end + 1)))

model = gp.Model("simple_schedule")
model.setParam('OutputFlag', 1)
model.setParam('TimeLimit', 300)  # 300 second time limit
model.setParam('MIPFocus', 1)  # Focus on finding feasible solutions quickly
model.setParam('Heuristics', 0.5)  # Increase heuristic effort (0-1)
model.setParam('Cuts', 1)  # Reduce cut generation to speed up


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

# loc[i,d,l] = 1 if team i is at location l on day d
loc = model.addVars(
    [(i, d, l) for i in TEAMS for d in DAYS0 for l in LOCATIONS],
    vtype=GRB.BINARY,
    name='loc'
)

# travel[i,d,l1,l2] = 1 if team i departs location l1 on day d-1 and arrives at l2 on day d
travel = model.addVars(
    [(i, d, l1, l2) for i in TEAMS for d in DAYS for l1 in LOCATIONS for l2 in LOCATIONS],
    vtype=GRB.BINARY,
    name='travel'
)

# tv_west[d] = 1 if West Coast TV slot is filled on weekday d
tv_west = model.addVars(
    WEEKDAYS,
    vtype=GRB.BINARY,
    name='tv_west'
)

# tv_east[d] = 1 if East Coast TV slot is filled on weekday d
tv_east = model.addVars(
    WEEKDAYS,
    vtype=GRB.BINARY,
    name='tv_east'
)

# tv_weekend[d, s] = 1 if weekend TV slot s is filled on day d (2 slots per day, any team can fill)
tv_weekend = model.addVars(
    [(d, s) for d in WEEKENDS for s in [1, 2]],
    vtype=GRB.BINARY,
    name='tv_weekend'
)

# Objective: maximize ticket revenue with weekend multiplier + TV slot revenue
# Pre-compute multipliers for efficiency
revenue_mult = {}
for d in DAYS:
    revenue_mult[d] = WEEKEND_MULTIPLIER if (d % 7 == 6 or d % 7 == 0) else 1.0

ticket_revenue = gp.quicksum(
    ticket_values[i] * revenue_mult[d] * x[i, j, d]
    for i in TEAMS for j in TEAMS if i != j for d in DAYS
)

tv_revenue = gp.quicksum(
    TV_SLOT_REVENUE * (tv_west[d] + tv_east[d])
    for d in WEEKDAYS
) + gp.quicksum(
    TV_SLOT_REVENUE * tv_weekend[d, s]
    for d in WEEKENDS for s in [1, 2]
)

travel_cost_term = gp.quicksum(
    travel_cost[(l1, l2)] * travel[i, d, l1, l2]
    for i in TEAMS for d in DAYS for l1 in LOCATIONS for l2 in LOCATIONS
)

revenue_expr = ticket_revenue + tv_revenue - travel_cost_term
model.setObjective(revenue_expr, GRB.MAXIMIZE)

printed_best_at_30s = False

def print_callback_solution(cb_model):
    best_obj = cb_model.cbGet(GRB.Callback.MIP_OBJBST)
    runtime = cb_model.cbGet(GRB.Callback.RUNTIME)
    print("\n--- Best feasible solution reached at 30 seconds ---")
    print(f"Runtime: {runtime:.1f}s")
    print(f"  Incumbent objective: ${int(best_obj):,}")

    for d in DAYS:
        games_on_day = []
        for i in TEAMS:
            for j in TEAMS:
                if i != j and cb_model.cbGetSolution(x[i, j, d]) > 0.5:
                    games_on_day.append(f"{team_names[i]} vs {team_names[j]} (home: {team_names[i]})")

        tv_info = ""
        if d in WEEKDAYS:
            tv_slots = []
            if cb_model.cbGetSolution(tv_west[d]) > 0.5:
                tv_slots.append("West TV")
            if cb_model.cbGetSolution(tv_east[d]) > 0.5:
                tv_slots.append("East TV")
            if tv_slots:
                tv_info = f" [{', '.join(tv_slots)}]"
        elif d in WEEKENDS:
            tv_slots = []
            if cb_model.cbGetSolution(tv_weekend[d, 1]) > 0.5:
                tv_slots.append("TV Slot 1")
            if cb_model.cbGetSolution(tv_weekend[d, 2]) > 0.5:
                tv_slots.append("TV Slot 2")
            if tv_slots:
                tv_info = f" [{', '.join(tv_slots)}]"

        game_count = len(games_on_day)
        game_label = "game" if game_count == 1 else "games"
        day_label = f"WDay {d}" if d in WEEKENDS else f"Day {d}"

        if games_on_day:
            print(f"{day_label} ({game_count} {game_label}): {', '.join(games_on_day)}{tv_info}")
        else:
            print(f"{day_label} (0 games): No games{tv_info}")


def best_solution_callback(cb_model, where):
    global printed_best_at_30s
    if where == GRB.Callback.MIP:
        runtime = cb_model.cbGet(GRB.Callback.RUNTIME)
        if runtime >= 30.0 and not printed_best_at_30s:
            printed_best_at_30s = True
            if cb_model.cbGet(GRB.Callback.MIP_SOLCNT) > 0:
                print_callback_solution(cb_model)
            else:
                print("\n--- No feasible incumbent available at 30 seconds ---")


def write_schedule_csv(filename, schedule):
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Day', 'DayType', 'Games', 'TV'])
        for d in sorted(schedule):
            row = schedule[d]
            writer.writerow([
                d,
                'Weekend' if d in WEEKENDS else 'Weekday',
                '; '.join(row['games']) if row['games'] else 'No games',
                row['tv'] or ''
            ])


def write_schedule_html(filename, schedule, weeks):
    with open(filename, 'w') as f:
        f.write('<!DOCTYPE html>\n<html lang="en">\n<head>\n')
        f.write('<meta charset="UTF-8">\n<title>Schedule Calendar</title>\n')
        f.write('<style>body{font-family:Arial,sans-serif;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #999;padding:8px;vertical-align:top;}th{background:#004080;color:#fff;}td.weekend{background:#f7f7f7;}td.empty{background:#eee;}</style>\n')
        f.write('</head>\n<body>\n')
        f.write('<h1>Schedule Calendar</h1>\n')
        f.write('<table>\n<thead><tr><th>Week</th>')
        f.write(''.join(f'<th>Day {day}</th>' for day in range(1, 8)))
        f.write('</tr></thead>\n<tbody>\n')

        for week_idx, week_days in enumerate(weeks, start=1):
            f.write(f'<tr><th>Week {week_idx}</th>')
            for d in week_days:
                cell = schedule.get(d, {'games': [], 'tv': ''})
                classes = ['weekend'] if d in WEEKENDS else []
                cell_html = ''
                if cell['games']:
                    cell_html += '<br>'.join(escape(item) for item in cell['games'])
                else:
                    cell_html += '<em>No games</em>'
                if cell['tv']:
                    cell_html += f'<div><strong>{escape(cell["tv"])}</strong></div>'
                f.write(f'<td class="{" ".join(classes)}"><div><strong>Day {d}</strong></div>{cell_html}</td>')
            f.write('</tr>\n')

        f.write('</tbody>\n</table>\n</body>\n</html>\n')

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

# Each team is at exactly one location each day, including day 0
for i in TEAMS:
    for d in DAYS0:
        model.addConstr(
            gp.quicksum(loc[i, d, l] for l in LOCATIONS) == 1,
            name=f'loc_one_{i}_{d}'
        )

# Initialize day 0 at home for every team
for i in TEAMS:
    model.addConstr(loc[i, 0, home_location[i]] == 1, name=f'loc_day0_home_{i}')

# Link game decisions to locations on game days
for i in TEAMS:
    for d in DAYS:
        model.addConstr(
            loc[i, d, i] >= gp.quicksum(x[i, j, d] for j in TEAMS if j != i),
            name=f'loc_home_game_{i}_{d}'
        )
        for l in LOCATIONS:
            if l != i:
                model.addConstr(
                    loc[i, d, l] >= x[l, i, d],
                    name=f'loc_away_game_{i}_{d}_{l}'
                )

# Carry forward location on rest days
for i in TEAMS:
    for d in DAYS:
        for l in LOCATIONS:
            model.addConstr(
                loc[i, d, l] >= loc[i, d-1, l] - y[i, d],
                name=f'loc_carry_lower_{i}_{d}_{l}'
            )
            model.addConstr(
                loc[i, d, l] <= loc[i, d-1, l] + y[i, d],
                name=f'loc_carry_upper_{i}_{d}_{l}'
            )

# Travel leg definition between consecutive days
for i in TEAMS:
    for d in DAYS:
        for l1 in LOCATIONS:
            model.addConstr(
                gp.quicksum(travel[i, d, l1, l2] for l2 in LOCATIONS) == loc[i, d-1, l1],
                name=f'travel_out_{i}_{d}_{l1}'
            )
        for l2 in LOCATIONS:
            model.addConstr(
                gp.quicksum(travel[i, d, l1, l2] for l1 in LOCATIONS) == loc[i, d, l2],
                name=f'travel_in_{i}_{d}_{l2}'
            )

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
for i in TEAMS:
    for week_idx, week_days in enumerate(weeks):
        games_in_week = gp.quicksum(y[i, d] for d in week_days)
        model.addConstr(
            games_in_week >= 2,
            name=f'min_games_per_week_{i}_{week_idx}'
        )

# TV slot constraints (only on weekdays)
for d in WEEKDAYS:
    # West Coast TV slot indicator
    west_games = gp.quicksum(x[i, j, d] for i in [7, 8] for j in TEAMS if j != i)
    
    # Upper bound: W_d <= sum of west games
    model.addConstr(
        tv_west[d] <= west_games,
        name=f'tv_west_upper_{d}'
    )
    
    # Lower bound: each west game forces the slot to 1
    for i in [7, 8]:
        for j in TEAMS:
            if j != i:
                model.addConstr(
                    x[i, j, d] <= tv_west[d],
                    name=f'tv_west_lower_{i}_{j}_{d}'
                )
    
    # East Coast TV slot indicator
    east_games = gp.quicksum(x[i, j, d] for i in [1, 2, 3, 4, 5, 6] for j in TEAMS if j != i)
    
    # Upper bound: E_d <= sum of east games
    model.addConstr(
        tv_east[d] <= east_games,
        name=f'tv_east_upper_{d}'
    )
    
    # Lower bound: each east game forces the slot to 1
    for i in [1, 2, 3, 4, 5, 6]:
        for j in TEAMS:
            if j != i:
                model.addConstr(
                    x[i, j, d] <= tv_east[d],
                    name=f'tv_east_lower_{i}_{j}_{d}'
                )

# TV slot constraints (on weekends)
for d in WEEKENDS:
    # Total games on this weekend day
    any_game = gp.quicksum(x[i, j, d] for i in TEAMS for j in TEAMS if j != i)
    
    # Upper bound: total weekend slots cannot exceed number of games
    model.addConstr(
        tv_weekend[d, 1] + tv_weekend[d, 2] <= any_game,
        name=f'tv_weekend_total_{d}'
    )

# Each team plays at least 2 games per week
# Removed to allow feasible solution with daily limits

# Solve and print results
model.optimize(best_solution_callback)

if model.Status == GRB.OPTIMAL or (model.Status == GRB.TIME_LIMIT and model.SolCount > 0):
    # Calculate revenue breakdown
    ticket_rev = sum(
        ticket_values[i] * revenue_mult[d] * x[i, j, d].X
        for i in TEAMS for j in TEAMS if i != j for d in DAYS
    )
    weekday_tv_rev = sum(
        TV_SLOT_REVENUE * (tv_west[d].X + tv_east[d].X)
        for d in WEEKDAYS
    )
    weekend_tv_rev = sum(
        TV_SLOT_REVENUE * tv_weekend[d, s].X
        for d in WEEKENDS for s in [1, 2]
    )
    tv_rev = weekday_tv_rev + weekend_tv_rev
    travel_cost_val = sum(
        travel_cost[(l1, l2)] * travel[i, d, l1, l2].X
        for i in TEAMS for d in DAYS for l1 in LOCATIONS for l2 in LOCATIONS
    )
    total_rev = ticket_rev + tv_rev - travel_cost_val
    
    print(f"Total Revenue: ${int(total_rev):,}")
    print(f"  Ticket Revenue: ${int(ticket_rev):,}")
    print(f"  TV Slot Revenue: ${int(tv_rev):,}")
    print(f"  Travel Cost: ${int(travel_cost_val):,}")
    print(f"    (Weekday TV: ${int(weekday_tv_rev):,}, Weekend TV: ${int(weekend_tv_rev):,})")
    print()
    
    # Compute games per team pair
    team_games = {i: {} for i in TEAMS}
    for i in TEAMS:
        for j in TEAMS:
            if i != j:
                count = sum(x[i, j, d].X + x[j, i, d].X for d in DAYS)
                team_games[i][team_names[j]] = int(count)
    
    # Print the dict for each team
    for i in TEAMS:
        print(f"{team_names[i]}: {team_games[i]}")
    
    print()
    schedule = {}
    for d in DAYS:
        games_on_day = []
        for i in TEAMS:
            for j in TEAMS:
                if i != j and x[i, j, d].X > 0.5:
                    games_on_day.append(f"{team_names[i]} vs {team_names[j]} (home: {team_names[i]})")

        tv_info = ""
        if d in WEEKDAYS:
            tv_slots = []
            if tv_west[d].X > 0.5:
                tv_slots.append("West TV")
            if tv_east[d].X > 0.5:
                tv_slots.append("East TV")
            if tv_slots:
                tv_info = f"{', '.join(tv_slots)}"
        elif d in WEEKENDS:
            tv_slots = []
            if tv_weekend[d, 1].X > 0.5:
                tv_slots.append("TV Slot 1")
            if tv_weekend[d, 2].X > 0.5:
                tv_slots.append("TV Slot 2")
            if tv_slots:
                tv_info = f"{', '.join(tv_slots)}"

        game_count = len(games_on_day)
        game_label = "game" if game_count == 1 else "games"
        day_label = f"WDay {d}" if d in WEEKENDS else f"Day {d}"

        schedule[d] = {
            'games': games_on_day,
            'tv': tv_info,
        }

        if games_on_day:
            print(f"{day_label} ({game_count} {game_label}): {', '.join(games_on_day)}" + (f" [{tv_info}]" if tv_info else ""))
        else:
            print(f"{day_label} (0 games): No games" + (f" [{tv_info}]" if tv_info else ""))

    write_schedule_csv('schedule.csv', schedule)
    write_schedule_html('schedule.html', schedule, weeks)
    print('\nSaved presentable schedule to schedule.csv and schedule.html')
    webbrowser.open('schedule.html')
else:
    print("No optimal solution found")
