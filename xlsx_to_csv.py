import pandas as pd

# Replace 'your_file.xlsx' with the path to your Excel file
excel_file = 'inventory.xlsx'
# Replace 'output_file.csv' with the desired output CSV file name
csv_file = 'inventory.csv'

# Read the Excel file
df = pd.read_excel(excel_file)

# Save to CSV
df.to_csv(csv_file, index=False)
