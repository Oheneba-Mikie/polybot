import re

def test_pair(name, o1, o2):
    if o1 <= 1.0 or o2 <= 1.0:
        return None
    prob = 1/o1 + 1/o2
    margin = (1 - prob) * 100
    if prob < 1.0:
        print(f"!!! ARBITRAGE FOUND !!! {name}: ({o1}, {o2}) -> Prob: {prob*100:.2f}%, Profit: {margin:+.2f}%")
        return (margin, name, o1, o2)
    else:
        # print closest ones (within 3% of arb)
        if prob < 1.03:
            print(f"[NEAR ARB {prob*100:.2f}%] {name}: ({o1}, {o2}) -> Deficit: {margin:.2f}%")
    return None

def test_trio(name, o1, o2, o3):
    if o1 <= 1.0 or o2 <= 1.0 or o3 <= 1.0:
        return None
    prob = 1/o1 + 1/o2 + 1/o3
    margin = (1 - prob) * 100
    if prob < 1.0:
        print(f"!!! ARBITRAGE FOUND !!! {name}: ({o1}, {o2}, {o3}) -> Prob: {prob*100:.2f}%, Profit: {margin:+.2f}%")
        return (margin, name, o1, o2, o3)
    else:
        if prob < 1.03:
            print(f"[NEAR ARB {prob*100:.2f}%] {name}: ({o1}, {o2}, {o3}) -> Deficit: {margin:.2f}%")
    return None

print("Checking potential combinations...")

# 1. 1X2 standard
test_trio("1X2 Best", 1.41, 5.27, 8.25)
test_trio("1X2 B1 Home, B1 Draw, B2 Away", 1.41, 5.27, 8.25)

# 2. Draw No Bet vs Draw & Double Chance
# In DNB: If draw, stake refunded.
# If you bet Home DNB at B2 (1.15) and Away (+0.5) / X2 at B1 (2.80) or B2 (3.05):
# That's not pure DNB.
# But what if you bet Home 1X2 at B1/B2 (1.41), Draw at B1 (5.27), and Away at B2 (8.25)? Tested above (102.02%).

# 3. Clean Sheets vs Total Team Goals:
# Bookie 1:
# Home Team Clean Sheet: Yes 1.96, No 1.78
# (Home team clean sheet means Osasuna scores 0, i.e., Osasuna Under 0.5)
# In Bookie 1: Osasuna Under 0.5 is 2.00!
# Notice: Home Clean Sheet Yes is 1.96, but Osasuna Under 0.5 is 2.00!
# In Bookie 2: Osasuna Under 0.5 is 2.00, Over 0.5 is 1.82.
test_pair("B1 Home Clean Sheet Yes (1.96) vs B2 Osasuna Over 0.5 (1.82)", 1.96, 1.82)
test_pair("B1 Osasuna Under 0.5 (2.00) vs B2 Osasuna Over 0.5 (1.82)", 2.00, 1.82)
# Both give ~104.9%

# What about Away Team Clean Sheet?
# Bookie 1: Away Clean Sheet Yes: 6.40, No: 1.10
# (Away clean sheet means Atletico Under 0.5)
# In Bookie 2: Atletico Under 0.5 is not listed directly, but "Only CA Osasuna" is 14.00, "Neither" is 14.50.
# Sum = 1/14.00 + 1/14.50 = 0.0714 + 0.0690 = 0.1404 (implied odds ~ 7.12)
# Atletico Over 0.5: In Bookie 2, Over 0.5 total is 1.05.

# 4. Both Halves / Team to score in both halves:
# Bookie 1:
# Home Team to Score In Both Halves: Yes 2.15, No 1.66
# Away Team to Score In Both Halves: Yes 7.40, No 1.07

# 5. Half Time / Full Time:
# 1st Half 1X2:
# B1: 1.85 / 2.60 / 7.40
# B2: 1.85 / 2.63 / 7.50
test_trio("1st Half 1X2", 1.85, 2.63, 7.50)

# 1st Half Double Chance:
# B1: 1X: 1.12, 12: 1.47, X2: 1.88
# Cross check: B1 1st Half X2 (1.88) vs B2 1st Half 1 (1.85)
test_pair("1st Half X2 (B1) vs 1st Half 1 (B2)", 1.88, 1.85)
test_pair("1st Half 1X (B1) vs 1st Half 2 (B2)", 1.12, 7.50)
test_pair("1st Half 12 (B1) vs 1st Half X (B2)", 1.47, 2.63)

# 6. Corners:
# B1 Over 10.5 (2.45), Under 10.5 (1.53)
# B2 Over 10.5 (2.47), Under 10.5 (1.53)
test_pair("Corners 10.5: B2 Over 2.47 vs B1/B2 Under 1.53", 2.47, 1.53)

# 7. Goals Over/Under:
# 0.5: Over 1.05 (B2) vs Under 14.50 (B1/B2)
test_pair("Goals 0.5", 1.05, 14.50)
# 1.5: Over 1.25 (B2) vs Under 4.40 (B1)
test_pair("Goals 1.5", 1.25, 4.40)
# 2.5: Over 1.75 (B2) vs Under 2.20 (B1)
test_pair("Goals 2.5", 1.75, 2.20)
# 3.5: Over 2.88 (B2) vs Under 1.47 (B1/B2)
test_pair("Goals 3.5", 2.88, 1.47)
# 4.5: Over 5.40 (B2) vs Under 4.5? In B1, is there Under 4.5?
# B1 has "Double Chance & Over/Under 4.5", "1X2 & Over/Under 4.5" -> Under 4.5: Home 1.66, Draw 4.70, Away 8.10.
# Sum of 1/1.66 + 1/4.70 + 1/8.10 = 0.6024 + 0.2128 + 0.1235 = 0.9386 (Under 4.5 synthetic odds: 1/0.9386 = 1.065)
# 5.5: Over 11.00 (B2) vs Under 1.07 (B1/B2)
test_pair("Goals 5.5", 11.00, 1.07)

# 8. Both Teams to Score:
test_pair("BTTS: Yes 2.05 (B1) vs No 1.82 (B2)", 2.05, 1.82)
test_pair("BTTS: Yes 2.03 (B2) vs No 1.79 (B1)", 2.03, 1.79)

# 9. 2-Way Handicap:
test_pair("AH 0.5: Home 1.41 (B2) vs Away 3.10 (B1)", 1.41, 3.10)
test_pair("AH 1.5: Home 2.10 (B1/B2) vs Away 1.77 (B2)", 2.10, 1.77)
test_pair("AH 2.5: Home 3.80 (B2) vs Away 1.30 (B2)", 3.80, 1.30)
test_pair("AH 2.5: Home 3.80 (B2) vs Away 1.28 (B1)", 3.80, 1.28)

# 10. Team to win either half:
# CA Osasuna: Yes 3.55 (B2), No 1.27 (B2), B1 has Yes 3.50, No 1.26
test_pair("Osasuna win either half", 3.55, 1.27)
