import gurobipy as gp
from gurobipy import GRB
 
# ---------------------------------------------------------------------------
# 0.  Index sets
# ---------------------------------------------------------------------------
TEAMS = list(range(8))
TEAM_NAMES = ["Montreal", "Ottawa", "Toronto", "Boston",
              "New York", "Minnesota", "Seattle", "Vancouver"]
 
N_DAYS   = 98          # days 1..98  (0-indexed: 0..97)
DAYS     = list(range(N_DAYS))       # 0-indexed
LAST_DAY = N_DAYS - 1               # index 97
 
# Week k (0-indexed) covers days 7k .. 7k+6
N_WEEKS = 14
WEEKS   = [tuple(range(7 * k, 7 * k + 7)) for k in range(N_WEEKS)]
 
# ---------------------------------------------------------------------------
# 1.  Constants (placeholder values)
# ---------------------------------------------------------------------------
 
# Travel cost matrix C[i][j] in USD (symmetric, rough great-circle estimates)
# Hard-coded values for the eight cities in the order:
# Montreal, Ottawa, Toronto, Boston, New York, Minnesota, Seattle, Vancouver
C = {
    (0, 0): 0.00, (0, 1): 579.53, (0, 2): 1763.72, (0, 3): 1409.89,
    (0, 4): 1868.36, (0, 5): 5388.80, (0, 6): 12858.62, (0, 7): 12904.37,
    (1, 0): 579.53, (1, 1): 0.00, (1, 2): 1233.66, (1, 3): 1761.42,
    (1, 4): 1894.14, (1, 5): 4814.42, (1, 6): 12330.86, (1, 7): 12390.80,
    (2, 0): 1763.72, (2, 1): 1233.66, (2, 2): 0.00, (2, 3): 2419.44,
    (2, 4): 1924.85, (2, 5): 3897.42, (2, 6): 11638.46, (2, 7): 11758.74,
    (3, 0): 1409.89, (3, 1): 1761.42, (3, 2): 2419.44, (3, 3): 0.00,
    (3, 4): 1072.70, (3, 5): 6314.30, (3, 6): 13999.15, (3, 7): 14086.98,
    (4, 0): 1868.36, (4, 1): 1894.14, (4, 2): 1924.85, (4, 3): 1072.70,
    (4, 4): 0.00, (4, 5): 5725.65, (4, 6): 13528.10, (4, 7): 13665.67,
    (5, 0): 5388.80, (5, 1): 4814.42, (5, 2): 3897.42, (5, 3): 6314.30,
    (5, 4): 5725.65, (5, 5): 0.00, (5, 6): 7834.31, (5, 7): 8023.02,
    (6, 0): 12858.62, (6, 1): 12330.86, (6, 2): 11638.46, (6, 3): 13999.15,
    (6, 4): 13528.10, (6, 5): 7834.31, (6, 6): 0.00, (6, 7): 670.06,
    (7, 0): 12904.37, (7, 1): 12390.80, (7, 2): 11758.74, (7, 3): 14086.98,
    (7, 4): 13665.67, (7, 5): 8023.02, (7, 6): 670.06, (7, 7): 0.00,
}
 
# ---------------------------------------------------------------------------
# 2.  Model
# ---------------------------------------------------------------------------
m = gp.Model("PWHL_Schedule")
m.setParam("OutputFlag", 1)
 
# ---------------------------------------------------------------------------
# 3.  Decision variables
# ---------------------------------------------------------------------------
 
# x[i,j,d] = 1  iff  team i hosts team j on day d
x = m.addVars(
    [(i, j, d) for i in TEAMS for j in TEAMS if i != j for d in DAYS],
    vtype=GRB.BINARY, name="x"
)
 
# g[i,d] = 1  iff  team i plays on day d  (home or away)
g = m.addVars(
    [(i, d) for i in TEAMS for d in DAYS],
    vtype=GRB.BINARY, name="g"
)
 
