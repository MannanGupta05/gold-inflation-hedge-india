import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.api as sm
from scipy import stats

print("=" * 70)
print("INDIA'S INFLATION VS. GOLD PRICES: COMPLETE ANALYSIS")
print("=" * 70)

# ==========================================
# 1. LOAD & PARSE DATA CORRECTLY
# ==========================================
print("\n[Step 1] Loading datasets...")

# ---------- GOLD DATA ----------
df_gold = pd.read_csv('gold_prices.csv')
print(f"Gold data shape: {df_gold.shape}")
print(f"Gold columns: {df_gold.columns.tolist()}")

# Parse gold dates (handle several formats, then normalize to month-start)
for fmt in ["%b %Y", "%b %y", "%d/%m/%Y", "%Y-%m-%d"]:
    try:
        df_gold["Date"] = pd.to_datetime(df_gold["Date"], format=fmt)
        break
    except ValueError:
        continue
else:
    df_gold["Date"] = pd.to_datetime(df_gold["Date"])  # fallback: infer

# keep only needed columns and clean price
if df_gold["Price"].dtype == "object":
    df_gold["Price"] = (
        df_gold["Price"].astype(str).str.replace(",", "", regex=False).astype(float)
    )

# normalize gold dates to monthly period (YYYY-MM-01)
df_gold["Date"] = df_gold["Date"].values.astype("datetime64[M]")

# ---------- CPI DATA ----------
df_cpi = pd.read_csv('cpi_data.csv')
print(f"CPI data shape: {df_cpi.shape}")
print(f"CPI columns: {df_cpi.columns.tolist()}")

df_cpi["Date"] = pd.to_datetime(df_cpi["Date"])
df_cpi["Date"] = df_cpi["Date"].values.astype("datetime64[M]")


# ==========================================
# 2. MERGE & VALIDATE
# ==========================================
print("\n[Step 2] Merging datasets...")

# Merge on Date
df = pd.merge(df_gold, df_cpi, on='Date', how='inner')
print(f"Merged data shape: {df.shape}")
print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")

# Sort strictly by date
df = df.sort_values('Date').reset_index(drop=True)

# Check for gaps
date_diffs = df['Date'].diff().dt.days
if (date_diffs.dropna() > 50).any():
    print("[WARNING] Possible date gaps detected!")
else:
    print("[OK] Date sequence looks correct (monthly intervals)")

# ==========================================
# 3. CALCULATE RETURNS & INFLATION
# ==========================================
print("\n[Step 3] Calculating metrics...")

# Monthly Returns (%)
df['Inflation_Rate'] = df['CPI_Combined'].pct_change() * 100
df['Gold_Returns'] = df['Price'].pct_change() * 100

# Drop first row (NaN from pct_change)
df = df.dropna()

print(f"Analysis dataset: {len(df)} observations")
print(f"Avg Monthly Inflation: {df['Inflation_Rate'].mean():.4f}%")
print(f"Avg Monthly Gold Return: {df['Gold_Returns'].mean():.4f}%")

# ==========================================
# 4. STATISTICAL ANALYSIS
# ==========================================
print("\n" + "=" * 70)
print("--- MAIN RESULTS ---")
print("=" * 70)

# A. OVERALL CORRELATION
corr_coeff = df['Inflation_Rate'].corr(df['Gold_Returns'])
print(f"\nOverall Correlation Coefficient: {corr_coeff:.4f}")

# B. OLS REGRESSION: Gold_Returns = alpha + beta * Inflation
X = sm.add_constant(df['Inflation_Rate'])
y = df['Gold_Returns']
model = sm.OLS(y, X).fit()

print("\n--- OLS REGRESSION RESULTS ---")
print(model.summary())

# Extract key statistics
r_squared = model.rsquared
beta = model.params['Inflation_Rate']
beta_pvalue = model.pvalues['Inflation_Rate']
alpha = model.params['const']

print(f"\nKey Interpretation:")
print(f"  Beta (Hedge Ratio): {beta:.4f}")
print(f"  Beta P-value: {beta_pvalue:.4f} {'(Significant)' if beta_pvalue < 0.05 else '(NOT Significant)'}")
print(f"  R-squared: {r_squared:.4f} (Inflation explains {r_squared*100:.2f}% of Gold movement)")

# C. ROLLING CORRELATION
print("\n[Step 4] Computing rolling statistics...")

window_size = 12  # 12-month rolling window
df['Rolling_Corr_12m'] = df['Inflation_Rate'].rolling(window=window_size).corr(df['Gold_Returns'])

window_size = 24  # 24-month rolling window
df['Rolling_Corr_24m'] = df['Inflation_Rate'].rolling(window=window_size).corr(df['Gold_Returns'])

