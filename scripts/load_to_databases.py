from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse

import pandas as pd


@dataclass(frozen=True)
class DatasetPaths:
    intersections: Path
    road_segments: Path
    hourly_traffic: Path
    segment_daily: Path


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.drop_duplicates().copy()
    for column in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[column]):
            median = frame[column].median()
            frame[column] = frame[column].fillna(0 if pd.isna(median) else median)
            frame[column] = frame[column].clip(lower=0)
        else:
            mode = frame[column].mode(dropna=True)
            fill_value = mode.iloc[0] if not mode.empty else "未知"
            frame[column] = frame[column].fillna(fill_value)
    return frame


def load_dataset(data_dir: Path) -> dict[str, pd.DataFrame]:
    paths = DatasetPaths(
        intersections=data_dir / "Intersections.csv",
        road_segments=data_dir / "Road_Segments.csv",
        hourly_traffic=data_dir / "Hourly_Traffic.csv",
        segment_daily=data_dir / "Segment_Daily.csv",
    )
    frames = {
        "intersections": pd.read_csv(paths.intersections),
        "road_segments": pd.read_csv(paths.road_segments),
        "hourly_traffic": pd.read_csv(paths.hourly_traffic),
        "segment_daily": pd.read_csv(paths.segment_daily),
    }
    cleaned: dict[str, pd.DataFrame] = {}
    for name, frame in frames.items():
        cleaned[name] = clean_frame(frame)
    return cleaned


def write_to_mysql(frames: dict[str, pd.DataFrame], mysql_url: str) -> None:
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError("缺少 SQLAlchemy，请先安装：pip install sqlalchemy pymysql") from exc
    engine = create_engine(mysql_url)
    frames["intersections"].to_sql("intersections", engine, if_exists="replace", index=False)
    frames["road_segments"].to_sql("road_segments", engine, if_exists="replace", index=False)
    frames["hourly_traffic"].to_sql("hourly_traffic", engine, if_exists="replace", index=False)
    frames["segment_daily"].to_sql("segment_daily", engine, if_exists="replace", index=False)


def write_to_postgis(frames: dict[str, pd.DataFrame], postgis_url: str) -> None:
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError("缺少 SQLAlchemy，请先安装：pip install sqlalchemy psycopg2-binary") from exc
    engine = create_engine(postgis_url)
    intersections = frames["intersections"].copy()
    intersections["geom_wkt"] = intersections.apply(
        lambda row: f"POINT({row['lng']} {row['lat']})",
        axis=1,
    )
    intersections.to_sql("intersections_geo", engine, if_exists="replace", index=False)
    frames["road_segments"].to_sql("road_segments_geo", engine, if_exists="replace", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="qinan_simulated_traffic_csv_40nodes")
    parser.add_argument("--mysql-url", default="")
    parser.add_argument("--postgis-url", default="")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    frames = load_dataset(data_dir)

    if args.mysql_url:
        write_to_mysql(frames, args.mysql_url)
        print("MySQL 导入完成")

    if args.postgis_url:
        write_to_postgis(frames, args.postgis_url)
        print("PostGIS 导入完成")

    if not args.mysql_url and not args.postgis_url:
        print("未指定数据库连接，已完成清洗与结构校验。")


if __name__ == "__main__":
    main()