# lam[i,k,d] = 1  iff  team i is in city k after day d
# d ranges over {-1, 0, ..., N_DAYS-1}  (d=-1 is the "before season" state)
# We use d_idx = d+1 so d_idx ∈ {0, ..., N_DAYS}
LAM_DAYS = list(range(-1, N_DAYS))   # -1 = initial state
 
lam = m.addVars(
    [(i, k, d) for i in TEAMS for k in TEAMS for d in LAM_DAYS],
    vtype=GRB.BINARY, name="lam"
)
 
# w[i,j,k,d] = x[i,j,d] * lam[i,k,d-1]   (linearisation for travel cost)
w = m.addVars(
    [(i, j, k, d) for i in TEAMS for j in TEAMS if i != j
                  for k in TEAMS for d in DAYS],
    vtype=GRB.BINARY, name="w"
)
 
# ---------------------------------------------------------------------------
# 4.  Objective: minimise total travel cost
#     For each game (i hosts j on day d):
#       home team i travels from its previous city k  ->  city i  (cost C[k,i])
#       away team j travels from its previous city k  ->  city i  (cost C[k,i])
#     We need two w-style variables: one tracking where i was, one where j was.
# ---------------------------------------------------------------------------
 
# For away team travel we need v[i,j,k,d] = x[i,j,d] * lam[j,k,d-1]
v = m.addVars(
    [(i, j, k, d) for i in TEAMS for j in TEAMS if i != j
                  for k in TEAMS for d in DAYS],
    vtype=GRB.BINARY, name="v"
)
 
travel_cost = (
    gp.quicksum(w[i, j, k, d] * C[k, i]
                for i in TEAMS for j in TEAMS if i != j
                for k in TEAMS for d in DAYS)
    +
    gp.quicksum(v[i, j, k, d] * C[k, i]
                for i in TEAMS for j in TEAMS if i != j
                for k in TEAMS for d in DAYS)
)
 
m.setObjective(travel_cost, GRB.MINIMIZE)
 
# ---------------------------------------------------------------------------
# 5.  Constraints
# ---------------------------------------------------------------------------
 
# --- Game-played indicator ---------------------------------------------------
m.addConstrs(
    (g[i, d] == gp.quicksum(x[i, j, d] + x[j, i, d] for j in TEAMS if j != i)
     for i in TEAMS for d in DAYS),
    name="game_indicator"
)
 
# --- 15 home games per team --------------------------------------------------
m.addConstrs(
    (gp.quicksum(x[i, j, d] for j in TEAMS if j != i for d in DAYS) == 15
     for i in TEAMS),
    name="home_games"
)
 
# --- 15 away games per team --------------------------------------------------
m.addConstrs(
    (gp.quicksum(x[i, j, d] for i in TEAMS if i != j for d in DAYS) == 15
     for j in TEAMS),
    name="away_games"
)
 
# --- Each pair plays 4 or 5 times total  (at least 2 each direction) ---------
m.addConstrs(
    (gp.quicksum(x[i, j, d] + x[j, i, d] for d in DAYS) >= 4
     for i in TEAMS for j in TEAMS if i < j),
    name="min_matchups"
)
m.addConstrs(
    (gp.quicksum(x[i, j, d] + x[j, i, d] for d in DAYS) <= 5
     for i in TEAMS for j in TEAMS if i < j),
    name="max_matchups"
)
 
# --- At least 2 home AND 2 away per pair (from document) --------------------
m.addConstrs(
    (gp.quicksum(x[i, j, d] for d in DAYS) >= 2
     for i in TEAMS for j in TEAMS if i != j),
    name="min_home_per_pair"
)
 
# --- No back-to-back games ---------------------------------------------------
m.addConstrs(
    (g[i, d] + g[i, d + 1] <= 1
     for i in TEAMS for d in DAYS[:-1]),
    name="no_back_to_back"
)
 
# --- At most 3 games per day (4 teams on ice simultaneously) -----------------
m.addConstrs(
    (gp.quicksum(x[i, j, d] for i in TEAMS for j in TEAMS if i != j) <= 3
     for d in DAYS[:-1]),   # last day fixed to 4 below
    name="max_games_per_day"
)
 
