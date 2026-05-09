import csv
import json

# 读取更新后的路口坐标
coords = {}
with open("qinan_simulated_traffic_csv_40nodes/Intersections.csv", "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        coords[row["intersection_id"]] = {
            "lat": float(row["lat"]),
            "lng": float(row["lng"]),
            "name": row["intersection_name"]
        }

# 读取路段数据获取连接关系
segments = []
with open("qinan_simulated_traffic_csv_40nodes/Road_Segments.csv", "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        segments.append({
            "segment_id": row["segment_id"],
            "from": row["from_intersection"],
            "to": row["to_intersection"],
            "road_name": row["road_name"]
        })

# 生成GeoJSON格式的道路网络
features = []
for seg in segments:
    from_id = seg["from"]
    to_id = seg["to"]
    
    if from_id in coords and to_id in coords:
        from_coord = coords[from_id]
        to_coord = coords[to_id]
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [from_coord["lng"], from_coord["lat"]],
                    [to_coord["lng"], to_coord["lat"]]
                ]
            },
            "properties": {
                "name": seg["road_name"],
                "segment_id": seg["segment_id"]
            }
        }
        features.append(feature)
        print(f"[OK] {seg['segment_id']}: {from_id} -> {to_id}")

# 写入JSON文件
geojson = {
    "type": "FeatureCollection",
    "features": features
}

output_file = "app/static/study_area_network.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)

print(f"\n[DONE] Generated {len(features)} road segments in {output_file}")
print(f"Total intersections: {len(coords)}")
