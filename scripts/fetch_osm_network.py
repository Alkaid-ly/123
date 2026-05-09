import osmnx as ox
import json
import os
import math
import pandas as pd
import numpy as np
from pathlib import Path

# GCJ-02 (Amap) to WGS-84 (OSM) conversion algorithms
def wgs84_to_gcj02(lng, lat):
    if out_of_china(lng, lat):
        return lng, lat
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lng + dlng, lat + dlat

def gcj02_to_wgs84(lng, lat):
    if out_of_china(lng, lat):
        return lng, lat
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    a = 6378245.0
    ee = 0.00669342162296594323
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lng - dlng, lat - dlat

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret

def transform_lng(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret

def out_of_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)

def update_background_network(
    inter_csv="qinan_simulated_traffic_csv_40nodes/Intersections.csv",
    output_json="app/static/study_area_network.json"
):
    print("正在根据真实坐标更新背景路网...")
    
    # 1. 加载路口
    df_nodes = pd.read_csv(inter_csv)
    
    # 2. 准备范围 (这些是 GCJ-02 坐标，先转回 WGS-84 以获取 OSM 数据)
    lats_gcj = df_nodes["lat"].dropna().tolist()
    lngs_gcj = df_nodes["lng"].dropna().tolist()
    
    if not lats_gcj or not lngs_gcj:
        print("错误：Intersections.csv 中没有有效的经纬度。")
        return

    # 转换边界点到 WGS-84
    lng_sw_wgs, lat_sw_wgs = gcj02_to_wgs84(min(lngs_gcj), min(lats_gcj))
    lng_ne_wgs, lat_ne_wgs = gcj02_to_wgs84(max(lngs_gcj), max(lats_gcj))
    
    # 设置边距
    north, south = lat_ne_wgs + 0.005, lat_sw_wgs - 0.005
    east, west = lng_ne_wgs + 0.005, lng_sw_wgs - 0.005
    
    print(f"正在从 OSM 获取区域路网 (WGS84): N={north}, S={south}, E={east}, W={west}...")
    
    ox.settings.use_cache = True
    try:
        G = ox.graph_from_bbox(bbox=(north, south, east, west), network_type='drive')
    except Exception as e:
        print(f"获取路网失败: {e}")
        return

    # 3. 转换 OSM 路网为 GCJ-02 特性
    features = []
    for u, v, k, data in G.edges(keys=True, data=True):
        if 'geometry' in data:
            coords = list(data['geometry'].coords)
            path = [list(wgs84_to_gcj02(p[0], p[1])) for p in coords]
        else:
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            p1 = wgs84_to_gcj02(u_data['x'], u_data['y'])
            p2 = wgs84_to_gcj02(v_data['x'], v_data['y'])
            path = [list(p1), list(p2)]
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": path
            },
            "properties": {
                "name": data.get("name", ""),
                "highway": data.get("highway", "")
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # 4. 写入文件
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    
    print(f"已成功更新背景路网文件: {output_json}")

if __name__ == "__main__":
    update_background_network()
