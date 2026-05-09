import pandas as pd

df = pd.read_csv('qinan_simulated_traffic_csv_40nodes/Intersections.csv')
print("=== CSV File Contents (First 5) ===")
for _, row in df.head(5).iterrows():
    print(f"{row['intersection_id']}: lat={row['lat']}, lng={row['lng']}")
