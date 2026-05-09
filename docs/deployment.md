# 部署说明

## 1. 环境要求

- Windows/Linux/macOS
- Python 3.11+
- 可联网（前端库通过 CDN 加载）
- 可选数据库：
  - MySQL 8+
  - PostgreSQL 14+（PostGIS 扩展）

## 2. 本地快速启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\run.ps1
```

浏览器访问：

```text
http://127.0.0.1:8000
```

## 3. 数据库初始化（可选）

MySQL：

```sql
source sql/mysql_schema.sql;
```

PostGIS：

```sql
\i sql/postgis_schema.sql
```

## 4. 执行数据清洗与入库

仅执行清洗校验：

```powershell
python scripts/load_to_databases.py --data-dir qinan_simulated_traffic_csv_40nodes
```

导入 MySQL：

```powershell
python scripts/load_to_databases.py --mysql-url "mysql+pymysql://root:password@127.0.0.1:3306/traffic_analysis"
```

导入 PostGIS：

```powershell
python scripts/load_to_databases.py --postgis-url "postgresql+psycopg2://postgres:password@127.0.0.1:5432/traffic_analysis"
```

## 5. 验收检查建议

- `/api/network` 返回 40 个路口与 67 条路段
- `/api/community` 返回社区列表与跨社区连接
- `/api/key-nodes` 默认返回 Top10 且评分为 0-100
- `/api/intersection/QNA001` 返回路口基础信息、时序与连接道路
- 页面具备 5 个页签：总览、路网地图、社区检测、关键路口、路口详情
