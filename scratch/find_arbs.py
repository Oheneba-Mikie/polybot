# Let's define the odds extracted from both bookies in arbisp.md

bookie1 = {}
bookie2 = {}

# Bookie 1 (SportyBet)
# 1X2
b1_1x2 = {'1': 1.41, 'X': 5.27, '2': 8.23}
b2_1x2 = {'1': 1.41, 'X': 4.90, '2': 8.25}

# Over/Under Goals
# Bookie 1:
# Over 0.5: 1.03, Under 0.5: 14.50
# Over 1.5: 1.23, Under 1.5: 4.40
# Over 2.5: 1.71, Under 2.5: 2.20
# Over 3.5: 2.75, Under 3.5: 1.47
# Over 4.5: (Wait, in B1: Over 4 4.30, Under 4 1.24? No, let's check exact B1 lines)
# Over 5.5: 9.50, Under 5.5: 1.07

b1_ou = {
    0.5: {'Over': 1.03, 'Under': 14.50},
    1.5: {'Over': 1.23, 'Under': 4.40},
    2.5: {'Over': 1.71, 'Under': 2.20},
    3.5: {'Over': 2.75, 'Under': 1.47},
    5.5: {'Over': 9.50, 'Under': 1.07},
}

# Bookie 2 (BetFox):
# Over 0.5: 1.05, Under 0.5: 14.50
# Over 1.5: 1.25, Under 1.5: 4.35
# Over 2.5: 1.75, Under 2.5: 2.18
# Over 3.5: 2.88, Under 3.5: 1.47
# Over 4.5: 5.40, Under 4.5: 1.18
# Over 5.5: 11.00, Under 5.5: 1.07

b2_ou = {
    0.5: {'Over': 1.05, 'Under': 14.50},
    1.5: {'Over': 1.25, 'Under': 4.35},
    2.5: {'Over': 1.75, 'Under': 2.18},
    3.5: {'Over': 2.88, 'Under': 1.47},
    4.5: {'Over': 5.40, 'Under': 1.18},
    5.5: {'Over': 11.00, 'Under': 1.07},
}

# Both Teams to Score (GG/NG)
# Bookie 1: Yes 2.05, No 1.79
# Bookie 2: Yes 2.03, No 1.82
b1_btts = {'Yes': 2.05, 'No': 1.79}
b2_btts = {'Yes': 2.03, 'No': 1.82}

# Double Chance
# Bookie 1: 1X: 1.10, 12: 1.18, X2: 2.80
# Bookie 2: 1X: 1.11, 12: 1.19, X2: 3.05
b1_dc = {'1X': 1.10, '12': 1.18, 'X2': 2.80}
b2_dc = {'1X': 1.11, '12': 1.19, 'X2': 3.05}

# Asian Handicap / 2-Way Handicap
# Bookie 1:
# -0.5: Home (-0.5) 1.38, Away (+0.5) 3.10
# -1.5: Home (-1.5) 2.10, Away (+1.5) 1.76
# -2.5: Home (-2.5) 3.70, Away (+2.5) 1.28
# Bookie 2:
# -0.5: Home (-0.5) 1.41, Away (+0.5) 3.05
# -1.5: Home (-1.5) 2.10, Away (+1.5) 1.77
# -2.5: Home (-2.5) 3.80, Away (+2.5) 1.30
b1_ah = {
    0.5: {'Home': 1.38, 'Away': 3.10},
    1.5: {'Home': 2.10, 'Away': 1.76},
    2.5: {'Home': 3.70, 'Away': 1.28},
}
b2_ah = {
    0.5: {'Home': 1.41, 'Away': 3.05},
    1.5: {'Home': 2.10, 'Away': 1.77},
    2.5: {'Home': 3.80, 'Away': 1.30},
}

# 3-Way Handicap:
# 0:1:
# B1: Home (0:1) 2.10, Draw (0:1) 3.80, Away (0:1) 3.10
# B2: Home (0:1) 2.10, Draw (0:1) 3.80, Away (0:1) 3.05
# 0:2:
# B1: Home (0:2) 3.80, Draw (0:2) 4.40, Away (0:2) 1.76
# B2: Home (0:2) 3.80, Draw (0:2) 4.35, Away (0:2) 1.77
# 0:3:
# B1: Home (0:3) 8.00, Draw (0:3) 6.50, Away (0:3) 1.28
# B2: Home (0:3) 8.00, Draw (0:3) 6.50, Away (0:3) 1.28

