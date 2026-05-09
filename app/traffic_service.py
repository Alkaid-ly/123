import logging
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import math
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd


def _out_of_china(lng: float, lat: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _gcj02_offset(lng: float, lat: float) -> tuple[float, float]:
    if _out_of_china(lng, lat):
        return 0.0, 0.0
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return dlng, dlat


def wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    dlng, dlat = _gcj02_offset(lng, lat)
    return lng + dlng, lat + dlat


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    dlng, dlat = _gcj02_offset(lng, lat)
    mg_lng = lng + dlng
    mg_lat = lat + dlat
    return 2 * lng - mg_lng, 2 * lat - mg_lat


@dataclass(frozen=True)
class DatasetPaths:
    intersections: Path
    road_segments: Path
    hourly_traffic: Path
    segment_daily: Path
    readme: Path


@dataclass(frozen=True)
class WeightConfig:
    topology: float = 0.2
    flow: float = 0.3
    distance: float = 0.15
    delay: float = 0.2
    speed: float = 0.15


@dataclass(frozen=True)
class ScoreConfig:
    betweenness: float = 0.34
    degree: float = 0.18
    flow: float = 0.22
    delay: float = 0.14
    queue: float = 0.12


class TrafficAnalysisService:
    """Loads the simulated traffic dataset and exposes analysis views for the UI."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.weight_config = WeightConfig()
        self.score_config = ScoreConfig()
        self.paths = DatasetPaths(
            intersections=data_dir / "Intersections.csv",
            road_segments=data_dir / "Road_Segments.csv",
            hourly_traffic=data_dir / "Hourly_Traffic.csv",
            segment_daily=data_dir / "Segment_Daily.csv",
            readme=data_dir / "README.csv",
        )
        self._load()

    def _load(self) -> None:
        self.intersections = pd.read_csv(self.paths.intersections).drop_duplicates(subset=["intersection_id"])
        self.road_segments = pd.read_csv(self.paths.road_segments).drop_duplicates(subset=["segment_id"])
        self.hourly_traffic = pd.read_csv(self.paths.hourly_traffic).drop_duplicates(subset=["intersection_id", "date", "hour"])
        self.segment_daily = pd.read_csv(self.paths.segment_daily).drop_duplicates(subset=["segment_id", "date"])
        self.dataset_note = pd.read_csv(self.paths.readme)

        self.preprocess_report = self._preprocess()
        self.available_dates = sorted(self.segment_daily["date"].astype(str).unique().tolist())
        self.available_hours = list(range(24))
        self.default_date = self.available_dates[-1]
        self.default_hour = 17

    def _preprocess(self) -> dict[str, Any]:
        frames = {
            "intersections": self.intersections,
            "roadSegments": self.road_segments,
            "hourlyTraffic": self.hourly_traffic,
            "segmentDaily": self.segment_daily,
        }
        report: dict[str, Any] = {}

        for name, frame in frames.items():
            missing_before = int(frame.isna().sum().sum())
            negative_clipped = 0

            for column in frame.columns:
                # 跳过经纬度列，由 _attach_coordinates 专门处理
                if name == "intersections" and column in ["lat", "lng"]:
                    continue

                if pd.api.types.is_numeric_dtype(frame[column]):
                    median = frame[column].median()
                    frame[column] = frame[column].fillna(0 if pd.isna(median) else median)
                    negative_count = int((frame[column] < 0).sum())
                    if negative_count:
                        frame[column] = frame[column].clip(lower=0)
                        negative_clipped += negative_count
                else:
                    mode = frame[column].mode(dropna=True)
                    fill_value = mode.iloc[0] if not mode.empty else "未知"
                    frame[column] = frame[column].fillna(fill_value)

            report[name] = {
                "rows": int(len(frame)),
                "columns": frame.columns.tolist(),
                "missingFilled": missing_before,
                "negativeValuesClipped": negative_clipped,
            }

        self.intersections["design_capacity_vph"] = self.intersections["design_capacity_vph"].astype(float)
        self.hourly_traffic["hour"] = self.hourly_traffic["hour"].astype(int)
        self.hourly_traffic["date"] = self.hourly_traffic["date"].astype(str)
        self.segment_daily["date"] = self.segment_daily["date"].astype(str)
        self._attach_coordinates()

        return report

    def _attach_coordinates(self) -> None:
        """
        为路口附加经纬度坐标。
        1. 严格使用 Intersections.csv 中的 lat, lng 字段（GCJ-02 高德坐标系）。
        2. 不进行坐标转换，直接返回原始 GCJ-02 坐标。
        3. 预处理 road_segments 的 geometry。
        """
        self.intersections["lat"] = pd.to_numeric(self.intersections["lat"], errors="coerce")
        self.intersections["lng"] = pd.to_numeric(self.intersections["lng"], errors="coerce")

        self.intersections = self.intersections.dropna(subset=["lat", "lng"]).copy()
        
        for idx in self.intersections.index:
            self.intersections.at[idx, "lng"] = round(float(self.intersections.at[idx, "lng"]), 6)
            self.intersections.at[idx, "lat"] = round(float(self.intersections.at[idx, "lat"]), 6)

        if "geometry" in self.road_segments.columns:
            self.road_segments["geometry_gcj"] = self.road_segments["geometry"].apply(self._normalize_geometry)

    def _normalize_geometry(self, geometry: Any) -> list[list[float]] | None:
        if geometry is None:
            return None
        if not isinstance(geometry, (list, tuple, str)) and pd.isna(geometry):
            return None
        if isinstance(geometry, str):
            geometry = geometry.strip()
            if not geometry:
                return None
            try:
                geometry = json.loads(geometry)
            except json.JSONDecodeError:
                return None
        if not isinstance(geometry, list):
            return None
        points: list[list[float]] = []
        for point in geometry:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                first = float(point[0])
                second = float(point[1])
            except (TypeError, ValueError):
                continue
            lng, lat = self._normalize_lng_lat(first, second)
            points.append([round(lng, 6), round(lat, 6)])
        return points if len(points) >= 2 else None

    def _normalize_lng_lat(self, first: float, second: float) -> tuple[float, float]:
        if _out_of_china(first, second) and not _out_of_china(second, first):
            return second, first
        if not _out_of_china(first, second) and _out_of_china(second, first):
            return first, second
        if abs(first) <= 90 < abs(second):
            return second, first
        return first, second

    def meta(self) -> dict[str, Any]:
        overview = self.dashboard(self.default_date, self.default_hour)
        dataset_brief = self.dataset_note.rename(
            columns={
                self.dataset_note.columns[0]: "item",
                self.dataset_note.columns[1]: "description",
            }
        ).to_dict(orient="records")
        return {
            "availableDates": self.available_dates,
            "availableHours": self.available_hours,
            "defaultDate": self.default_date,
            "defaultHour": self.default_hour,
            "datasetBrief": dataset_brief,
            "preprocessing": self.preprocess_report,
            "overview": overview["overview"],
        }

    def api_network(self, date: str, hour: int) -> dict[str, Any]:
        data = self.dashboard(date, hour)
        nodes = [
            {
                "intersection_id": node["intersection_id"],
                "name": node["intersection_name"],
                "lng": node["lng"],
                "lat": node["lat"],
                "community_id": node.get("community_id", -1),
                "flow": node.get("slot_total_veh", 0),
                "delay": node.get("slot_delay_s", 0),
                "queue_length": node.get("slot_queue_m", 0),
                "critical_score": node.get("critical_score", 0),
                "slot_saturation": node.get("slot_saturation", 0),
                "functional_zone": node.get("functional_zone", ""),
            }
            for node in data["nodes"]
        ]
        edges = [
            {
                "id": edge["segment_id"],
                "start_node": edge["from_intersection"],
                "end_node": edge["to_intersection"],
                "weight": edge.get("community_weight", 0),
                "flow": edge.get("daily_volume_proxy", 0),
                "speed": edge.get("avg_speed_kmh", 0),
                "delay": edge.get("estimated_delay_s", 0),
                "distance_m": edge.get("length_m", 0),
                "is_cross_community": edge.get("is_cross_community", False),
                "path": edge.get("path", []),
                "road_name": edge.get("road_name", ""),
                "functional_class": edge.get("functional_class", ""),
            }
            for edge in data["edges"]
        ]
        return {"nodes": nodes, "edges": edges, "overview": data["overview"]}

    def api_community(self, date: str, hour: int) -> dict[str, Any]:
        data = self.dashboard(date, hour)
        communities = [
            {
                "id": item["communityId"],
                "node_count": item["size"],
                "total_flow": item["totalVeh"],
                "avg_delay": item["avgDelayS"],
                "avg_speed": item["avgSpeedKmh"],
                "internal_roads": item["internalEdgeCount"],
                "cross_links": item["crossEdgeCount"],
                "congestion_level": item["congestionLevel"],
            }
            for item in data["communityInsights"]
        ]
        cross_edges = [
            {
                "id": edge["segment_id"],
                "start_node": edge["from_intersection"],
                "end_node": edge["to_intersection"],
                "flow": edge.get("daily_volume_proxy", 0),
                "from_community": edge.get("from_community", -1),
                "to_community": edge.get("to_community", -1),
            }
            for edge in data["edges"]
            if edge.get("is_cross_community")
        ]
        return {
            "communities": communities,
            "cross_edges": cross_edges,
            "communityInsights": data["communityInsights"],
            "overview": data["overview"],
        }

    def api_key_nodes(self, date: str, hour: int, limit: int = 10) -> dict[str, Any]:
        data = self.dashboard(date, hour)
        top_nodes = sorted(data["nodes"], key=lambda node: float(node.get("critical_score", 0.0)), reverse=True)[:limit]
        result = [
            {
                "id": node["intersection_id"],
                "name": node["intersection_name"],
                "score": node["critical_score"],
                "flow": node["slot_total_veh"],
                "delay": node["slot_delay_s"],
                "queue_length": node["slot_queue_m"],
                "community_id": node.get("community_id", -1),
                "lng": node["lng"],
                "lat": node["lat"],
                "rank": idx + 1,
            }
            for idx, node in enumerate(top_nodes)
        ]
        return {"key_nodes": result, "topNodes": top_nodes, "overview": data["overview"]}

    def api_intersection_detail(self, intersection_id: str, date: str) -> dict[str, Any]:
        detail = self.intersection_detail(intersection_id, date)
        intersection = detail["intersection"]
        daily_context = self._daily_context(self._resolve_date(date))
        community_id = int(daily_context["community_map"].get(intersection_id, -1))
        day_series = detail["timeseries"]
        avg_flow = float(np.mean([item["totalVeh"] for item in day_series])) if day_series else 0.0
        avg_delay = float(np.mean([item["avgDelayS"] for item in day_series])) if day_series else 0.0
        avg_queue = float(np.mean([item["queueLengthM"] for item in day_series])) if day_series else 0.0
        return {
            "id": intersection["intersection_id"],
            "name": intersection["intersection_name"],
            "lng": intersection["lng"],
            "lat": intersection["lat"],
            "community_id": community_id,
            "flow": round(avg_flow, 2),
            "delay": round(avg_delay, 2),
            "queue_length": round(avg_queue, 2),
            "connectedSegments": detail["connectedSegments"],
            "timeseries": day_series,
            "intersection": intersection,
            "criticalReference": detail["criticalReference"],
        }

    def dashboard(self, date: str, hour: int) -> dict[str, Any]:
        selected_date = self._resolve_date(date)
        selected_hour = self._resolve_hour(hour)

        daily_context = self._daily_context(selected_date)
        slot_stats = self._slot_stats(selected_date, selected_hour)

        nodes = daily_context["nodes"].merge(slot_stats, on="intersection_id", how="left")
        nodes["slot_total_veh"] = nodes["slot_total_veh"].fillna(nodes["avg_daily_volume"])
        nodes["slot_saturation"] = nodes["slot_saturation"].fillna(nodes["avg_daily_saturation"])
        nodes["slot_speed_kmh"] = nodes["slot_speed_kmh"].fillna(nodes["avg_daily_speed"])
        nodes["slot_delay_s"] = nodes["slot_delay_s"].fillna(nodes["avg_daily_delay"])
        nodes["slot_queue_m"] = nodes["slot_queue_m"].fillna(nodes["max_queue_m"])

        nodes["pressure_index"] = (
            nodes["slot_total_veh"] / nodes["design_capacity_vph"].replace(0, np.nan)
        ).fillna(0.0)
        nodes["critical_score"] = self._critical_score(nodes)
        nodes["risk_level"] = nodes["slot_saturation"].apply(self._risk_level)
        nodes["community_id"] = nodes["intersection_id"].map(daily_context["community_map"]).fillna(-1).astype(int)

        edges = daily_context["edges"].copy()
        coords_lookup = daily_context["coords_lookup"]
        edges["path"] = edges.apply(lambda row: self._edge_path(row, coords_lookup), axis=1)
        edges["from_community"] = edges["from_intersection"].map(daily_context["community_map"]).fillna(-1).astype(int)
        edges["to_community"] = edges["to_intersection"].map(daily_context["community_map"]).fillna(-1).astype(int)
        edges["is_cross_community"] = edges["from_community"] != edges["to_community"]
        edges["risk_level"] = edges["v_c_ratio"].apply(self._edge_risk_level)

        boundary_nodes = set(
            pd.concat(
                [
                    edges.loc[edges["is_cross_community"], "from_intersection"],
                    edges.loc[edges["is_cross_community"], "to_intersection"],
                ]
            )
            .dropna()
            .astype(str)
            .tolist()
        )
        nodes["is_boundary"] = nodes["intersection_id"].isin(boundary_nodes)

        overview = self._overview(nodes, edges, daily_context, selected_date, selected_hour)
        charts = self._charts(nodes, selected_date)
        community_insights = self._community_insights(nodes, edges, daily_context["communities"])

        return {
            "overview": overview,
            "nodes": nodes.to_dict(orient="records"),
            "edges": edges.to_dict(orient="records"),
            "communities": daily_context["communities"],
            "communityInsights": community_insights,
            "charts": charts,
        }

    def _community_insights(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        communities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for community in communities:
            members = set(community["members"])
            subset_nodes = nodes[nodes["intersection_id"].isin(members)]
            subset_edges = edges[
                edges["from_intersection"].isin(members) & edges["to_intersection"].isin(members)
            ]
            cross_edges = edges[
                (edges["from_intersection"].isin(members) ^ edges["to_intersection"].isin(members))
            ]

            total_veh = float(subset_nodes["slot_total_veh"].sum()) if not subset_nodes.empty else 0.0
            avg_delay = float(subset_nodes["slot_delay_s"].mean()) if not subset_nodes.empty else 0.0
            avg_speed = float(subset_nodes["slot_speed_kmh"].mean()) if not subset_nodes.empty else 0.0
            avg_sat = float(subset_nodes["slot_saturation"].mean()) if not subset_nodes.empty else 0.0

            if avg_sat >= 0.9:
                congestion_level = "严重拥堵"
            elif avg_sat >= 0.75:
                congestion_level = "中度拥堵"
            elif avg_sat >= 0.55:
                congestion_level = "轻度拥堵"
            else:
                congestion_level = "畅通"

            results.append(
                {
                    "communityId": community["communityId"],
                    "dominantZone": community.get("dominantZone", "未知"),
                    "size": int(community.get("size", len(members))),
                    "totalVeh": int(round(total_veh)),
                    "avgDelayS": round(avg_delay, 1),
                    "avgSpeedKmh": round(avg_speed, 1),
                    "avgSaturation": round(avg_sat, 3),
                    "congestionLevel": congestion_level,
                    "internalEdgeCount": int(len(subset_edges)),
                    "crossEdgeCount": int(len(cross_edges)),
                }
            )

        results.sort(key=lambda item: (-item["size"], item["communityId"]))
        return results

    def intersection_detail(self, intersection_id: str, date: str) -> dict[str, Any]:
        selected_date = self._resolve_date(date)
        node_row = self.intersections[self.intersections["intersection_id"] == intersection_id]
        if node_row.empty:
            raise KeyError(f"Unknown intersection: {intersection_id}")

        day_series = (
            self.hourly_traffic[
                (self.hourly_traffic["date"] == selected_date)
                & (self.hourly_traffic["intersection_id"] == intersection_id)
            ]
            .sort_values("hour")
            .copy()
        )
        related_segments = self.road_segments[
            (self.road_segments["from_intersection"] == intersection_id)
            | (self.road_segments["to_intersection"] == intersection_id)
        ].copy()
        daily_segments = self.segment_daily[self.segment_daily["date"] == selected_date]
        related_segments = related_segments.merge(daily_segments, on="segment_id", how="left", suffixes=("", "_daily"))

        daily_context = self._daily_context(selected_date)
        community_map = daily_context.get("community_map", {})
        score_row = daily_context["nodes"][daily_context["nodes"]["intersection_id"] == intersection_id]
        critical_score = float(score_row["betweenness"].iloc[0]) if not score_row.empty else 0.0

        return {
            "intersection": node_row.iloc[0].to_dict(),
            "criticalReference": round(critical_score, 4),
            "timeseries": [
                {
                    "hour": int(row["hour"]),
                    "totalVeh": int(row["total_veh"]),
                    "saturation": round(float(row["saturation"]), 3),
                    "avgSpeedKmh": round(float(row["avg_speed_kmh"]), 1),
                    "avgDelayS": round(float(row["avg_delay_s"]), 1),
                    "queueLengthM": round(float(row["queue_length_m"]), 1),
                }
                for _, row in day_series.iterrows()
            ],
            "connectedSegments": [
                {
                    "segmentId": row["segment_id"],
                    "roadName": row.get("road_name", ""),
                    "fromIntersection": row.get("from_intersection", ""),
                    "toIntersection": row.get("to_intersection", ""),
                    "direction": "out" if row.get("from_intersection") == intersection_id else "in",
                    "otherEnd": row["to_intersection"]
                    if row["from_intersection"] == intersection_id
                    else row["from_intersection"],
                    "lengthM": round(float(row.get("length_m", 0.0) or 0.0), 1),
                    "lanes": int(row.get("lanes", 0) or 0),
                    "functionalClass": row.get("functional_class", ""),
                    "freeFlowSpeedKmh": round(float(row.get("free_flow_speed_kmh", 0.0) or 0.0), 1),
                    "dailyVolume": int(round(float(row.get("daily_volume_proxy", 0.0) or 0.0))),
                    "peakHourVolume": int(round(float(row.get("peak_hour_volume", 0.0) or 0.0))),
                    "vCRatio": round(float(row.get("v_c_ratio", 0.0) or 0.0), 3),
                    "avgSpeedKmh": round(float(row.get("avg_speed_kmh", 0.0) or 0.0), 1),
                    "travelTimeMin": round(float(row.get("travel_time_min", 0.0) or 0.0), 2),
                    "riskLevel": self._edge_risk_level(float(row.get("v_c_ratio", 0.0) or 0.0)),
                    "fromCommunity": int(community_map.get(row.get("from_intersection", ""), -1)),
                    "toCommunity": int(community_map.get(row.get("to_intersection", ""), -1)),
                    "isCrossCommunity": int(community_map.get(row.get("from_intersection", ""), -1))
                    != int(community_map.get(row.get("to_intersection", ""), -1)),
                }
                for _, row in related_segments.iterrows()
            ],
        }

    def _resolve_date(self, date: str | None) -> str:
        if date in self.available_dates:
            return str(date)
        return self.default_date

    def _resolve_hour(self, hour: int | None) -> int:
        if hour in self.available_hours:
            return int(hour)
        return self.default_hour

    @lru_cache(maxsize=64)
    def _daily_context(self, date: str) -> dict[str, Any]:
        daily_columns = [
            "segment_id",
            "date",
            "daily_volume_proxy",
            "avg_speed_kmh",
            "peak_hour_volume",
            "v_c_ratio",
            "travel_time_min",
            "community_weight",
        ]
        edges = self.road_segments.merge(
            self.segment_daily.loc[self.segment_daily["date"] == date, daily_columns],
            on="segment_id",
            how="left",
        )

        edges = edges.copy()
        edges["daily_volume_proxy"] = pd.to_numeric(edges["daily_volume_proxy"], errors="coerce").fillna(0.0)
        edges["avg_speed_kmh"] = pd.to_numeric(edges["avg_speed_kmh"], errors="coerce").fillna(0.0)
        edges["free_flow_speed_kmh"] = pd.to_numeric(edges["free_flow_speed_kmh"], errors="coerce").fillna(0.0)
        edges["v_c_ratio"] = pd.to_numeric(edges["v_c_ratio"], errors="coerce").fillna(0.0)
        edges["travel_time_min"] = pd.to_numeric(edges["travel_time_min"], errors="coerce").fillna(0.0)
        edges["community_weight"] = pd.to_numeric(edges["community_weight"], errors="coerce").fillna(0.0)

        max_volume = float(edges["daily_volume_proxy"].max() or 0.0)
        max_distance = float(edges["length_m"].max() or 1.0)
        day_agg = (
            self.hourly_traffic[self.hourly_traffic["date"] == date]
            .groupby("intersection_id", as_index=False)
            .agg(
                avg_daily_volume=("total_veh", "mean"),
                peak_daily_volume=("total_veh", "max"),
                avg_daily_saturation=("saturation", "mean"),
                peak_daily_saturation=("saturation", "max"),
                avg_daily_speed=("avg_speed_kmh", "mean"),
                avg_daily_delay=("avg_delay_s", "mean"),
                max_queue_m=("queue_length_m", "max"),
            )
        )
        node_delay_lookup = {
            row["intersection_id"]: float(row["avg_daily_delay"])
            for _, row in day_agg.iterrows()
            if not pd.isna(row["avg_daily_delay"])
        }
        max_delay = float(day_agg["avg_daily_delay"].max() or 0.0)

        graph = nx.Graph()
        coords_lookup = {
            row["intersection_id"]: {"lat": float(row["lat"]), "lng": float(row["lng"])}
            for _, row in self.intersections.iterrows()
        }

        for _, row in self.intersections.iterrows():
            graph.add_node(
                row["intersection_id"],
                name=row["intersection_name"],
                zone=row["functional_zone"],
                road_class=row["road_class"],
            )

        for _, row in edges.iterrows():
            from_delay = node_delay_lookup.get(row["from_intersection"], 0.0)
            to_delay = node_delay_lookup.get(row["to_intersection"], 0.0)
            estimated_delay = (from_delay + to_delay) / 2.0
            edges.loc[edges["segment_id"] == row["segment_id"], "estimated_delay_s"] = estimated_delay
            weight = self._edge_affinity_weight(
                row,
                max_volume=max_volume,
                max_distance=max_distance,
                estimated_delay=estimated_delay,
                max_delay=max_delay,
            )
            graph.add_edge(
                row["from_intersection"],
                row["to_intersection"],
                weight=weight,
                distance=max(float(row["travel_time_min"]), 0.001),
            )

        communities_raw = list(nx.algorithms.community.asyn_lpa_communities(graph, weight="weight", seed=42))
        communities_raw = self._merge_small_communities(graph, communities_raw, min_size=3)
        communities = []
        community_map: dict[str, int] = {}
        for idx, members in enumerate(sorted(communities_raw, key=lambda group: (-len(group), sorted(group)[0]))):
            member_list = sorted(members)
            subset = self.intersections[self.intersections["intersection_id"].isin(member_list)]
            dominant_zone = subset["functional_zone"].mode(dropna=True).iloc[0]
            avg_vc = (
                edges[
                    edges["from_intersection"].isin(member_list)
                    & edges["to_intersection"].isin(member_list)
                ]["v_c_ratio"].mean()
            )
            community = {
                "communityId": idx,
                "size": len(member_list),
                "dominantZone": dominant_zone,
                "avgVCRatio": round(float(avg_vc if not pd.isna(avg_vc) else 0.0), 3),
                "members": member_list,
            }
            communities.append(community)
            for node in member_list:
                community_map[node] = idx

        betweenness = nx.betweenness_centrality(graph, weight="distance", normalized=True)
        degree_centrality = nx.degree_centrality(graph)
        closeness = nx.closeness_centrality(graph, distance="distance")

        nodes = self.intersections.merge(day_agg, on="intersection_id", how="left")
        nodes["betweenness"] = nodes["intersection_id"].map(betweenness).fillna(0.0)
        nodes["degree_centrality"] = nodes["intersection_id"].map(degree_centrality).fillna(0.0)
        nodes["closeness_centrality"] = nodes["intersection_id"].map(closeness).fillna(0.0)

        return {
            "date": date,
            "graph": graph,
            "edges": edges,
            "nodes": nodes,
            "communities": communities,
            "community_map": community_map,
            "coords_lookup": coords_lookup,
        }

    def _edge_affinity_weight(
        self,
        row: pd.Series,
        max_volume: float,
        max_distance: float,
        estimated_delay: float,
        max_delay: float,
    ) -> float:
        base = max(float(row.get("community_weight") or 0.0), 0.0)
        volume = max(float(row.get("daily_volume_proxy") or 0.0), 0.0)
        speed = max(float(row.get("avg_speed_kmh") or 0.0), 0.0)
        free_speed = max(float(row.get("free_flow_speed_kmh") or 0.0), 0.0)
        distance = max(float(row.get("length_m") or 0.0), 0.0)
        topology = 1.0

        volume_norm = 0.0 if max_volume <= 0 else np.log1p(volume) / np.log1p(max_volume)
        distance_norm = 0.0 if max_distance <= 0 else min(distance / max_distance, 1.0)
        delay_norm = 0.0 if max_delay <= 0 else min(max(estimated_delay / max_delay, 0.0), 1.0)
        if free_speed <= 0:
            speed_norm = 0.0
        else:
            speed_norm = min(max(1.0 - speed / free_speed, 0.0), 1.0)

        config = self.weight_config
        blended = (
            config.topology * topology
            + config.flow * volume_norm
            + config.distance * (1.0 - distance_norm)
            + config.delay * delay_norm
            + config.speed * speed_norm
        )
        return max(float(base * (1.0 + blended)), 0.001)

    @staticmethod
    def _merge_small_communities(
        graph: nx.Graph, communities_raw: list[set[str]], min_size: int
    ) -> list[set[str]]:
        large_groups = [set(group) for group in communities_raw if len(group) >= min_size]
        small_groups = [set(group) for group in communities_raw if len(group) < min_size]

        if not large_groups:
            return [set(group) for group in communities_raw]

        for group in small_groups:
            best_idx = 0
            best_score = -1.0
            for idx, target_group in enumerate(large_groups):
                score = 0.0
                for node in group:
                    for neighbor in graph.neighbors(node):
                        if neighbor in target_group:
                            score += float(graph[node][neighbor].get("weight", 0.0))
                if score > best_score:
                    best_score = score
                    best_idx = idx
            large_groups[best_idx].update(group)
        return large_groups

    def _slot_stats(self, date: str, hour: int) -> pd.DataFrame:
        frame = self.hourly_traffic[
            (self.hourly_traffic["date"] == date) & (self.hourly_traffic["hour"] == hour)
        ].copy()
        frame = frame.rename(
            columns={
                "total_veh": "slot_total_veh",
                "saturation": "slot_saturation",
                "avg_speed_kmh": "slot_speed_kmh",
                "avg_delay_s": "slot_delay_s",
                "queue_length_m": "slot_queue_m",
            }
        )
        return frame[
            [
                "intersection_id",
                "slot_total_veh",
                "slot_saturation",
                "slot_speed_kmh",
                "slot_delay_s",
                "slot_queue_m",
                "weather",
                "day_type",
            ]
        ]

    def _overview(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        daily_context: dict[str, Any],
        date: str,
        hour: int,
    ) -> dict[str, Any]:
        high_pressure = int((nodes["slot_saturation"] >= 0.75).sum())
        alignment = self._community_alignment(daily_context["communities"])
        return {
            "selectedDate": date,
            "selectedHour": hour,
            "totalIntersections": int(len(nodes)),
            "totalSegments": int(len(edges)),
            "communityCount": int(len(daily_context["communities"])),
            "avgSpeedKmh": round(float(nodes["slot_speed_kmh"].mean()), 1),
            "avgSaturation": round(float(nodes["slot_saturation"].mean()), 3),
            "avgDelayS": round(float(nodes["slot_delay_s"].mean()), 1),
            "highPressureCount": high_pressure,
            "zoneAlignment": round(alignment * 100, 1),
            "weather": self._mode_or_default(nodes.get("weather"), "未知"),
            "dayType": self._mode_or_default(nodes.get("day_type"), "未知"),
        }

    def _charts(self, nodes: pd.DataFrame, date: str) -> dict[str, Any]:
        comps = pd.DataFrame(
            {
                "betweenness_norm": self._normalize(nodes["betweenness"]),
                "degree_norm": self._normalize(nodes["degree_centrality"]),
                "flow_norm": self._normalize(nodes["slot_total_veh"]),
                "delay_norm": self._normalize(nodes["slot_delay_s"]),
                "queue_norm": self._normalize(nodes["slot_queue_m"]),
            },
            index=nodes.index,
        )
        top_nodes = nodes.sort_values("critical_score", ascending=False)[
            [
                "intersection_id",
                "intersection_name",
                "critical_score",
                "slot_total_veh",
                "slot_delay_s",
                "slot_queue_m",
                "slot_saturation",
                "community_id",
                "functional_zone",
                "betweenness",
                "degree_centrality",
            ]
        ].copy()
        top_nodes = top_nodes.join(comps, how="left")
        top_nodes.insert(0, "rank", range(1, len(top_nodes) + 1))
        top_nodes["critical_score"] = top_nodes["critical_score"].round(3)
        top_nodes["slot_saturation"] = top_nodes["slot_saturation"].round(3)

        hourly_trend = (
            self.hourly_traffic[self.hourly_traffic["date"] == date]
            .groupby("hour", as_index=False)
            .agg(
                totalVeh=("total_veh", "sum"),
                avgSpeedKmh=("avg_speed_kmh", "mean"),
                avgSaturation=("saturation", "mean"),
            )
        )
        hourly_trend["avgSpeedKmh"] = hourly_trend["avgSpeedKmh"].round(1)
        hourly_trend["avgSaturation"] = hourly_trend["avgSaturation"].round(3)

        zone_load = (
            nodes.groupby("functional_zone", as_index=False)
            .agg(
                avgSaturation=("slot_saturation", "mean"),
                avgSpeedKmh=("slot_speed_kmh", "mean"),
                totalVeh=("slot_total_veh", "sum"),
                keyNodeCount=("risk_level", lambda values: int((values == "高").sum())),
            )
            .sort_values("totalVeh", ascending=False)
        )
        zone_load["avgSaturation"] = zone_load["avgSaturation"].round(3)
        zone_load["avgSpeedKmh"] = zone_load["avgSpeedKmh"].round(1)

        community_stats = []
        for community in self._daily_context(date)["communities"]:
            subset = nodes[nodes["intersection_id"].isin(community["members"])]
            community_stats.append(
                {
                    "communityId": community["communityId"],
                    "size": community["size"],
                    "dominantZone": community["dominantZone"],
                    "avgCriticalScore": round(float(subset["critical_score"].mean()), 3),
                    "avgSaturation": round(float(subset["slot_saturation"].mean()), 3),
                }
            )

        return {
            "topNodes": top_nodes.to_dict(orient="records"),
            "hourlyTrend": hourly_trend.to_dict(orient="records"),
            "zoneLoad": zone_load.to_dict(orient="records"),
            "communityStats": community_stats,
        }

    def _normalize(self, series: pd.Series) -> pd.Series:
        min_val = series.min()
        max_val = series.max()
        if max_val == min_val:
            return pd.Series([0.0] * len(series), index=series.index)
        return (series - min_val) / (max_val - min_val)

    def _critical_score(self, nodes: pd.DataFrame) -> pd.Series:
        # Ensure normalized columns exist or create them
        nodes["betweenness_norm"] = self._normalize(nodes["betweenness"])
        nodes["degree_norm"] = self._normalize(nodes["degree_centrality"])
        nodes["flow_norm"] = self._normalize(nodes["slot_total_veh"])
        nodes["delay_norm"] = self._normalize(nodes["slot_delay_s"])
        nodes["queue_norm"] = self._normalize(nodes["slot_queue_m"])

        config = self.score_config
        critical_score = (
            config.betweenness * nodes["betweenness_norm"]
            + config.degree * nodes["degree_norm"]
            + config.flow * nodes["flow_norm"]
            + config.delay * nodes["delay_norm"]
            + config.queue * nodes["queue_norm"]
        )
        return critical_score

    def _mode_or_default(self, series: pd.Series | None, default: Any) -> Any:
        if series is None or series.empty:
            return default
        mode_val = series.mode()
        if mode_val.empty:
            return default
        return mode_val.iloc[0]

    def _risk_level(self, value: float, is_edge: bool = False) -> str:
        if value >= 0.9:
            return "高"
        elif value >= (0.7 if is_edge else 0.75):
            return "中"
        elif value >= 0.55:
            return "低"
        return "畅通"

    def _edge_risk_level(self, v_c_ratio: float) -> str:
        return self._risk_level(v_c_ratio, is_edge=True)

    def _community_alignment(self, communities: list[dict[str, Any]]) -> float:
        if not communities:
            return 0.0
        total_nodes = sum(c["size"] for c in communities)
        return 1.0 if total_nodes > 0 else 0.0

    def _edge_path(self, row: pd.Series, coords_lookup: dict[str, Any]) -> list[list[float]]:
        """
        确定路段轨迹。
        优先使用 Road_Segments.csv 中的 geometry 轨迹，否则回退为路口直线连接。
        """
        from_node = row["from_intersection"]
        to_node = row["to_intersection"]

        if from_node not in coords_lookup or to_node not in coords_lookup:
            return []

        geometry_path = row.get("geometry_gcj")
        if geometry_path is None:
            geometry_path = row.get("geometry")
        geometry_path = self._normalize_geometry(geometry_path)
        if geometry_path:
            path = [list(point) for point in geometry_path]
            from_coord = coords_lookup[from_node]
            to_coord = coords_lookup[to_node]
            from_point = [from_coord["lng"], from_coord["lat"]]
            to_point = [to_coord["lng"], to_coord["lat"]]
            start = path[0]
            end = path[-1]
            if self._squared_distance(end, from_point) < self._squared_distance(start, from_point):
                path = list(reversed(path))
            path[0] = from_point
            path[-1] = to_point
            return path

        # 直接使用路口的真实坐标连接
        return [
            [coords_lookup[from_node]["lng"], coords_lookup[from_node]["lat"]],
            [coords_lookup[to_node]["lng"], coords_lookup[to_node]["lat"]],
        ]

    @staticmethod
    def _squared_distance(point: list[float], target: list[float]) -> float:
        return (point[0] - target[0]) ** 2 + (point[1] - target[1]) ** 2
