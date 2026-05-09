from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import service


def main() -> None:
    date = service.default_date
    hour = service.default_hour

    dashboard = service.dashboard(date, hour)

    print(f"\n=== /api/dashboard 返回的 nodes 数量: {len(dashboard['nodes'])} ===\n")

    if dashboard["nodes"]:
        print("前 5 个节点的坐标数据:")
        for i, node in enumerate(dashboard["nodes"][:5]):
            print(f"  {i+1}. id={node['intersection_id']}, name={node.get('name', 'N/A')}")
            print(f"     lat={node.get('lat')}, lng={node.get('lng')}")

        print("\n检查所有节点的 lat/lng:")
        for node in dashboard["nodes"]:
            lat = node.get("lat")
            lng = node.get("lng")
            if lat is None or lng is None:
                print(f"  WARNING: {node['intersection_id']} 缺少坐标!")

        print("\n节点 lat 范围:", min(n['lat'] for n in dashboard["nodes"]), "~", max(n['lat'] for n in dashboard["nodes"]))
        print("节点 lng 范围:", min(n['lng'] for n in dashboard["nodes"]), "~", max(n['lng'] for n in dashboard["nodes"]))


if __name__ == "__main__":
    main()