# --- Exactly 4 games on last day ---------------------------------------------
m.addConstr(
    gp.quicksum(x[i, j, LAST_DAY] for i in TEAMS for j in TEAMS if i != j) == 4,
    name="last_day_games"
)
 
# --- Every team plays on last day --------------------------------------------
m.addConstrs(
    (g[i, LAST_DAY] == 1 for i in TEAMS),
    name="all_play_last_day"
)
 
# --- Each team plays at least twice per week ----------------------------------
m.addConstrs(
    (gp.quicksum(g[i, d] for d in week) >= 2
     for i in TEAMS for week in WEEKS),
    name="min_games_per_week"
)
 
# --- Location constraints ----------------------------------------------------
 
# Initial location: each team is at their home city before day 0
m.addConstrs(
    (lam[i, i, -1] == 1 for i in TEAMS),
    name="init_loc_home"
)
m.addConstrs(
    (lam[i, k, -1] == 0 for i in TEAMS for k in TEAMS if k != i),
    name="init_loc_away"
)
 
# Exactly one location per team per day
m.addConstrs(
    (gp.quicksum(lam[i, k, d] for k in TEAMS) == 1
     for i in TEAMS for d in LAM_DAYS),
    name="one_loc_per_day"
)
 
# Home game => team i ends the day at city i
m.addConstrs(
    (lam[i, i, d] >= x[i, j, d]
     for i in TEAMS for j in TEAMS if i != j for d in DAYS),
    name="home_sets_loc"
)
 
# Away game => team j ends the day at host city i
m.addConstrs(
    (lam[j, i, d] >= x[i, j, d]
     for i in TEAMS for j in TEAMS if i != j for d in DAYS),
    name="away_sets_loc"
)
 
# On an off-day, team stays put (if they were in k and have no game, stay in k)
m.addConstrs(
    (lam[i, k, d] >= lam[i, k, d - 1] - g[i, d]
     for i in TEAMS for k in TEAMS for d in DAYS),
    name="stay_put"
)
 
# --- Linearisation of w[i,j,k,d] = x[i,j,d] * lam[i,k,d-1] ----------------
prev = {d: d - 1 for d in DAYS}
prev[0] = -1
 
m.addConstrs(
    (w[i, j, k, d] <= x[i, j, d]
     for i in TEAMS for j in TEAMS if i != j for k in TEAMS for d in DAYS),
    name="w_ub_x"
)
m.addConstrs(
    (w[i, j, k, d] <= lam[i, k, prev[d]]
     for i in TEAMS for j in TEAMS if i != j for k in TEAMS for d in DAYS),
    name="w_ub_lam"
)
m.addConstrs(
    (w[i, j, k, d] >= x[i, j, d] + lam[i, k, prev[d]] - 1
     for i in TEAMS for j in TEAMS if i != j for k in TEAMS for d in DAYS),
    name="w_lb"
)
 
# --- Linearisation of v[i,j,k,d] = x[i,j,d] * lam[j,k,d-1] ----------------
m.addConstrs(
    (v[i, j, k, d] <= x[i, j, d]
     for i in TEAMS for j in TEAMS if i != j for k in TEAMS for d in DAYS),
    name="v_ub_x"
)
m.addConstrs(
    (v[i, j, k, d] <= lam[j, k, prev[d]]
     for i in TEAMS for j in TEAMS if i != j for k in TEAMS for d in DAYS),
    name="v_ub_lam"
)
m.addConstrs(
    (v[i, j, k, d] >= x[i, j, d] + lam[j, k, prev[d]] - 1
     for i in TEAMS for j in TEAMS if i != j for k in TEAMS for d in DAYS),
    name="v_lb"
)
 
# ---------------------------------------------------------------------------
# 6.  Write model to file
# ---------------------------------------------------------------------------
LP_FILE = "pwhl_schedule.lp"
m.write(LP_FILE)
print(f"\nModel written to {LP_FILE}")
print(f"  Variables : {m.NumVars}")
print(f"  Constraints: {m.NumConstrs}")