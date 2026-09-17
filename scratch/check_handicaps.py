# Let's inspect all markets from the prompt diff and cross compare

# We can search through the prompt lines for specific markets in Bookie 1
with open(r"C:\Users\mwx1432398\.gemini\antigravity-ide\brain\7f77952b-686c-401a-812f-6fb56bac5048\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    import json
    for line in f:
        pass # let's check step 0 or others

# Let's write a script that checks specific interesting cross comparisons:
# Let's test 1st Half OU:
# Bookie 2:
# 1st Half OU 0.5: Over 1.32, Under 3.30
# 1st Half OU 1.5: Over 2.47, Under 1.55
# 1st Half OU 2.5: Over 5.80, Under 1.14

# In Bookie 1:
# "1st Half - Exact Goals 0: 3.50, 1: 2.65, 2: 4.00, 3+: 6.25"
# Notice: 1st Half Exact Goals 0 is EXACTLY 1st Half Under 0.5!
# Under 0.5 Goals in 1st half means 0 goals!
# In Bookie 1: 1st Half Exact Goals 0 is 3.50!
# In Bookie 2: 1st Half Over 0.5 is 1.32!
# Let's check: 1 / 3.50 + 1 / 1.32 = 0.2857 + 0.7576 = 1.0433 (104.33% - close, but no arb)

# What about Bookie 1:
# "Total Goals Over/Under from 1 to 50 minute..."
# "1st Half - Correct Score"
# "1st Half - Over/Under"
# Over 1: 1.65, Under 1: 2.30
# Over 2: 4.75, Under 2: 1.21
# Over 2.5: 6.00, Under 2.5: 1.15
# Compare Over 2.5 in B1 (6.00) vs Under 2.5 in B2 (1.14):
# 1/6.00 + 1/1.14 = 0.1667 + 0.8772 = 1.0439 (No)
# Compare Over 2.5 in B2 (5.80) vs Under 2.5 in B1 (1.15):
# 1/5.80 + 1/1.15 = 0.1724 + 0.8696 = 1.0420 (No)

# What about 1st Half OU 1.5?
# Bookie 2: Over 1.5: 2.47, Under 1.5: 1.55
# In Bookie 1, do we have 1st Half OU 1.5?
# "1st Half - 1X2 & Over/Under 1.5"
# "1st Half - Multigoals"
# "1st Half Home Team to Win to Nil"

# What about Handicap?
# Bookie 1:
# Handicap 1:0: Home (1:0) 1.10, Draw (1:0) 9.25, Away (1:0) 24.00
# Bookie 2:
# Handicap 1:0: Home (1:0) 1.11, Draw (1:0) 10.00, Away (1:0) 24.00
# Prob: 1/1.11 + 1/10.00 + 1/24.00 = 0.9009 + 0.1000 + 0.0417 = 1.0426 (No)

# Handicap 0:1:
# Bookie 1: Home 2.10, Draw 3.80, Away 3.10
# Bookie 2: Home 2.10, Draw 3.80, Away 3.05
# Prob: 1/2.10 + 1/3.80 + 1/3.10 = 0.4762 + 0.2632 + 0.3226 = 1.0619 (No)

# Handicap 0:2:
# Bookie 1: Home 3.80, Draw 4.40, Away 1.76
# Bookie 2: Home 3.80, Draw 4.35, Away 1.77
# Prob: 1/3.80 + 1/4.40 + 1/1.77 = 0.2632 + 0.2273 + 0.5650 = 1.0554 (No)

# Handicap 0:3:
# Bookie 1: Home 8.00, Draw 6.50, Away 1.28
# Bookie 2: Home 8.00, Draw 6.50, Away 1.28
# Identical!

print("Detailed check done.")