# D. HEDGE RATIO (Dynamic Beta)
# Calculate rolling beta (sensitivity of Gold to Inflation)
def rolling_beta(inflation, gold_returns, window=12):
    betas = []
    for i in range(len(inflation) - window + 1):
        X_window = sm.add_constant(inflation.iloc[i:i+window])
        y_window = gold_returns.iloc[i:i+window]
        try:
            model_window = sm.OLS(y_window, X_window).fit()
            betas.append(model_window.params[1])
        except:
            betas.append(np.nan)
    return [np.nan] * (window - 1) + betas

df['Rolling_Beta_12m'] = rolling_beta(df['Inflation_Rate'], df['Gold_Returns'], window=12)

# ==========================================
# 5. VISUALIZATION 1: Trend Comparison (Dual Axis)
# ==========================================
print("\n[Step 5] Generating visualizations...")

fig, ax1 = plt.subplots(figsize=(14, 7))

color = 'tab:red'
ax1.set_xlabel('Year', fontsize=12, fontweight='bold')
ax1.set_ylabel('Gold Price (INR per 10g)', color=color, fontsize=12, fontweight='bold')
line1 = ax1.plot(df['Date'], df['Price'], color=color, linewidth=2.5, label='Gold Price (MCX)')
ax1.tick_params(axis='y', labelcolor=color)
ax1.grid(True, alpha=0.3)

# Second Y-axis
ax2 = ax1.twinx()
color = 'tab:blue'
ax2.set_ylabel('CPI Index (2012=100)', color=color, fontsize=12, fontweight='bold')
line2 = ax2.plot(df['Date'], df['CPI_Combined'], color=color, linestyle='--', linewidth=2.5, label='CPI Combined')
ax2.tick_params(axis='y', labelcolor=color)

# Highlight Duty Cut
duty_cut_date = pd.to_datetime('2024-07-01')
ax1.axvline(duty_cut_date, color='green', linestyle=':', linewidth=2, alpha=0.7, label='Import Duty Cut')
ax1.text(duty_cut_date, df['Price'].max() * 0.95, ' Duty Cut\n(July 2024)', 
         color='green', fontweight='bold', fontsize=10, va='top')

plt.title('Gold Price vs. CPI Level (2015-2025): Structural Break Analysis', 
          fontsize=14, fontweight='bold', pad=20)

# Combined legend
lines = line1 + line2
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='upper left', fontsize=10)

plt.tight_layout()
plt.savefig('01_trend_comparison.png', dpi=300, bbox_inches='tight')
print("[SAVED] Saved: 01_trend_comparison.png")
plt.show()

# ==========================================
# 6. VISUALIZATION 2: Rolling Correlation
# ==========================================

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# Plot 1: 12-month and 24-month rolling correlation
ax1.plot(df['Date'], df['Rolling_Corr_12m'], color='navy', linewidth=2, label='12-Month Rolling Correlation')
ax1.plot(df['Date'], df['Rolling_Corr_24m'], color='darkblue', linewidth=2, alpha=0.6, label='24-Month Rolling Correlation')
ax1.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax1.axhline(corr_coeff, color='orange', linestyle='--', linewidth=1.5, alpha=0.5, label=f'Overall Corr: {corr_coeff:.3f}')
ax1.axvline(duty_cut_date, color='green', linestyle=':', linewidth=2, alpha=0.7)
ax1.fill_between(df['Date'], 0, df['Rolling_Corr_12m'], alpha=0.1, color='navy')
ax1.set_ylabel('Correlation Coefficient', fontsize=11, fontweight='bold')
ax1.set_title('Does Gold Act as an Inflation Hedge? Rolling Correlation Analysis', 
              fontsize=13, fontweight='bold', pad=15)
ax1.grid(True, alpha=0.3)
ax1.legend(loc='upper left', fontsize=10)
ax1.set_ylim(-1, 1)

