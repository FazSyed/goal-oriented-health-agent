import pandas as pd

# Load the XPT files for both cycles
bioprog = pd.read_sas('BIOPRO_G.XPT', format='xport', encoding='utf-8')
demog = pd.read_sas('DEMO_G.XPT', format='xport', encoding='utf-8')
bmxg = pd.read_sas('BMX_G.XPT', format='xport', encoding='utf-8')

bioproh = pd.read_sas('BIOPRO_H.XPT', format='xport', encoding='utf-8')
demoh = pd.read_sas('DEMO_H.XPT', format='xport', encoding='utf-8')
bmxh = pd.read_sas('BMX_H.XPT', format='xport', encoding='utf-8')

# Merge each cycle on SEQN then combine cycles
df_g = bioprog.merge(demog[['SEQN', 'RIDAGEYR', 'RIAGENDR']], on='SEQN', how='inner')
df_g = df_g.merge(bmxg[['SEQN', 'BMXWT', 'BMXBMI']], on='SEQN', how='inner')
df_g['cycle'] = '2011-2012'

df_h = bioproh.merge(demoh[['SEQN', 'RIDAGEYR', 'RIAGENDR']], on='SEQN', how='inner')
df_h = df_h.merge(bmxh[['SEQN', 'BMXWT', 'BMXBMI']], on='SEQN', how='inner')
df_h['cycle'] = '2013-2014'

# Combine both cycles
df = pd.concat([df_g, df_h], ignore_index=True)

# Filter geriatric group (age >= 65)
df_elderly = df[df['RIDAGEYR'] >= 65].copy()

# Select only hydration-relevant columns
features = ['SEQN', 'RIDAGEYR', 'RIAGENDR', 'BMXWT', 'BMXBMI', 'LBXSNASI', 'LBXSKSI', 'LBXSCLSI', 'LBXSBU', 'LBXSCR', 'LBXSGL','LBXSAL', 'LBXSOSSI']

df_elderly = df_elderly[features].dropna()

# --- Helper functions for severity grading ---
def calculate_bun_cr_ratio(bun, creatinine):
    if creatinine == 0:
        return 0
    return bun / creatinine

def severity_score(na, bun_cr):
    score = 0
    if na >= 150:
        score += 2
    elif na >= 145:
        score += 1

    if bun_cr >= 30:
        score += 2
    elif bun_cr >= 20:
        score += 1

    return score

# Create dehydration label from osmolality, with Na + BUN:Cr splitting Moderate/Severe
def label_hydration(row):
    osm = row['LBXSOSSI']
    if osm < 275:
        return 'Hyperhydrated'
    elif osm < 296:
        return 'Euhydrated'
    elif osm < 300:
        return 'Mild/Impending'
    else:
        bun_cr = calculate_bun_cr_ratio(row['LBXSBU'], row['LBXSCR'])
        score = severity_score(row['LBXSNASI'], bun_cr)
        if score >= 3:
            return 'Severe'
        else:
            return 'Moderate'

# Apply row-wise (axis=1) since the function now needs multiple columns, not just osmolality
df_elderly['hydration_status'] = df_elderly.apply(label_hydration, axis=1)

df_elderly.rename(columns={
    'SEQN': 'id',
    'RIDAGEYR': 'Age',
    'RIAGENDR': 'Sex',
    'BMXWT': 'Weight',
    'BMXBMI': 'BMI',
    'LBXSNASI': 'Sodium',
    'LBXSKSI': 'Potassium',
    'LBXSCLSI': 'Chloride',
    'LBXSBU': 'Blood_Urea_Nitrogen',
    'LBXSCR': 'Creatinine',
    'LBXSGL': 'Glucose',
    'LBXSAL': 'Albumin',
    'LBXSOSSI': 'Osmolality',
    'hydration_status': 'HydrationStatus'
}, inplace=True)


pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

print(df_elderly['HydrationStatus'].value_counts(), "\n")

print(f"Total elderly records: {len(df_elderly)}\n")
print(df_elderly.head(10).to_string(index=False))

print("\nMild/Impending rows:\n")
print(df_elderly[df_elderly['HydrationStatus'] == 'Mild/Impending'].to_string(index=False))

print("\nModerately Dehydrated rows:\n")
print(df_elderly[df_elderly['HydrationStatus'] == 'Moderate'].to_string(index=False))

print("\nSeverely Dehydrated rows:\n")
print(df_elderly[df_elderly['HydrationStatus'] == 'Severe'].to_string(index=False))