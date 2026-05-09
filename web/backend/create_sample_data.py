#!/usr/bin/env python3
"""
创建示例赛事数据
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def register_user(username, password):
    """注册用户"""
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        params={"username": username, "password": password}
    )
    print(f"注册用户 {username}: {resp.status_code}")

def login(username, password):
    """登录获取token"""
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": username, "password": password}
    )
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None

def create_competition(token, name, date, location):
    """创建赛事"""
    resp = requests.post(
        f"{BASE_URL}/api/v1/competitions",
        json={"name": name, "date": date, "location": location},
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        return resp.json()
    return None

def create_event(token, competition_id, name, project_id, round_name, scoring_type, dances):
    """创建场次"""
    resp = requests.post(
        f"{BASE_URL}/api/v1/competitions/{competition_id}/events",
        json={
            "name": name,
            "project_id": project_id,
            "round": round_name,
            "scoring_type": scoring_type,
            "dances": dances,
            "advancement_count": 8
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        return resp.json()
    return None

def create_competitor(token, competition_id, number, name, unit, group_name, is_couple=False, partner_unit=None):
    """创建选手"""
    data = {
        "number": number,
        "name": name,
        "unit": unit,
        "group_name": group_name,
        "is_couple": is_couple
    }
    if is_couple and partner_unit:
        data["partner_unit"] = partner_unit

    resp = requests.post(
        f"{BASE_URL}/api/v1/competitions/{competition_id}/competitors",
        json=data,
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        return resp.json()
    return None

def main():
    print("=" * 50)
    print("创建示例赛事数据")
    print("=" * 50)

    # 1. 注册用户
    print("\n[1] 注册用户...")
    register_user("admin", "admin123")

    # 2. 登录
    print("\n[2] 登录...")
    token = login("admin", "admin123")
    if not token:
        print("登录失败!")
        return
    print(f"登录成功! Token: {token[:20]}...")

    # 3. 创建赛事
    print("\n[3] 创建赛事...")
    competition = create_competition(
        token,
        name="2024年校园体育舞蹈比赛",
        date="2024-06-15",
        location="体育馆"
    )
    if not competition:
        print("创建赛事失败!")
        return
    comp_id = competition["id"]
    print(f"赛事创建成功: {competition['name']} (ID: {comp_id})")

    # 4. 创建选手
    print("\n[4] 创建选手...")
    competitors = [
        ("001", "张三", "北京大学", "单人A组"),
        ("002", "李四", "北京大学", "单人A组"),
        ("003", "王五", "清华大学", "单人A组"),
        ("004", "赵六", "清华大学", "单人A组"),
        ("005", "钱七", "复旦大学", "单人A组"),
        ("006", "孙八", "复旦大学", "单人A组"),
        ("007", "周九", "交通大学", "单人B组"),
        ("008", "吴十", "交通大学", "单人B组"),
        ("009", "郑一", "浙江大学", "单人B组"),
        ("010", "王二", "浙江大学", "单人B组"),
    ]

    # 单人选手
    for num, name, unit, group in competitors:
        create_competitor(token, comp_id, num, name, unit, group)

    # 双人选手
    create_competitor(token, comp_id, "101", "陈A", "北京大学", "双人组", True, "清华大学")
    create_competitor(token, comp_id, "102", "刘B", "清华大学", "双人组", True, "北京大学")
    create_competitor(token, comp_id, "103", "林C", "复旦大学", "双人组", False)
    create_competitor(token, comp_id, "104", "杨D", "交通大学", "双人组", False)

    print(f"已创建 {len(competitors) + 4} 名选手")

    # 5. 创建场次
    print("\n[5] 创建场次...")
    events = [
        ("单人A组初赛", "001", "初赛", "mark", ["华尔兹", "探戈"]),
        ("单人A组决赛", "001", "决赛", "skating", ["华尔兹", "探戈"]),
        ("单人B组初赛", "002", "初赛", "mark", ["快步", "狐步"]),
        ("双人组决赛", "003", "决赛", "skating", ["华尔兹"]),
    ]

    created_events = []
    for name, project, round_name, scoring, dances in events:
        event = create_event(token, comp_id, name, project, round_name, scoring, dances)
        if event:
            created_events.append(event)
            print(f"  - {name}: {event['id']}")

    # 6. 设置奖项得分
    print("\n[6] 设置奖项得分...")
    default_points = {"1": 9, "2": 7, "3": 6, "4": 5, "5": 4, "6": 3, "7": 2, "8": 1}
    for event in created_events:
        resp = requests.put(
            f"{BASE_URL}/api/v1/events/{event['id']}/award-config",
            json={"event_id": event["id"], "points": default_points},
            headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 200:
            print(f"  - {event['name']}: 奖项得分已设置")

    # 7. 查看赛事列表
    print("\n[7] 验证数据...")
    resp = requests.get(
        f"{BASE_URL}/api/v1/competitions",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"  - 赛事总数: {data['total']}")

    resp = requests.get(
        f"{BASE_URL}/api/v1/competitions/{comp_id}/competitors",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"  - 选手总数: {len(data)}")

    resp = requests.get(
        f"{BASE_URL}/api/v1/competitions/{comp_id}/events",
        headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"  - 场次总数: {len(data)}")

    print("\n" + "=" * 50)
    print("示例数据创建完成!")
    print("=" * 50)
    print(f"\n登录信息:")
    print(f"  用户名: admin")
    print(f"  密码: admin123")
    print(f"\nAPI文档: http://localhost:8000/docs")
    print("=" * 50)

if __name__ == "__main__":
    main()
