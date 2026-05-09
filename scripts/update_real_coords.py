"""
解析用户提供的真实坐标并更新CSV文件
"""

import csv
import re

# 用户提供的原始数据（从消息中提取）
raw_data = """
QNA001成纪大道-环城西路105.668917,34.851686 
 QNA002成纪大道-解放南路105.674624,34.860499 
 QNA003 成纪大道-兴国路  105.671033,34.860521 
 QNA004 成纪大道-蔡林路  105.667865,34.860475 
 QNA005 成纪大道-北坛街  105.671869,34.862083 
 QNA006成纪大道-解放北路105.674625,34.860581 
 QNA007 成纪大道-应乾路  105.670412,34.860506 
 QNA008 成纪大道-街泉街  105.669962,34.874061 
 QNA009 太白街-环城西路  105.668917,34.851686 
 QNA010 太白街-解放南路  105.674657,34.858423 
 QNA011 太白街-兴国路    105.671072,34.858758 
 QNA012 太白街-蔡林路    105.6679,34.861828 
 QNA013 太白街-北坛街    105.672153,34.863419 
 QNA014 太白街-解放北路  105.674375,34.857375 
 QNA015 太白街-应乾路    105.676229,34.877851 
 QNA016 太白街-街泉街    105.669962,34.874061 
 QNA017 新华街-环城西路  105.668917,34.851686 
 QNA018 新华街-解放南路  105.674618,34.855849 
 QNA019 新华街-兴国路    105.671072,34.858758 
 QNA020 新华街-蔡林路    105.6679,34.861828 
 QNA021 新华街-北坛街    105.672153,34.863419 
 QNA022 新华街-解放北路  105.673971,34.8701 
 QNA023 新华街-应乾路    105.676229,34.877851 
 QNA024 新华街-街泉街    105.669962,34.874061 
 QNA025 人民街-环城西路  105.668917,34.851686 
 QNA026 人民街-解放南路  105.674618,34.855849 
 QNA027 人民街-兴国路    105.671072,34.858758 
 QNA028 人民街-蔡林路    105.6679,34.861828 
 QNA029 人民街-北坛街    105.674504,34.863471 
 QNA030 人民街-解放北路  105.674504,34.863471 
 QNA031 人民街-应乾路    105.672317,34.855835 
 QNA032 人民街-街泉街    105.669962,34.874061 
 QNA033 映南路-环城西路  105.668917,34.851686 
 QNA034 映南路-解放南路  105.674618,34.855849 
 QNA035 映南路-兴国路    105.67169,34.866517 
 QNA036 映南路-蔡林路    105.67176,34.864268 
 QNA037 映南路-北坛街    105.671445,34.863381 
 QNA038 映南路-解放北路  105.678275,34.864125 
 QNA039 映南路-应乾路    105.676229,34.877851 
 QNA040 映南路-街泉街    105.669962,34.874061
"""

def parse_coordinates(raw_text):
    """解析原始文本，提取ID和坐标"""
    coords = {}
    
    # 匹配模式：QNAxxx + 名称 + lng,lat
    pattern = r'(QNA\d{3})[^\d]*?(\d+\.?\d*),(\d+\.?\d*)'
    
    matches = re.findall(pattern, raw_text)
    
    for match in matches:
        intersection_id = match[0]
        lng = float(match[1])
        lat = float(match[2])
        coords[intersection_id] = {"lng": lng, "lat": lat}
        print(f"[OK] {intersection_id}: ({lat}, {lng})")
    
    return coords


def update_csv(input_file, output_file, new_coords):
    """更新CSV文件中的坐标"""
    rows = []
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            intersection_id = row['intersection_id']
            
            if intersection_id in new_coords:
                old_lat = row['lat']
                old_lng = row['lng']
                new_coord = new_coords[intersection_id]
                
                row['lat'] = str(new_coord['lat'])
                row['lng'] = str(new_coord['lng'])
                
                status = "[UPDATED]" if changed else "[SAME]"
                print(f"{status} {intersection_id}: ({old_lat}, {old_lng}) -> ({row['lat']}, {row['lng']})")
            
            rows.append(row)
    
    # 写入新文件
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n[OK] Updated file: {output_file}")
    print(f"   共处理 {len(rows)} 条记录")


if __name__ == "__main__":
    print("=" * 70)
    print("解析真实坐标数据")
    print("=" * 70 + "\n")
    
    # 解析坐标
    new_coords = parse_coordinates(raw_data)
    
    print(f"\n共解析出 {len(new_coords)} 个坐标\n")
    
    # 更新CSV
    input_csv = "qinan_simulated_traffic_csv_40nodes/Intersections.csv"
    output_csv = "qinan_simulated_traffic_csv_40nodes/Intersections.csv"  # 直接覆盖原文件
    
    print("=" * 70)
    print("更新 CSV 文件")
    print("=" * 70 + "\n")
    
    update_csv(input_csv, output_csv, new_coords)
