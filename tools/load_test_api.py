#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R41 API 压测器（httpx asyncio，单进程轻量，压测机零额外负担）。

场景：
  A 观众读    —— 轮换 GET /public/results /public/schedule /public/team-standings
  B 裁判写    —— N 裁判会话循环提交 F1 评分制 sheet（8 人随机分值）
  C 检录风暴  —— marshal 会话对 W1A-D 各组批量检录/撤销循环
  D 混合峰值  —— A(50) + B(13) + C(20) 同时
  E SSE 保持  —— N 路长连接挂 duration，统计建立成功率与首事件延迟
用法：
  python3 tools/load_test_api.py --scenario A --vus 50 --duration 90 [--base URL] [--ids /tmp/load_ids.json]
指标：分端点 count/err/p50/p95/p99/avg/rps + 总 RPS；错误率>30% 连续10s 自动熔断。
"""
import argparse
import asyncio
import json
import random
import statistics
import sys
import time

import httpx

sys.path.insert(0, __file__.rsplit("/", 1)[0])


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    i = min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1))))
    return sorted_vals[i]


class Stats:
    def __init__(self):
        self.data = {}   # key -> list[(t0, dt, status)]

    def add(self, key, dt, status):
        self.data.setdefault(key, []).append((time.time(), dt, status))

    def report(self, duration):
        print(f"\n{'端点':<46}{'次数':>7}{'错误':>6}{'RPS':>8}{'P50ms':>9}{'P95ms':>9}{'P99ms':>9}{'avg':>8}")
        total = 0
        for key in sorted(self.data):
            rows = self.data[key]
            dts = sorted(r[1] for r in rows)
            errs = sum(1 for r in rows if r[2] >= 400)
            total += len(rows)
            print(f"{key:<46}{len(rows):>7}{errs:>6}{len(rows)/duration:>8.1f}"
                  f"{pct(dts,50)*1000:>9.0f}{pct(dts,95)*1000:>9.0f}{pct(dts,99)*1000:>9.0f}"
                  f"{statistics.mean(dts)*1000:>8.0f}")
        print(f"{'TOTAL':<46}{total:>7}{total/duration:>8.1f} rps")


async def vu_reader(client, base, stats, stop_at, bucket):
    """场景 A：观众轮换读三页。"""
    paths = ["/public/results", "/public/schedule", "/public/team-standings"]
    i = random.randrange(3)
    while time.time() < stop_at:
        i = (i + 1) % 3
        t0 = time.time()
        try:
            r = await client.get(base + paths[i])
            stats.add("A " + paths[i], time.time() - t0, r.status_code)
            bucket.append(1 if r.status_code >= 500 else 0)
        except Exception:
            stats.add("A " + paths[i] + " (exc)", time.time() - t0, 599)
            bucket.append(1)
        await asyncio.sleep(1.5)


async def vu_judge(client, base, ids, jid, stats, stop_at, bucket):
    """场景 B：裁判循环提交 F1 sheet。"""
    values = {str(n): round(random.uniform(6.0, 10.0), 1) for n in range(1001, 1009)}
    await client.post(base + "/api/login", json={"role": "judge", "judge_id": jid})
    while time.time() < stop_at:
        t0 = time.time()
        try:
            r = await client.put(
                base + f"/api/judge/competition-events/{ids['F1']}/dances/%E9%9B%86%E4%BD%93%E8%88%9E/sheet",
                json={"values": values})
            stats.add(f"B judge {jid} PUT", time.time() - t0, r.status_code)
            bucket.append(1 if r.status_code >= 500 else 0)
        except Exception:
            stats.add(f"B judge {jid} PUT (exc)", time.time() - t0, 599)
            bucket.append(1)
        await asyncio.sleep(2.0)


async def vu_checkin(client, base, ids, group, stats, stop_at, bucket):
    """场景 C：marshal 循环批量检录/撤销（组内 12 人）。"""
    await client.post(base + "/api/login", json={"role": "marshal", "username": "marshal",
                                                 "password": "marshal123"})
    nums = [str(n) for n in range(group[0], group[1] + 1)]
    state = True
    ceid = ids[group[2]]
    while time.time() < stop_at:
        t0 = time.time()
        try:
            r = await client.post(base + f"/api/competition-events/{ceid}/checkin",
                                  json={"numbers": nums, "state": state})
            stats.add(f"C checkin {group[2]} {'on' if state else 'off'}", time.time() - t0, r.status_code)
            bucket.append(1 if r.status_code >= 500 else 0)
            state = not state
        except Exception:
            stats.add(f"C checkin {group[2]} (exc)", time.time() - t0, 599)
            bucket.append(1)
        await asyncio.sleep(1.2)


async def sse_client(client, base, cid, stats, stop_at):
    """场景 E：单路 SSE 长连接。"""
    t0 = time.time()
    first_at = None
    bytes_read = 0
    try:
        async with client.stream("GET", base + f"/api/events/{cid}/stream", timeout=60) as r:
            ok = r.status_code == 200
            async for chunk in r.aiter_bytes():
                bytes_read += len(chunk)
                if first_at is None:
                    first_at = time.time() - t0
                if time.time() >= stop_at:
                    break
        stats.add(f"E sse first-event={first_at and round(first_at,2)}s bytes={bytes_read}",
                  time.time() - t0, 200 if ok else r.status_code)
        return ok
    except Exception as e:
        stats.add(f"E sse exc:{type(e).__name__}", time.time() - t0, 599)
        return False


async def circuit_breaker(bucket, stop_event):
    """滑窗熔断：10s 内错误率 >30% 持续触发。"""
    while not stop_event.is_set():
        await asyncio.sleep(2)
        recent = bucket[-200:]
        if len(recent) >= 50 and sum(recent) / len(recent) > 0.3:
            consecutive = sum(1 for x in recent[-30:] if x)
            if consecutive >= 25:
                stop_event.set()
                print("!! 熔断触发：错误率过高，中止本档")
                return


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, choices=["A", "B", "C", "D", "E"])
    ap.add_argument("--vus", type=int, default=50)
    ap.add_argument("--duration", type=int, default=90)
    ap.add_argument("--base", default="http://59.110.90.21:8321")
    ap.add_argument("--ids", default="/tmp/load_ids.json")
    ap.add_argument("--sse", type=int, default=300, help="E 场景连接数")
    args = ap.parse_args()
    ids = json.load(open(args.ids))
    cid = ids["cid"]
    stop_at = time.time() + args.duration
    stop_event = asyncio.Event()
    bucket = []
    breaker = asyncio.create_task(circuit_breaker(bucket, stop_event))
    limits = httpx.Limits(max_connections=args.vus + 320, max_keepalive_connections=200)
    timeout = httpx.Timeout(30.0)
    stats = Stats()
    t_start = time.time()

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        if args.scenario in ("A", "D"):
            n = 50 if args.scenario == "D" else args.vus
            await asyncio.gather(*[vu_reader(client, args.base, stats, stop_at, bucket)
                                   for _ in range(n)])
        elif args.scenario == "B":
            await asyncio.gather(*[vu_judge(client, args.base, ids, f"J{i}", stats, stop_at, bucket)
                                   for i in range(1, 14)])
        elif args.scenario == "C":
            groups = [("1009", "1020", "W1A"), ("1021", "1032", "W1B"),
                      ("1033", "1044", "W1C"), ("1045", "1056", "W1D")]
            n = min(args.vus, 20)
            await asyncio.gather(*[vu_checkin(client, args.base, ids, groups[i % 4], stats, stop_at, bucket)
                                   for i in range(n)])
        elif args.scenario == "D":
            groups = [("1009", "1020", "W1A"), ("1021", "1032", "W1B"),
                      ("1033", "1044", "W1C"), ("1045", "1056", "W1D")]
            await asyncio.gather(
                *[vu_reader(client, args.base, stats, stop_at, bucket) for _ in range(50)],
                *[vu_judge(client, args.base, ids, f"J{i}", stats, stop_at, bucket) for i in range(1, 14)],
                *[vu_checkin(client, args.base, ids, groups[i % 4], stats, stop_at, bucket) for i in range(20)],
            )
        elif args.scenario == "E":
            sem = asyncio.Semaphore(100)
            async def bounded(i):
                async with sem:
                    return await sse_client(client, args.base, cid, stats, stop_at)
            ok = await asyncio.gather(*[bounded(i) for i in range(args.sse)])
            print(f"SSE 建立成功 {sum(ok)}/{len(ok)}")

    duration = time.time() - t_start
    breaker.cancel()
    stats.report(duration)


if __name__ == "__main__":
    asyncio.run(main())
