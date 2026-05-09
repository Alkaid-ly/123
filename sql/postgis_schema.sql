CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS traffic;

CREATE TABLE IF NOT EXISTS traffic.intersections_geo (
  intersection_id TEXT PRIMARY KEY,
  intersection_name TEXT,
  road_class TEXT,
  functional_zone TEXT,
  zone_hint_for_validation TEXT,
  grid_x INT,
  grid_y INT,
  design_capacity_vph DOUBLE PRECISION,
  degree INT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  geom geometry(Point, 4326)
);

CREATE TABLE IF NOT EXISTS traffic.road_segments_geo (
  segment_id TEXT PRIMARY KEY,
  from_intersection TEXT,
  to_intersection TEXT,
  road_name TEXT,
  length_m DOUBLE PRECISION,
  lanes INT,
  free_flow_speed_kmh DOUBLE PRECISION,
  functional_class TEXT
);

CREATE INDEX IF NOT EXISTS idx_intersections_geom ON traffic.intersections_geo USING GIST (geom);
