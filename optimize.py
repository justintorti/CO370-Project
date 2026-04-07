from gurobipy import *
import pandas as pd 

primal = read('sports_schedule.lp')
primal.optimize()

print(primal.ObjVal)
primal.printAttr('X')

vdict = {} # makes dictionary of variables names and values
for var in primal.getVars()[0:]:
    vdict[var.varName] = var.X

with open('variable_values.txt', 'w') as fout:
    fout.write(f'Objective: {primal.ObjVal}\n')
    for name in sorted(vdict):
        fout.write(f'{name} {vdict[name]}\n')
