import requests
import json

response = requests.get("http://127.0.0.1:8001/api/dashboard?date=2025-10-31&hour=17")
data = response.json()

print(f"=== 前端实际收到的 /api/dashboard ===")
print(f"nodes 数量: {len(data.get('nodes', []))}")

if data.get('nodes'):
    print("\n前 5 个节点:")
    for i, node in enumerate(data['nodes'][:5]):
        print(f"  {i+1}. {node.get('intersection_id')}: lat={node.get('lat')}, lng={node.get('lng')}")

    print(f"\n坐标范围:")
    lats = [n['lat'] for n in data['nodes']]
    lngs = [n['lng'] for n in data['nodes']]
    print(f"  lat: {min(lats)} ~ {max(lats)}")
    print(f"  lng: {min(lngs)} ~ {max(lngs)}")

print("\n\n=== /api/network ===")
response2 = requests.get("http://127.0.0.1:8001/api/network?date=2025-10-31&hour=17")
data2 = response2.json()

print(f"nodes 数量: {len(data2.get('nodes', []))}")
if data2.get('nodes'):
    print("\n前 5 个节点:")
    for i, node in enumerate(data2['nodes'][:5]):
        print(f"  {i+1}. {node.get('intersection_id')}: lat={node.get('lat')}, lng={node.get('lng')}")