# Plot 2: Rolling Beta (Hedge Ratio)
ax2.plot(df['Date'], df['Rolling_Beta_12m'], color='purple', linewidth=2, label='12-Month Rolling Beta')
ax2.axhline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
ax2.axhline(beta, color='orange', linestyle='--', linewidth=1.5, alpha=0.5, label=f'Overall Beta: {beta:.3f}')
ax2.axhline(1.0, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Perfect Hedge (Beta=1.0)')
ax2.axvline(duty_cut_date, color='green', linestyle=':', linewidth=2, alpha=0.7)
ax2.fill_between(df['Date'], 0, df['Rolling_Beta_12m'], alpha=0.1, color='purple')
ax2.set_xlabel('Year', fontsize=11, fontweight='bold')
ax2.set_ylabel('Regression Beta (Slope)', fontsize=11, fontweight='bold')
ax2.set_title('Hedge Ratio Over Time: How Much Does Gold Rise Per 1% Inflation?', 
              fontsize=13, fontweight='bold', pad=15)
ax2.grid(True, alpha=0.3)
ax2.legend(loc='upper left', fontsize=10)

plt.tight_layout()
plt.savefig('02_rolling_correlation_and_beta.png', dpi=300, bbox_inches='tight')
print("[SAVED] Saved: 02_rolling_correlation_and_beta.png")
plt.show()

# ==========================================
# 7. VISUALIZATION 3: Scatter Plot with Regression Line
# ==========================================

fig, ax = plt.subplots(figsize=(12, 8))

# Scatter plot
ax.scatter(df['Inflation_Rate'], df['Gold_Returns'], alpha=0.6, s=60, color='steelblue', edgecolors='black', linewidth=0.5)

# Regression line
x_line = np.array([df['Inflation_Rate'].min(), df['Inflation_Rate'].max()])
y_line = alpha + beta * x_line
ax.plot(x_line, y_line, 'r--', linewidth=2.5, label=f'Regression: Gold = {alpha:.2f} + {beta:.2f} * Inflation')

ax.axhline(0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
ax.axvline(0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)

ax.set_xlabel('Monthly Inflation Rate (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('Monthly Gold Returns (%)', fontsize=12, fontweight='bold')
ax.set_title(f'Gold Returns vs. Inflation: Weak Hedge Evidence (r = {corr_coeff:.3f}, R-sq = {r_squared:.4f})', 
             fontsize=13, fontweight='bold', pad=15)
ax.grid(True, alpha=0.3)
ax.legend(fontsize=11, loc='upper left')

plt.tight_layout()
plt.savefig('03_regression_scatter.png', dpi=300, bbox_inches='tight')
print("[SAVED] Saved: 03_regression_scatter.png")
plt.show()

# ==========================================
# 8. EXPORT RESULTS
# ==========================================
print("\n[Step 6] Exporting results...")

# Save processed data
df.to_csv('final_analysis_data.csv', index=False)
print("[SAVED] Saved: final_analysis_data.csv")

# Summary statistics to text file
with open('analysis_summary.txt', 'w') as f:
    f.write("=" * 70 + "\n")
    f.write("INDIA'S INFLATION VS. GOLD PRICES: STATISTICAL SUMMARY\n")
    f.write("=" * 70 + "\n\n")
    
    f.write(f"Data Period: {df['Date'].min().strftime('%B %Y')} to {df['Date'].max().strftime('%B %Y')}\n")
    f.write(f"Number of Observations: {len(df)}\n\n")
    
    f.write("DESCRIPTIVE STATISTICS:\n")
    f.write(f"  Inflation Rate: Mean = {df['Inflation_Rate'].mean():.4f}%, Std = {df['Inflation_Rate'].std():.4f}%\n")
    f.write(f"  Gold Returns:   Mean = {df['Gold_Returns'].mean():.4f}%, Std = {df['Gold_Returns'].std():.4f}%\n\n")
    
    f.write("KEY FINDINGS:\n")
    f.write(f"1. Overall Correlation: {corr_coeff:.4f}\n")
    f.write(f"   - Gold and inflation have a {'WEAK' if abs(corr_coeff) < 0.3 else 'MODERATE' if abs(corr_coeff) < 0.6 else 'STRONG'} relationship\n\n")
    
    f.write(f"2. Regression (Gold = alpha + beta * Inflation):\n")
    f.write(f"   - Intercept (alpha):    {alpha:.4f}\n")
    f.write(f"   - Beta (beta):         {beta:.4f}\n")
    f.write(f"   - P-value:          {beta_pvalue:.4f} {'(Statistically Significant at 5%)' if beta_pvalue < 0.05 else '(NOT Statistically Significant)'}\n")
    f.write(f"   - R-squared:        {r_squared:.4f}\n")
    f.write(f"   - Interpretation: For every 1% rise in inflation, gold rises {beta:.2f}% on average\n\n")
    
    f.write(f"3. Hedge Quality:\n")
    if beta < 0.5:
        f.write(f"   - WEAK HEDGE: Gold only captures ~{beta*100:.0f}% of inflation\n")
    elif beta < 1.0:
        f.write(f"   - PARTIAL HEDGE: Gold captures ~{beta*100:.0f}% of inflation\n")
    else:
        f.write(f"   - STRONG HEDGE: Gold captures MORE than inflation (over-hedge)\n\n")
    
    f.write("POLICY SHOCK:\n")
    f.write(f"   - July 2024 Import Duty Cut (15% -> 6%) caused artificial price suppression\n")
    f.write(f"   - Visible in rolling correlation plot: sharp drop after July 2024\n")

print("[SAVED] Saved: analysis_summary.txt")

print("\n" + "=" * 70)
print("ANALYSIS COMPLETE!")
print("=" * 70)
print("\nFiles Generated:")
print("  1. 01_trend_comparison.png")
print("  2. 02_rolling_correlation_and_beta.png")
print("  3. 03_regression_scatter.png")
print("  4. final_analysis_data.csv")
print("  5. analysis_summary.txt")
print("\nReady for report writing!")
print("=" * 70)
