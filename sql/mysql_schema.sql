CREATE DATABASE IF NOT EXISTS traffic_analysis DEFAULT CHARACTER SET utf8mb4;
USE traffic_analysis;

CREATE TABLE IF NOT EXISTS intersections (
  intersection_id VARCHAR(32) PRIMARY KEY,
  intersection_name VARCHAR(128) NOT NULL,
  road_class VARCHAR(32),
  functional_zone VARCHAR(64),
  zone_hint_for_validation VARCHAR(16),
  grid_x INT,
  grid_y INT,
  design_capacity_vph DOUBLE,
  degree INT,
  lat DOUBLE,
  lng DOUBLE
);

CREATE TABLE IF NOT EXISTS road_segments (
  segment_id VARCHAR(32) PRIMARY KEY,
  from_intersection VARCHAR(32) NOT NULL,
  to_intersection VARCHAR(32) NOT NULL,
  road_name VARCHAR(64),
  length_m DOUBLE,
  lanes INT,
  free_flow_speed_kmh DOUBLE,
  functional_class VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS hourly_traffic (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  date DATE NOT NULL,
  hour INT NOT NULL,
  intersection_id VARCHAR(32) NOT NULL,
  intersection_name VARCHAR(128),
  functional_zone VARCHAR(64),
  road_class VARCHAR(32),
  inbound_veh DOUBLE,
  outbound_veh DOUBLE,
  total_veh DOUBLE,
  design_capacity_vph DOUBLE,
  saturation DOUBLE,
  avg_speed_kmh DOUBLE,
  avg_delay_s DOUBLE,
  queue_length_m DOUBLE,
  weather VARCHAR(32),
  day_type VARCHAR(32),
  degree INT,
  zone_hint_for_validation VARCHAR(16),
  INDEX idx_hourly_date_hour (date, hour),
  INDEX idx_hourly_intersection (intersection_id)
);

CREATE TABLE IF NOT EXISTS segment_daily (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  date DATE NOT NULL,
  segment_id VARCHAR(32) NOT NULL,
  from_intersection VARCHAR(32),
  to_intersection VARCHAR(32),
  road_name VARCHAR(64),
  length_m DOUBLE,
  lanes INT,
  free_flow_speed_kmh DOUBLE,
  functional_class VARCHAR(32),
  daily_volume_proxy DOUBLE,
  avg_speed_kmh DOUBLE,
  peak_hour_volume DOUBLE,
  v_c_ratio DOUBLE,
  travel_time_min DOUBLE,
  community_weight DOUBLE,
  INDEX idx_segment_daily_date (date),
  INDEX idx_segment_daily_segment (segment_id)
);