# 1st Half 1X2:
# B1: Home 1.85, Draw 2.60, Away 7.40
# B2: Home 1.85, Draw 2.63, Away 7.50

# 1st Half Over/Under:
# 0.5:
# B1: Wait, B1: "1st Half - Over/Under Over 1 1.65 Under 1 2.30", "Over 2.5 6.00, Under 2.5 1.15"
# What about B1 0.5 and 1.5?
# In B1 text:
# Let's search B1 1st half OU in text.

# Team Goals:
# Atletico Madrid:
# Over 1.5: B1 (1.52 / 2.55), B2 (1.52 / 2.56)
# Over 2.5: B1 (2.55 / 1.52), B2 (2.55 / 1.52)
# Osasuna:
# Over 0.5: B1 (1.82 / 2.00), B2 (1.82 / 2.00)
# Over 1.5: B1 (5.00 / 1.18), B2 (5.00 / 1.18)

# Corners Over/Under:
# 7.5: B1 (1.34 / 3.20), B2 (1.34 / 3.20)
# 8.5: B1 (1.58 / 2.35), B2 (1.58 / 2.35)
# 9.5: B1 (1.94 / 1.84), B2 (1.94 / 1.84)
# 10.5: B1 (2.45 / 1.53), B2 (2.47 / 1.53)
# 11.5: B1 (3.25 / 1.33), B2 (3.25 / 1.33)

def check_2way(name, o1, o2):
    prob = 1/o1 + 1/o2
    margin = (1 - prob) * 100
    is_arb = prob < 1.0
    print(f"[{'ARB' if is_arb else 'NO'}] {name}: Odds ({o1}, {o2}) -> Prob: {prob*100:.2f}%, Profit: {margin:+.2f}%")
    return is_arb

def check_3way(name, o1, o2, o3):
    prob = 1/o1 + 1/o2 + 1/o3
    margin = (1 - prob) * 100
    is_arb = prob < 1.0
    print(f"[{'ARB' if is_arb else 'NO'}] {name}: Odds ({o1}, {o2}, {o3}) -> Prob: {prob*100:.2f}%, Profit: {margin:+.2f}%")
    return is_arb

print("=== 1X2 ===")
check_3way("1X2 Best", max(b1_1x2['1'], b2_1x2['1']), max(b1_1x2['X'], b2_1x2['X']), max(b1_1x2['2'], b2_1x2['2']))

print("\n=== Over/Under Total Goals ===")
for line in [0.5, 1.5, 2.5, 3.5, 5.5]:
    over_best = max(b1_ou[line]['Over'], b2_ou[line]['Over'])
    under_best = max(b1_ou[line]['Under'], b2_ou[line]['Under'])
    check_2way(f"Total Goals OU {line}", over_best, under_best)

print("\n=== Both Teams To Score (GG/NG) ===")
check_2way("BTTS", max(b1_btts['Yes'], b2_btts['Yes']), max(b1_btts['No'], b2_btts['No']))

print("\n=== Double Chance vs Straight Bet ===")
# 1X vs 2
check_2way("1X vs 2", max(b1_dc['1X'], b2_dc['1X']), max(b1_1x2['2'], b2_1x2['2']))
# X2 vs 1
check_2way("X2 vs 1", max(b1_dc['X2'], b2_dc['X2']), max(b1_1x2['1'], b2_1x2['1']))
# 12 vs X
check_2way("12 vs X", max(b1_dc['12'], b2_dc['12']), max(b1_1x2['X'], b2_1x2['X']))

print("\n=== Asian Handicap / 2-Way Handicap ===")
for line in [0.5, 1.5, 2.5]:
    h_best = max(b1_ah[line]['Home'], b2_ah[line]['Home'])
    a_best = max(b1_ah[line]['Away'], b2_ah[line]['Away'])
    check_2way(f"AH -{line}/+{line}", h_best, a_best)

print("\n=== Corners Over/Under ===")
# 10.5
check_2way("Corners OU 10.5", 2.47, 1.53)

print("\n=== 1st Half 1X2 ===")
check_3way("1st Half 1X2", max(1.85, 1.85), max(2.60, 2.63), max(7.40, 7.50))
