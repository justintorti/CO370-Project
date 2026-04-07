import gurobipy as gp
from gurobipy import GRB

# ---------------------------------------------------------------------------
# 0. Index sets
# ---------------------------------------------------------------------------
TEAMS = list(range(8))
N_DAYS = 98 
DAYS = list(range(N_DAYS))
LAST_DAY = N_DAYS - 1
N_WEEKS = 14
WEEKS = [tuple(range(7 * k, 7 * k + 7)) for k in range(N_WEEKS)]

# Placeholder distance (400km for any travel)
DIST = 400.0
COST_PER_KM = 3.50
FIXED_TRAVEL_COST = DIST * COST_PER_KM

# ---------------------------------------------------------------------------
# 1. Model & Parameters
# ---------------------------------------------------------------------------
m = gp.Model("PWHL_Schedule_Optimized")

# Focus on finding feasible solutions fast, and stop at a 5% gap
m.Params.MIPFocus = 1 
m.Params.MIPGap = 0.05
m.Params.TimeLimit = 300 # 5 minute cap for testing

# ---------------------------------------------------------------------------
# 2. Decision variables
# ---------------------------------------------------------------------------

# x[i,j,d] = 1 if team i hosts team j on day d
x = m.addVars(
    [(i, j, d) for i in TEAMS for j in TEAMS if i != j for d in DAYS],
    vtype=GRB.BINARY, name="x"
)

# g[i,d] = 1 if team i plays on day d (home or away)
g = m.addVars(TEAMS, DAYS, vtype=GRB.BINARY, name="g")

# lam[i,k,d] = 1 if team i is in city k after day d
LAM_DAYS = list(range(-1, N_DAYS))
lam = m.addVars(TEAMS, TEAMS, LAM_DAYS, vtype=GRB.BINARY, name="lam")

# z[i,d] = Travel cost for team i on day d (Continuous is faster!)
z = m.addVars(TEAMS, DAYS, lb=0, vtype=GRB.CONTINUOUS, name="z")

# ---------------------------------------------------------------------------
# 3. Objective
# ---------------------------------------------------------------------------
m.setObjective(z.sum(), GRB.MINIMIZE)

# ---------------------------------------------------------------------------
# 4. Constraints
# ---------------------------------------------------------------------------

# --- Travel Cost Logic (The Simplified Version) ---
# If team i is in city k1 on day d-1 and city k2 on day d, z[i,d] >= FIXED_COST
prev = {d: d - 1 for d in DAYS}
for i in TEAMS:
    for d in DAYS:
        for k1 in TEAMS:
            for k2 in TEAMS:
                if k1 != k2:
                    # Logic: If (lam_prev == 1 AND lam_curr == 1), then z >= Cost
                    m.addConstr(z[i, d] >= FIXED_TRAVEL_COST * (lam[i, k1, prev[d]] + lam[i, k2, d] - 1))

# --- Basic Game Rules ---
m.addConstrs((g[i, d] == gp.quicksum(x[i, j, d] + x[j, i, d] for j in TEAMS if j != i)
              for i in TEAMS for d in DAYS), name="game_ind")

m.addConstrs((x.sum(i, '*', '*') == 15 for i in TEAMS), name="home_limit")
m.addConstrs((x.sum('*', j, '*') == 15 for j in TEAMS), name="away_limit")

# Matchup limits (4-5 games total, min 2 home each)
for i in TEAMS:
    for j in TEAMS:
        if i < j:
            m.addConstr(gp.quicksum(x[i, j, d] + x[j, i, d] for d in DAYS) >= 4)
            m.addConstr(gp.quicksum(x[i, j, d] + x[j, i, d] for d in DAYS) <= 5)
        if i != j:
            m.addConstr(gp.quicksum(x[i, j, d] for d in DAYS) >= 2)

# --- Scheduling Logistics ---
m.addConstrs((g[i, d] + g[i, d+1] <= 1 for i in TEAMS for d in DAYS[:-1]), name="no_btb")
m.addConstrs((x.sum('*', '*', d) <= 3 for d in DAYS[:-1]), name="max_daily")
m.addConstr(x.sum('*', '*', LAST_DAY) == 4, name="finale_count")
m.addConstrs((g[i, LAST_DAY] == 1 for i in TEAMS), name="finale_all_play")

m.addConstrs((gp.quicksum(g[i, d] for d in week) >= 2 
              for i in TEAMS for week in WEEKS), name="min_weekly")

# --- Location Logic ---
m.addConstrs((lam[i, i, -1] == 1 for i in TEAMS), name="start_home")
m.addConstrs((lam.sum(i, '*', d) == 1 for i in TEAMS for d in LAM_DAYS), name="one_city")

for i in TEAMS:
    for d in DAYS:
        # If hosting, team i must be at city i
        m.addConstr(lam[i, i, d] >= gp.quicksum(x[i, j, d] for j in TEAMS if j != i))
        for j in TEAMS:
            if i != j:
                # If team j is away at i, team j must be at city i
                m.addConstr(lam[j, i, d] >= x[i, j, d])
        
        # If no game, stay where you were
        for k in TEAMS:
            m.addConstr(lam[i, k, d] >= lam[i, k, prev[d]] - g[i, d])

# ---------------------------------------------------------------------------
# 5. Solve
# ---------------------------------------------------------------------------
m.optimize()

if m.Status == GRB.OPTIMAL or m.Status == GRB.TIME_LIMIT:
    print(f"Total Travel Cost: ${m.ObjVal:,.2f}")
    vdict = {} # makes dictionary of variables names and values
    for var in m.getVars()[0:]:
        vdict[var.varName] = var.X
    print(vdict)
