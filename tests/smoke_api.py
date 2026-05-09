from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import service


def main() -> None:
    date = service.default_date
    hour = service.default_hour

    network = service.api_network(date, hour)
    assert "nodes" in network and "edges" in network
    assert len(network["nodes"]) == 40
    assert len(network["edges"]) == 67

    community = service.api_community(date, hour)
    assert "communities" in community
    assert len(community["communities"]) > 0

    key_nodes = service.api_key_nodes(date, hour, 10)
    assert len(key_nodes["key_nodes"]) == 10
    assert key_nodes["key_nodes"][0]["score"] >= key_nodes["key_nodes"][-1]["score"]

    detail = service.api_intersection_detail("QNA001", date)
    assert detail["id"] == "QNA001"
    assert len(detail["timeseries"]) == 24

    print("smoke_api passed")


if __name__ == "__main__":
    main()
