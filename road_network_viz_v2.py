import osmnx as ox
import folium
import networkx as nx
import requests
import json
import csv
import pandas as pd
# 兰州市城关区的中心点坐标 (高德坐标系，约略)
# 实际上 osmnx 使用的是 WGS84 坐标，高德使用的是 GCJ02 坐标。
# 在中国范围内，两者有几百米的偏移。
# 为了毕设的严谨性，我们后续可以加入坐标转换，现在先用一个大致的 WGS84 坐标。
LANZHOU_CENTER = (36.0611, 103.8343)  # (lat, lng)
def export_intersections_to_csv(G, output_file="intersections.csv"):
    """
    导出路口节点坐标到 CSV
    """
    if G is None:
        return

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["node_id", "lat", "lng"])
        for node, data in G.nodes(data=True):
            writer.writerow([node, data["y"], data["x"]])

    print(f"路口坐标已导出到: {output_file}")


def export_intersections_to_json(G, output_file="intersections.json"):
    """
    导出路口节点坐标到 JSON
    """
    if G is None:
        return

    intersections = []
    for node, data in G.nodes(data=True):
        intersections.append({
            "node_id": node,
            "lat": data["y"],
            "lng": data["x"]
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(intersections, f, ensure_ascii=False, indent=2)

    print(f"路口坐标已导出到: {output_file}")
def build_road_network_by_point(center_point, dist=1500):
    """
    使用 osmnx 根据中心点坐标和半径获取路网，避开 Nominatim 搜索报错。
    """
    print(f"正在获取中心点 {center_point} 附近 {dist} 米的路网数据...")
    
    # 设置 osmnx 的请求超时和重试，增加稳定性
    ox.settings.timeout = 60
    ox.settings.use_cache = True
    
    try:
        # network_type='drive' 获取驾驶路网
        G = ox.graph_from_point(center_point, dist=dist, network_type='drive')
        print(f"路网构建完成。节点数: {len(G.nodes)}, 边数: {len(G.edges)}")
        return G
    except Exception as e:
        print(f"获取路网失败: {e}")
        return None
from collections import defaultdict

def normalize_name(name):
    if pd.isna(name):
        return ""
    return str(name).strip().replace("－", "-").replace("—", "-")

def split_intersection_name(name):
    name = normalize_name(name)
    parts = [p.strip() for p in name.split("-") if p.strip()]
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]

def edge_names(data):
    """
    提取一条边的道路名，统一转成 set
    """
    names = data.get("name")
    if names is None:
        return set()
    if isinstance(names, list):
        return {str(x).strip() for x in names if str(x).strip()}
    return {str(names).strip()}

def collect_node_road_names(G):
    """
    收集每个节点相邻边上的道路名
    """
    node_roads = defaultdict(set)

    for u, v, k, data in G.edges(keys=True, data=True):
        names = edge_names(data)
        if names:
            node_roads[u].update(names)
            node_roads[v].update(names)

    return node_roads

def find_candidates_for_intersection(G, road_a, road_b, node_roads):
    """
    找同时连接 road_a 和 road_b 的节点
    """
    candidates = []

    for node, roads in node_roads.items():
        if road_a in roads and road_b in roads:
            data = G.nodes[node]
            candidates.append({
                "node_id": node,
                "lat": data["y"],
                "lng": data["x"],
                "degree": G.degree(node),
                "roads": sorted(list(roads))
            })

    return candidates

def choose_best_candidate(candidates):
    """
    简单策略：优先选 degree 最大的
    后面可以再加 grid 顺序约束
    """
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda x: (-x["degree"], x["node_id"]))
    return candidates[0]

def match_dataset_intersections(G, csv_file):
    df = pd.read_csv(csv_file)
    node_roads = collect_node_road_names(G)

    results = []

    for _, row in df.iterrows():
        road_a, road_b = split_intersection_name(row["intersection_name"])

        if not road_a or not road_b:
            results.append({
                **row.to_dict(),
                "matched": False,
                "matched_node_id": None,
                "lat": None,
                "lng": None,
                "candidate_count": 0
            })
            continue

        candidates = find_candidates_for_intersection(G, road_a, road_b, node_roads)
        best = choose_best_candidate(candidates)

        if best is None:
            results.append({
                **row.to_dict(),
                "matched": False,
                "matched_node_id": None,
                "lat": None,
                "lng": None,
                "candidate_count": 0
            })
        else:
            results.append({
                **row.to_dict(),
                "matched": True,
                "matched_node_id": best["node_id"],
                "lat": best["lat"],
                "lng": best["lng"],
                "candidate_count": len(candidates)
            })

    return pd.DataFrame(results)

def visualize_network(G, output_file="road_network_v2.html"):
    """
    使用 folium 将路网可视化并保存为 HTML
    """
    if G is None:
        return

    print("正在生成可视化地图...")
    # 获取路网中心点
    nodes, edges = ox.graph_to_gdfs(G)
    center_lat = nodes.geometry.y.mean()
    center_lng = nodes.geometry.x.mean()
    
    # 使用高德地图作为底图 (GCJ02 坐标系)
    # 注意：OSM 数据是 WGS84，直接叠加在高德底图上会有偏移。
    # 毕设中通常需要进行坐标纠偏，这里先展示原始叠加效果。
    amap_tiles = 'http://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
    
    m = folium.Map(location=[center_lat, center_lng], 
                   zoom_start=15, 
                   tiles=amap_tiles, 
                   attr='Amap')
    
    # 将路网边添加到地图上
    for u, v, data in G.edges(data=True):
        if 'geometry' in data:
            coords = list(data['geometry'].coords)
            path = [[p[1], p[0]] for p in coords]
            folium.PolyLine(path, color="#3388ff", weight=4, opacity=0.8).add_to(m)
        else:
            u_node = G.nodes[u]
            v_node = G.nodes[v]
            path = [[u_node['y'], u_node['x']], [v_node['y'], v_node['x']]]
            folium.PolyLine(path, color="#3388ff", weight=4, opacity=0.8).add_to(m)
            
    # 将路口节点添加到地图上
    for node, data in G.nodes(data=True):
        folium.CircleMarker(
            location=[data['y'], data['x']],
            radius=4,
            color="red",
            fill=True,
            fill_color="white",
            fill_opacity=1,
            popup=f"Intersection ID: {node}"
        ).add_to(m)
        
    m.save(output_file)
    print(f"可视化地图已保存至: {output_file}")

if __name__ == "__main__":
    # 1. 指定中心点（兰州市东方红广场附近）
    # 如果你想换城市，只需修改这里的经纬度即可
    center = (34.8599862, 105.6657512)
    
    # 2. 构建路网 (1.5公里半径)
    G = build_road_network_by_point(center, dist=1500)
    
    # 3. 可视化
    if G:
        visualize_network(G, "lanzhou_fixed_network.html")
        export_intersections_to_csv(G, "lanzhou_intersections.csv")
