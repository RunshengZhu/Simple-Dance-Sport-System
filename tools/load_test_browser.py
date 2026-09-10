#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R41 浏览器行为模拟压测（不发真实浏览器，模拟完整前端加载链路，压测机负担极小）。

单访客（VU）模型：
  1. GET 页面 HTML（计 DOMContentLoaded 等价的 HTML 完整时延）
  2. 解析 HTML 中的 /static/ 资源引用（css/js），模拟浏览器级联加载：
     首访全量 GET 200；重访带 If-None-Match/If-Modified-Since 期待 304（缓存命中）
  3. 建立 1 条 SSE 长连接保持（模拟页面 EventSource）
  4. 每 8s 重新 GET 当前页（模拟线上 softReload 周期），静态资源走缓存
  5. 驻留至 duration 结束，关闭 SSE
指标：HTML 时延、资源级联总时延（首访/重访）、304 命中率、SSE 建立率、每访客流量。
用法：python3 tools/load_test_browser.py --vus 50 --duration 90 [--ramp 5] [--page results]
"""
import argparse
import asyncio
import json
import re
import statistics
import sys
import time

import httpx

STATIC_RE = re.compile(r'(?:href|src)="(/static/[^"]+)"')


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    return sorted_vals[min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1))))]


class Agg:
    def __init__(self):
        self.html, self.res_first, self.res_cached, self.sse = [], [], [], []
        self.hit304 = [0, 0]   # [304 数, 资源请求数]
        self.bytes_total = 0
        self.errors = 0

    def report(self, duration, vus_done):
        print(f"\n== 浏览器模拟报告 == 完成访客 {vus_done}  错误 {self.errors}  总流量 {self.bytes_total/1e6:.1f} MB")
        for name, arr in (("HTML 完整时延", self.html), ("资源级联·首访", self.res_first),
                          ("资源级联·重访(304)", self.res_cached)):
            if arr:
                s = sorted(arr)
                print(f"{name:<18} n={len(arr):<5} P50={pct(s,50)*1000:.0f}ms "
                      f"P95={pct(s,95)*1000:.0f}ms avg={statistics.mean(arr)*1000:.0f}ms")
        if self.hit304[1]:
            print(f"静态缓存 304 命中率 {self.hit304[0]}/{self.hit304[1]} = {self.hit304[0]/self.hit304[1]*100:.0f}%")
        if self.sse:
            print(f"SSE 建立 {sum(self.sse)}/{len(self.sse)}")


async def visitor(client, base, cid, page_path, duration, ramp_delay, agg, stats):
    await asyncio.sleep(ramp_delay)   # 分批启动
    started = time.time()
    stop_at = started + duration
    cache = {}       # path -> (etag/last-modified headers)
    sse_ok = False
    try:
        while time.time() < stop_at:
            # 1) HTML
            t0 = time.time()
            r = await client.get(base + page_path)
            html_dt = time.time() - t0
            agg.html.append(html_dt)
            agg.bytes_total += len(r.content)
            if r.status_code != 200:
                agg.errors += 1
                await asyncio.sleep(3)
                continue
            # 2) 静态资源级联（首次全量，重访带缓存头）
            res_paths = sorted(set(STATIC_RE.findall(r.text)))
            t0 = time.time()
            is_first = not cache
            for rp in res_paths:
                headers = {}
                if rp in cache:
                    headers.update(cache[rp])
                rr = await client.get(base + rp, headers=headers)
                agg.hit304[1] += 1
                if rr.status_code == 304:
                    agg.hit304[0] += 1
                elif rr.status_code == 200:
                    etag, lm = rr.headers.get("etag"), rr.headers.get("last-modified")
                    cond = {}
                    if etag:
                        cond["if-none-match"] = etag
                    if lm:
                        cond["if-modified-since"] = lm
                    if "max-age" in rr.headers.get("cache-control", ""):
                        cond["fresh"] = True
                    cache[rp] = cond
                    agg.bytes_total += len(rr.content)
                else:
                    agg.errors += 1
            (agg.res_first if is_first else agg.res_cached).append(time.time() - t0)
            # 3) SSE 建立（读首个事件块验证）
            t1 = time.time()
            try:
                async with client.stream("GET", base + f"/api/events/{cid}/stream",
                                         timeout=httpx.Timeout(10, read=8)) as r:
                    chunks = []
                    async for chunk in r.aiter_bytes():
                        chunks.append(chunk)
                        break   # 首个事件块（state_sync 立即推送）即算建立
                    agg.sse.append(r.status_code == 200 and bool(chunks))
                    agg.bytes_total += len(chunks[0]) if chunks else 0
            except Exception:
                agg.sse.append(False)
            # 4) softReload 周期：8s 后整页重载（HTML + 静态资源带缓存头，与真实 reload 一致）
            while time.time() < stop_at:
                await asyncio.sleep(8)
                t2 = time.time()
                r2 = await client.get(base + page_path)
                agg.html.append(time.time() - t2)
                agg.bytes_total += len(r2.content)
                if r2.status_code != 200:
                    agg.errors += 1
                for rp in sorted(set(STATIC_RE.findall(r2.text))):
                    if cache.get(rp, {}).get("fresh"):
                        continue   # Cache-Control max-age 内浏览器不发请求（R41 缓存头优化）
                    headers = dict(cache.get(rp, {}))
                    rr = await client.get(base + rp, headers=headers)
                    agg.hit304[1] += 1
                    if rr.status_code == 304:
                        agg.hit304[0] += 1
                    elif rr.status_code == 200:
                        etag, lm = rr.headers.get("etag"), rr.headers.get("last-modified")
                        cond = {}
                        if etag:
                            cond["if-none-match"] = etag
                        if lm:
                            cond["if-modified-since"] = lm
                        cc = rr.headers.get("cache-control", "")
                        if "max-age" in cc:
                            cond["fresh"] = True   # max-age 内直接用本地缓存
                        cache[rp] = cond
                if time.time() >= stop_at:
                    break
    except Exception as e:
        agg.errors += 1
        stats.append(f"{type(e).__name__}: {e}"[:120])
    return sse_ok


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vus", type=int, default=50)
    ap.add_argument("--duration", type=int, default=90, help="每访客驻留秒数")
    ap.add_argument("--ramp", type=int, default=5, help="每秒启动的访客数")
    ap.add_argument("--page", default="results", choices=["results", "schedule", "standings"])
    ap.add_argument("--base", default="http://59.110.90.21:8321")
    ap.add_argument("--ids", default="/tmp/load_ids.json")
    args = ap.parse_args()
    cid = json.load(open(args.ids))["cid"]
    page_path = {"results": "/public/results", "schedule": "/public/schedule",
                 "standings": "/public/team-standings"}[args.page]
    agg = Agg()
    stats = []
    limits = httpx.Limits(max_connections=args.vus + 40, max_keepalive_connections=args.vus + 20)
    t0 = time.time()
    async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(30.0),
                                 follow_redirects=True) as client:
        tasks = []
        for i in range(args.vus):
            tasks.append(asyncio.create_task(
                visitor(client, args.base, cid, page_path, args.duration,
                        (i // args.ramp) * 1.0, agg, stats)))
        await asyncio.gather(*tasks)
    duration = time.time() - t0
    print(f"总时长 {duration:.0f}s，平均并发访客约 {args.vus * args.duration / duration:.0f}")
    agg.report(duration, args.vus)
    if stats:
        print("异常样本：", stats[:5])


if __name__ == "__main__":
    asyncio.run(main())
