# 城市交通网络社区检测及关键路口分析系统

基于秦安县核心城区 40 个路口的模拟交通数据，完成城市交通网络建模、标签传播社区检测、关键路口识别和地图联动可视化。系统采用 `FastAPI + Vue 3 + Element Plus + Leaflet + ECharts`，后端负责数据预处理与复杂网络分析，前端负责地图与仪表盘展示。

## 已实现功能

- 五大页面：总览、路网地图、社区检测、关键路口、路口详情。
- 路网可视化：渲染全部路口和道路，支持缩放、拖动、图层表达与提示信息。
- 社区检测：标签传播算法（LPA）+ 小社区合并后处理，支持社区着色与分区统计。
- 关键路口识别：Score = a×介数中心性 + b×节点度 + c×流量 + d×延误 + e×排队长度，标准化为 0-100 分。
- 图表分析：社区规模分布、小时趋势、功能区负载、Top10关键路口指标对比。
- 交互联动：社区表格与地图联动、关键路口排行与地图联动、点击路口查看详情时序与连接道路。

## 核心接口

- `GET /api/network`：完整路网（nodes + edges）
- `GET /api/community`：社区结果与跨社区连接
- `GET /api/key-nodes`：关键路口 TopN（默认 Top10）
- `GET /api/intersection/{id}`：指定路口详情

详细字段见 [docs/api.md](docs/api.md)。

## 运行方式

1. 创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

3. 启动系统：

```powershell
.\run.ps1
```

或直接执行：

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. 打开浏览器访问：

```text
http://127.0.0.1:8000
```

## 数据说明

- 数据目录：`qinan_simulated_traffic_csv_40nodes`

- `Intersections.csv`：40 个核心路口基础属性
- `Road_Segments.csv`：67 条路段连接关系
- `Hourly_Traffic.csv`：2025-10-01 至 2025-10-31 按小时生成的路口交通指标
- `Segment_Daily.csv`：按天统计的路段交通状态与社区权重

## 数据入库（MySQL/PostGIS）

- 脚本：`scripts/load_to_databases.py`
- MySQL 建表：`sql/mysql_schema.sql`
- PostGIS 建表：`sql/postgis_schema.sql`
- 部署与入库流程见 [docs/deployment.md](docs/deployment.md)

## 测试

```powershell
.\.venv\Scripts\python.exe tests\smoke_api.py
```

## 说明

- 数据集为模拟数据，地图坐标根据网格位置映射到秦安县城区中心附近，用于可视化展示和系统联调。
- 页面依赖 CDN 加载前端库，因此运行时需要联网。
