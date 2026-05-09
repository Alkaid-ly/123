# 城市交通网络分析系统接口文档

## 通用说明

- Base URL: `http://127.0.0.1:8000`
- 响应格式：`application/json`
- 跨域：已开启 CORS，支持前端直接调用
- 状态码：
  - `200` 成功
  - `400` 参数错误
  - `404` 资源不存在
  - `500` 服务错误

## 1. 获取完整路网

- **GET** `/api/network`
- Query 参数：
  - `date`：可选，格式 `YYYY-MM-DD`
  - `hour`：可选，范围 `0-23`
- 返回结构：

```json
{
  "nodes": [
    {
      "id": "QNA001",
      "lng": 105.668917,
      "lat": 34.851686,
      "community_id": 0,
      "flow": 1486,
      "delay": 32.2
    }
  ],
  "edges": [
    {
      "id": "S001",
      "start_node": "QNA001",
      "end_node": "QNA002",
      "weight": 17.8,
      "flow": 9599
    }
  ],
  "overview": {}
}
```

## 2. 获取社区划分

- **GET** `/api/community`
- Query 参数：
  - `date`：可选
  - `hour`：可选
- 返回结构：

```json
{
  "communities": [
    {
      "id": 0,
      "node_count": 8,
      "total_flow": 11293,
      "avg_delay": 29.1,
      "congestion_level": "轻度拥堵"
    }
  ],
  "cross_edges": [],
  "communityInsights": [],
  "overview": {}
}
```

## 3. 获取关键路口 TopN

- **GET** `/api/key-nodes`
- Query 参数：
  - `date`：可选
  - `hour`：可选
  - `limit`：可选，默认 `10`，范围 `1-50`
- 返回结构：

```json
{
  "key_nodes": [
    {
      "id": "QNA010",
      "score": 92.35,
      "flow": 1680,
      "delay": 38.2,
      "queue_length": 45.3,
      "rank": 1
    }
  ],
  "overview": {}
}
```

## 4. 获取路口详情

- **GET** `/api/intersection/{id}`
- Path 参数：
  - `id`：路口 ID，如 `QNA001`
- Query 参数：
  - `date`：可选
- 返回结构：

```json
{
  "id": "QNA001",
  "lng": 105.668917,
  "lat": 34.851686,
  "community_id": 0,
  "flow": 853.4,
  "delay": 24.8,
  "queue_length": 29.3,
  "connected_edges": [],
  "timeseries": []
}
```
