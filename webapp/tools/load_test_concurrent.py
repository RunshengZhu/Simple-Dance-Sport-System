#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R48 并发多角色压测：13+裁判同时打分 + 检录员同时操作 + 大量观众并发浏览 + 管理员监控。

模拟真实赛事场景：全部角色同时活跃，而非串行测试。
用法：python3 webapp/tools/load_test_concurrent.py [BASE]
前置：build_mega_data.py 已就绪。
"""
import asyncio
import json
import random
import statistics
import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8303").rstrip("/")
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 60  # 秒
ids = json.load(open("/tmp/mega_ids.json"))
CID = ids["cid"]
CEIDS = ids["ceids"]

results = {}   # {role: [(latency_ms, status_code)]}
errors = []


def rec(role, dt, status):
    results.setdefault(role, []).append((dt, status))


def pct(vals, p):
    if not vals:
        return 0
    return sorted(vals)[min(len(vals) - 1, int(p / 100 * (len(vals) - 1)))]


async def judge_worker(client, jid, ceid, dance, stop_at):
    """裁判：循环 打分→提交→重提交"""
    role = f"judge_{jid}"
    # 登录
    r = await client.post(BASE + "/api/login", json={"role": "judge", "judge_id": jid})
    vals = {str(n): round(6 + random.random() * 3.5, 1) for n in range(1001, 1009)}
    from urllib.parse import quote
    url = BASE + f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet"
    while time.time() < stop_at:
        t0 = time.time()
        r = await client.put(url, json={"values": vals})
        rec(role, (time.time() - t0) * 1000, r.status_code)
        if r.status_code >= 400:
            errors.append(f"{role}: {r.status_code}")
        await asyncio.sleep(random.uniform(0.5, 2.0))


async def checkin_worker(client, ceid, stop_at):
    """检录员：循环 批量检录/撤销"""
    await client.post(BASE + "/api/login", json={
        "role": "marshal", "username": "marshal", "password": "marshal123"})
    nums = [str(n) for n in range(1001, 1013)]
    state = True
    while time.time() < stop_at:
        t0 = time.time()
        r = await client.post(BASE + f"/api/competition-events/{ceid}/checkin",
                              json={"numbers": nums[:6], "state": state})
        rec("checkin", (time.time() - t0) * 1000, r.status_code)
        state = not state
        await asyncio.sleep(random.uniform(0.3, 1.0))


async def spectator_worker(client, stop_at, vid):
    """观众：轮换浏览三个公开页 + 完整资源加载"""
    pages = ["/public/results", "/public/schedule", "/public/team-standings"]
    i = random.randrange(3)
    role = f"spectator_{vid}"
    while time.time() < stop_at:
        i = (i + 1) % 3
        t0 = time.time()
        r = await client.get(BASE + pages[i])
        dt = (time.time() - t0) * 1000
        rec(f"spectator GET", dt, r.status_code)
        # 模拟静态资源加载
        for asset in ["/static/style.css", "/static/app.js"]:
            t1 = time.time()
            ar = await client.get(BASE + asset)
            rec("static asset", (time.time() - t1) * 1000, ar.status_code)
        if r.status_code >= 400:
            errors.append(f"spectator: {r.status_code} on {pages[i]}")
        await asyncio.sleep(random.uniform(0.3, 1.5))


async def admin_worker(client, stop_at):
    """管理员：监控控制台+查看结果+查审计"""
    await client.post(BASE + "/api/login", json={"role": "admin", "password": "admin123"})
    while time.time() < stop_at:
        t0 = time.time()
        paths = [f"/events/{CID}/console/{CEIDS['D1']}",
                 f"/events/{CID}/results",
                 "/api/audit?limit=50"]
        for p in paths:
            r = await client.get(BASE + p)
            rec("admin GET", (time.time() - t0) * 1000, r.status_code)
        await asyncio.sleep(2.0)


async def sse_worker(client, ceid, stop_at):
    """SSE 长连接保持"""
    role = "sse"
    try:
        async with client.stream("GET", BASE + f"/api/events/{ceid}/stream",
                                 timeout=httpx.Timeout(10, read=300)) as r:
            rec(role, 0, r.status_code)
            async for chunk in r.aiter_bytes():
                if time.time() >= stop_at:
                    break
    except Exception as e:
        rec(role, 0, 599)


async def main():
    print(f"=== 并发多角色压测 ===")
    print(f"BASE: {BASE}")
    print(f"时长: {DURATION}s")
    print(f"角色: 13裁判 + 2检录员 + 50观众 + 1管理员 + 5条SSE长连接")
    print()

    limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)
    timeout = httpx.Timeout(30.0)

    t_start = time.time()
    stop_at = t_start + DURATION

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # 初始数据准备：确保 D1 评分制场次可用
        await client.post(BASE + "/api/login", json={"role": "admin", "password": "admin123"})

        # 并发启动所有角色
        tasks = []

        # 13 裁判同时打分（轮换 3 个场次）
        scoring_ceids = [CEIDS.get("D1"), CEIDS.get("S1"), CEIDS.get("P1F")]
        for i in range(13):
            jid = f"J{(i % 13) + 1}"
            ceid = scoring_ceids[i % 3]
            tasks.append(asyncio.create_task(
                judge_worker(client, jid, ceid, "集体舞", stop_at)))

        # 2 检录员并发操作
        for i in range(2):
            ceid = list(CEIDS.values())[i]
            tasks.append(asyncio.create_task(
                checkin_worker(client, ceid, stop_at)))

        # 50 观众并发浏览
        for i in range(50):
            delay = random.uniform(0, 3)
            tasks.append(asyncio.create_task(
                spectator_worker(client, stop_at - random.uniform(0, 5), f"spec_{i}")))

        # 1 管理员
        tasks.append(asyncio.create_task(admin_worker(client, stop_at)))

        # 5 条 SSE 长连接
        for _ in range(5):
            tasks.append(asyncio.create_task(sse_worker(client, CID, stop_at)))

        await asyncio.gather(*tasks, return_exceptions=True)

    duration = time.time() - t_start

    # ===== 汇报 =====
    print(f"\n{'角色':<30}{'次数':>8}{'错误':>6}{'RPS':>8}{'P50ms':>9}{'P95ms':>9}{'P99ms':>9}{'avg':>8}")
    total_reqs = 0
    total_errs = 0
    for role in sorted(results.keys()):
        rows = results[role]
        dts = sorted(r[0] for r in rows)
        errs = sum(1 for r in rows if r[1] >= 400)
        total_reqs += len(rows)
        total_errs += errs
        print(f"{role:<30}{len(rows):>8}{errs:>6}{len(rows)/duration:>8.1f}"
              f"{pct(dts,50):>9.0f}{pct(dts,95):>9.0f}{pct(dts,99):>9.0f}"
              f"{statistics.mean(dts)*1000:>8.0f}")
    print(f"{'TOTAL':<30}{total_reqs:>8}{total_errs:>6}{total_reqs/duration:>8.1f}")
    print(f"错误率: {total_errs/max(1,total_reqs)*100:.2f}%")


if __name__ == "__main__":
    import httpx  # noqa
    DURATION = 60
    if len(sys.argv) > 2:
        DURATION = int(sys.argv[2])
    asyncio.run(main())
