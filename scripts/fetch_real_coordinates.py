"""
自动获取秦安县40个路口的真实经纬度（高德地图）
使用方法：
  1. 注册高德开放平台账号: https://console.amap.com/dev/key/app
  2. 创建应用，获取 Web 服务 API Key
  3. 运行: python fetch_real_coordinates.py YOUR_API_KEY
"""

import requests
import json
import csv
import sys
import time

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"

def get_coordinate(api_key: str, address: str, city: str = "天水市") -> dict | None:
    """调用高德地理编码API获取坐标"""
    params = {
        "key": api_key,
        "address": address,
        "city": city,
        "output": "JSON"
    }
    
    try:
        resp = requests.get(AMAP_GEOCODE_URL, params=params, timeout=10)
        data = resp.json()
        
        if data.get("status") == "1" and data.get("geocodes"):
            geocode = data["geocodes"][0]
            location = geocode.get("location", "")
            if location:
                lng, lat = location.split(",")
                return {
                    "address": address,
                    "formatted_address": geocode.get("formatted_address", ""),
                    "lat": float(lat),
                    "lng": float(lng),
                    "level": geocode.get("level", ""),
                    "confidence": geocode.get("confidence", "")
                }
        else:
            print(f"  ⚠️ API返回错误: {data.get('info', '未知错误')}")
            return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("高德地图真实坐标获取工具")
        print("=" * 60)
        print("")
        print("使用方法:")
        print("  python fetch_real_coordinates.py <你的API_KEY>")
        print("")
        print("获取API Key步骤:")
        print("  1. 访问: https://console.amap.com/dev/key/app")
        print("  2. 登录/注册高德开放平台账号")
        print("  3. 创建新应用 → 添加 Key → 选择「Web服务」")
        print("  4. 复制 Key 运行本脚本")
        print("")
        print("示例:")
        print("  python fetch_real_coordinates.py abc123def456...")
        print("=" * 60)
        sys.exit(1)
    
    api_key = sys.argv[1]
    
    # 读取现有CSV文件
    input_csv = "qinan_simulated_traffic_csv_40nodes/Intersections.csv"
    output_csv = "qinan_simulated_traffic_csv_40nodes/Intersections_real.csv"
    
    intersections = []
    with open(input_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            intersections.append(row)
    
    print(f"\n{'='*60}")
    print(f"开始获取 {len(intersections)} 个路口的真实坐标...")
    print(f"{'='*60}\n")
    
    results = []
    success_count = 0
    
    for i, item in enumerate(intersections):
        intersection_id = item["intersection_id"]
        intersection_name = item["intersection_name"]
        
        # 构建搜索地址：路口名称 + 秦安县
        search_address = f"{intersection_name},秦安县"
        
        print(f"[{i+1:2d}/{len(intersections)}] {intersection_id} {intersection_name}")
        
        coord = get_coordinate(api_key, search_address, city="天水市")
        
        if coord:
            # 更新坐标
            item["lat"] = round(coord["lat"], 6)
            item["lng"] = round(coord["lng"], 6)
            
            print(f"  ✅ 成功: ({coord['lat']}, {coord['lng']})")
            print(f"     地址: {coord['formatted_address']}")
            success_count += 1
        else:
            print(f"  ❌ 失败: 保持原坐标 ({item['lat']}, {item['lng']})")
        
        results.append(item)
        
        # 避免请求过快（高德限制：50次/秒，我们保守一点）
        if i < len(intersections) - 1:
            time.sleep(0.15)
    
    # 写入新的CSV文件
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = results[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n{'='*60}")
    print(f"完成！成功获取 {success_count}/{len(intersections)} 个坐标")
    print(f"输出文件: {output_csv}")
    print(f"{'='*60}\n")
    
    # 显示部分结果对比
    print("坐标对比（前5个）:")
    print("-" * 70)
    print(f"{'ID':<8} {'路口名称':<20} {'原坐标':<25} {'新坐标':<25}")
    print("-" * 70)
    
    with open(input_csv, "r", encoding="utf-8-sig") as f:
        original = list(csv.DictReader(f))
    
    for i in range(min(5, len(results))):
        orig = original[i]
        new = results[i]
        old_coord = f"({orig['lat']}, {orig['lng']})"
        new_coord = f"({new['lat']}, {new['lng']})"
        changed = "✅ 已更新" if old_coord != new_coord else "⚠️ 未变"
        print(f"{new['intersection_id']:<8} {new['intersection_name']:<20} {old_coord:<25} {new_coord:<25} {changed}")


if __name__ == "__main__":
    main()
