import csv

# 用户提供的真实坐标数据
real_coords = {
    "QNA001": (34.851686, 105.668917),
    "QNA002": (34.860499, 105.674624),
    "QNA003": (34.860521, 105.671033),
    "QNA004": (34.860475, 105.667865),
    "QNA005": (34.862083, 105.671869),
    "QNA006": (34.860581, 105.674625),
    "QNA007": (34.860506, 105.670412),
    "QNA008": (34.874061, 105.669962),
    "QNA009": (34.851686, 105.668917),
    "QNA010": (34.858423, 105.674657),
    "QNA011": (34.858758, 105.671072),
    "QNA012": (34.861828, 105.667900),
    "QNA013": (34.863419, 105.672153),
    "QNA014": (34.857375, 105.674375),
    "QNA015": (34.877851, 105.676229),
    "QNA016": (34.874061, 105.669962),
    "QNA017": (34.851686, 105.668917),
    "QNA018": (34.855849, 105.674618),
    "QNA019": (34.858758, 105.671072),
    "QNA020": (34.861828, 105.667900),
    "QNA021": (34.863419, 105.672153),
    "QNA022": (34.870100, 105.673971),
    "QNA023": (34.877851, 105.676229),
    "QNA024": (34.874061, 105.669962),
    "QNA025": (34.851686, 105.668917),
    "QNA026": (34.855849, 105.674618),
    "QNA027": (34.858758, 105.671072),
    "QNA028": (34.861828, 105.667900),
    "QNA029": (34.863471, 105.674504),
    "QNA030": (34.863471, 105.674504),
    "QNA031": (34.855835, 105.672317),
    "QNA032": (34.874061, 105.669962),
    "QNA033": (34.851686, 105.668917),
    "QNA034": (34.855849, 105.674618),
    "QNA035": (34.866517, 105.671690),
    "QNA036": (34.864268, 105.671760),
    "QNA037": (34.863381, 105.671445),
    "QNA038": (34.864125, 105.678275),
    "QNA039": (34.877851, 105.676229),
    "QNA040": (34.874061, 105.669962),
}

input_file = "qinan_simulated_traffic_csv_40nodes/Intersections.csv"
output_file = "qinan_simulated_traffic_csv_40nodes/Intersections.csv"

rows = []
with open(input_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    
    for row in reader:
        intersection_id = row['intersection_id']
        
        if intersection_id in real_coords:
            old_lat, old_lng = row['lat'], row['lng']
            new_lat, new_lng = real_coords[intersection_id]
            
            row['lat'] = str(new_lat)
            row['lng'] = str(new_lng)
            
            print(f"[UPDATED] {intersection_id}: ({old_lat}, {old_lng}) -> ({new_lat}, {new_lng})")
        
        rows.append(row)

with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n[DONE] Updated {len(rows)} records in {output_file}")
