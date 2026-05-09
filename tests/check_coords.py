from __future__ import annotations

from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import service


def main() -> None:
    date = service.default_date
    hour = service.default_hour

    network = service.api_network(date, hour)

    print(f"\n=== API /api/network 返回的 nodes 数量: {len(network['nodes'])} ===\n")

    print("前 5 个节点的坐标数据:")
    for i, node in enumerate(network["nodes"][:5]):
        print(f"  {i+1}. id={node['intersection_id']}, name={node['name']}")
        print(f"     lat={node.get('lat')}, lng={node.get('lng')}")

    print("\n检查所有 40 个节点的 lat/lng:")
    for node in network["nodes"]:
        lat = node.get("lat")
        lng = node.get("lng")
        if lat is None or lng is None:
            print(f"  WARNING: {node['intersection_id']} 缺少坐标!")
        elif lat < 34 or lat > 35 or lng < 105 or lng > 106:
            print(f"  WARNING: {node['intersection_id']} 坐标可疑: lat={lat}, lng={lng}")

    print("\n节点 lat 范围:", min(n['lat'] for n in network["nodes"]), "~", max(n['lat'] for n in network["nodes"]))
    print("节点 lng 范围:", min(n['lng'] for n in network["nodes"]), "~", max(n['lng'] for n in network["nodes"]))


if __name__ == "__main__":
    main()