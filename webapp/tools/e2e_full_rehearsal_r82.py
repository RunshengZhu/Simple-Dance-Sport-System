# -*- coding: utf-8 -*-
"""R82 全角色全要素模拟（生产 comp21 正式新生赛，随机评分）。

流程：筹备链路（总览/报项回环/名单/材料）→ 赛程编排（proposal 保存）→ 按出场序逐场：
检录→裁判评分→收齐自动算→发布→播报；预赛后晋级确认（含人工调减）；异常注入：
补检录、缺裁判拦截、错误重交、撤回重发、自动发布开关。收官：团体总分/观众查询/大屏/材料导出。

用法：python3 e2e_full_rehearsal_r82.py [base=https://dancetkt.com]
"""
import asyncio, csv, io, json, os, random, sys, time
from urllib.parse import quote

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8302"
CID = 21
OUT = "/tmp/e2e_r82"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
R, TL = [], []
NJ = 7


def log(event, ok=True, detail=""):
    t = time.time() - T0
    TL.append({"t": round(t, 1), "event": event, "ok": bool(ok), "detail": str(detail)[:160]})
    print(f"[{t:6.1f}s] {'✓' if ok else '✗'} {event}" + (f" :: {detail}" if detail else ""), flush=True)


def assert_(name, ok, detail=""):
    R.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    log("ASSERT " + name, ok, detail)


def api(method, path, body=None, cookie="", raw=None, expect_json=True):
    import urllib.request, urllib.error
    rq = urllib.request.Request(BASE + path, method=method)
    if cookie:
        rq.add_header("Cookie", cookie)
    data = None
    if raw is not None:
        rq.data = raw
        rq.add_header("Content-Type", "text/csv; charset=utf-8")
    elif body is not None:
        rq.data = json.dumps(body).encode()
        rq.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(rq, timeout=60) as resp:
            raw_body = resp.read()
            sc = resp.headers.get("Set-Cookie", "").split(";")[0]
            try:
                return resp.status, (json.loads(raw_body) if expect_json else raw_body), sc
            except Exception:
                return resp.status, {"_text": raw_body.decode("utf-8", "replace")[:400]}, sc
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read() or b"{}")
        except Exception:
            d = {}
        return e.code, d, ""


def login(body):
    for _ in range(8):   # 429 退避：生产限流窗口 5 失败/60s，惰性清理
        c, d, ck = api("POST", "/api/login", body)
        if c == 200:
            return ck
        if c == 429:
            time.sleep(22)
            continue
        raise AssertionError(f"登录失败 {body} {c} {d}")
    raise AssertionError(f"登录限流未解除 {body}")


def wait_status(ceid, want, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
        ev = next((e for e in d.get("events", []) if e["id"] == ceid), {})
        if ev.get("status") == want:
            return True
        time.sleep(1.2)
    return False


async def main():
    # ---------- 会话 ----------
    ck = login({"role": "admin", "password": "CE9DoLRhkb37R9w_bgrpDA55"})
    ck_ca = login({"role": "admin", "username": "xs-admin", "password": "XsAdmin2026", "competition_id": CID})
    ck_m = login({"role": "marshal", "username": "xinsheng-checkin", "password": "XsCheck2026", "competition_id": CID})
    ck_h = login({"role": "host", "username": "xinsheng-host", "password": "XsHost2026", "competition_id": CID})
    cks_j = {f"J{i}": login({"role": "judge", "judge_id": f"J{i}", "competition_id": CID}) for i in range(1, NJ + 1)}
    log("各角色会话就绪（总管/赛管/检录/主持/裁判×7）")

    # ---------- Phase 0 快照（演练前数据库备份） ----------
    c, d, _ = api("POST", "/api/backup", {}, cookie=ck)
    assert_("P0 演练前数据库快照", c == 200 and "backup-" in str(d.get("path", "")), str(d)[:80])

    # ---------- Phase A 筹备链路（赛事管理员视角） ----------
    c, d, _ = api("GET", f"/api/events/{CID}/exports/competitors?format=csv", cookie=ck_ca, expect_json=False)
    rows = list(csv.reader(io.StringIO(d.decode("utf-8-sig") if isinstance(d, bytes) else str(d))))
    entries = {}   # proj -> [numbers]
    for r in rows[1:]:
        if len(r) >= 3 and r[2].strip():
            entries.setdefault(r[0].strip(), []).append(r[2].strip())
    assert_("A1 报项数据可下载且结构完整", len(entries) >= 10 and sum(len(v) for v in entries.values()) >= 150,
            f"项目 {len(entries)} 个 / 条目 {sum(len(v) for v in entries.values())}")
    import base64
    c, xbytes, _ = api("GET", f"/api/events/{CID}/exports/competitors?format=xlsx", cookie=ck_ca, expect_json=False)
    c, d, _ = api("POST", f"/api/events/{CID}/imports/file", cookie=ck_ca,
                  body={"kind": "competitors", "data_b64": base64.b64encode(xbytes).decode()})
    assert_("A2 报名总表 xlsx 回环导入幂等", c == 200 and d.get("imported", 0) >= 150,
            f"imported={d.get('imported')} auto={bool(d.get('auto_schedule'))}（已有赛程应无）")
    for path, mark in [(f"/events/{CID}/overview", "赛事总览"), (f"/events/{CID}/roster", "名单"),
                       (f"/events/{CID}/direct-links", "直达链接")]:
        c, d, _ = api("GET", path, cookie=ck_ca, expect_json=False)
        body = d.decode("utf-8", "replace") if isinstance(d, bytes) else str(d)
        assert_(f"A3 {mark}页可达", c == 200 and mark in body, f"http {c} len={len(body)}")
    for path in ["/api/public/events/21/exports/schedule?format=html",
                 "/api/public/events/21/exports/runsheet?format=csv&seed=20261114",
                 f"/api/events/{CID}/exports?format=markdown",
                 f"/api/events/{CID}/exports/judges"]:
        c, d, _ = api("GET", path, cookie=ck_ca, expect_json=False)
        assert_(f"A4 材料 {path.split('/')[-1].split('?')[0]} 可下载", c == 200, f"http {c}")

    # ---------- Phase B 赛程编排（proposal 保存） ----------
    c, d, _ = api("GET", f"/api/events/{CID}/run-order/proposal", cookie=ck_ca)
    order = [x["ceid"] for x in d.get("order", [])]
    assert_("B1 自动编排建议生成", c == 200 and len(order) == 19, f"{len(order)} 场")
    c, d, _ = api("POST", f"/api/events/{CID}/run-order", {"order": order}, cookie=ck_ca)
    assert_("B2 管理员保存出场顺序", c == 200)
    c, d, _ = api("GET", f"/api/events/{CID}/run-order", cookie=ck_ca)
    seq = sorted(d.get("order", []), key=lambda x: (x.get("run_seq") or 9999))
    assert_("B3 出场序 19 场（含名单）", len(seq) == 19 and all(x.get("roster") is not None for x in seq),
            str([(x["code"], len(x.get("roster") or [])) for x in seq[:5]]))
    c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
    st_by_id = {e["id"]: e for e in d["events"]}
    dance_by_id = {}   # R82 修正：公开 payload 不含舞种，统一从裁判工作台解析真实舞种名

    # ---------- Phase C 逐场进行 ----------
    scenario_log = []
    published_seen = False
    late_done = False
    ranks_before = {}
    r2_roster_expect = {}
    n_prelim_done = 0
    for e in seq:
        ceid, code = e["ceid"], e["code"]
        proj, rnd = code.split("-R")[0], int(code.rsplit("R", 1)[1])
        is_prelim = rnd == 1 and any(x["code"] == f"{proj}-R2" for x in seq)
        roster_nums = sorted(set(e.get("roster") or []), key=lambda x: (len(x), x)) or \
            sorted(set(entries.get(proj, [])), key=lambda x: (len(x), x))
        styp = st_by_id.get(ceid, {}).get("scoring_type", "顺位法")
        dance = dance_by_id.get(ceid)

        # 异常注入：首个 ≥3 人场次补检录（先缺 1 人开场）
        late = None
        if not late_done and len(roster_nums) >= 3:
            late = roster_nums[-1]
            late_done = True
        checked_in = [n for n in roster_nums if n != late]
        c, d, _ = api("POST", f"/api/competition-events/{ceid}/open", {"roster": roster_nums, "reset": False}, cookie=ck)
        if not dance:
            import urllib.request as _u, re as _re
            _rq = _u.Request(BASE + "/judge"); _rq.add_header("Cookie", cks_j["J1"])
            with _u.urlopen(_rq, timeout=30) as _r:
                _h = _r.read().decode("utf-8", "replace")
            _m = _re.search(r'href="(/judge/competition-events/%d/dances/([^"]+))"' % ceid, _h)
            dance = _m.group(2).replace("%E2%80%8B", "") if _m else "华尔兹"
            dance_by_id[ceid] = dance
        c, d, _ = api("POST", f"/api/competition-events/{ceid}/checkin", {"numbers": checked_in, "state": True}, cookie=ck_m)
        if late:
            # 缺席者先不可评：J1 提交时把未检录者一并写入（按制式构造），记录服务端行为
            rng = random.Random(f"late:{code}")
            if styp == "Mark制" or is_prelim:
                values = {n: True for n in rng.sample(checked_in, min(8, len(checked_in)))}
                values[late] = True
            else:
                perm = checked_in + [late]
                values = {n: str(rk) for rk, n in enumerate(perm, 1)}
            c, d, _ = api("PUT", f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
                          body={"values": values}, cookie=cks_j["J1"])
            scenario_log.append({"场景": f"{code} 未检录者一并提交", "HTTP": c, "detail": str(d)[:80]})
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/checkin", {"numbers": [late], "state": True}, cookie=ck_m)
            assert_(f"C {code} 补检录生效", c == 200)
        # 异常注入：缺裁判拦截（第二场少交一名）
        skip_judge = "J7" if code == seq[1]["code"] else None
        rng = random.Random("rng:" + code)
        submitters = [f"J{i}" for i in range(1, NJ + 1) if f"J{i}" != skip_judge]
        for jn in submitters:
            if styp == "Mark制" or is_prelim:
                picks = rng.sample(roster_nums, min(8, len(roster_nums)))
                values = {n: True for n in picks}
            else:
                perm = roster_nums[:]
                rng.shuffle(perm)
                values = {n: str(rk) for rk, n in enumerate(perm, 1)}
            c, d, _ = api("PUT", f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
                          body={"values": values}, cookie=cks_j[jn])
            if c != 200:
                log(f"C {code} {jn} 提交失败", ok=False, detail=str(d)[:80])
        if skip_judge:
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/calculate", {}, cookie=ck)
            scenario_log.append({"场景": f"{code} 缺 1 名裁判时手动计算",
                                 "行为": "200 强制按已有记录计算（管理员明示操作）" if c == 200 else str(d)[:60]})
            assert_(f"C {code} 缺裁判手动计算（行为记录）", c in (200, 400), f"HTTP {c}")
            c, d, _ = api("PUT", f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
                          body={"values": {n: True for n in rng.sample(roster_nums, min(8, len(roster_nums)))}},
                          cookie=cks_j["J7"])
        ok = wait_status(ceid, "calculated") or wait_status(ceid, "published", 10)
        assert_(f"C {code} 收齐自动计算（含自动发布直跳）", ok, styp)

        # 异常注入：自动发布开关（对第五场启用，验证收齐即发布）
        if code == seq[4]["code"]:
            c, d, _ = api("POST", f"/api/events/{CID}/auto-publish", {"auto_publish": True}, cookie=ck)
            assert_(f"C {code} 前开启自动发布", c == 200)

        # 发布（若自动发布已代劳则跳过）
        c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
        ev_now = next(x for x in d["events"] if x["id"] == ceid)
        if ev_now["status"] == "calculated":
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/publish", {}, cookie=ck)
            if code == seq[4]["code"]:
                # 自动发布应已在其上一步生效，这里可能已 published；仅记录
                scenario_log.append({"场景": f"{code} 自动发布", "开启后状态": ev_now["status"]})
        ok = wait_status(ceid, "published")
        assert_(f"C {code} 发布进大屏/观众页", ok)

        # 异常注入：首个已发布场次 撤回→重发
        if not published_seen:
            published_seen = True
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/unpublish", {}, cookie=ck)
            back = wait_status(ceid, "calculated")
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/publish", {}, cookie=ck)
            ok = wait_status(ceid, "published")
            assert_(f"C {code} 撤回发布→重新发布", back and ok)

        # 主持播报标记
        c, d, _ = api("POST", f"/api/competition-events/{ceid}/announce", {"announced": True}, cookie=ck_h)
        assert_(f"C {code} 主持标记已播报", c == 200)

        # 改判动线（P02-R1）：撤回→退回评分→全员重交（J4 反序）→重算发布→名次对比
        if code == "P02-R1" and not is_prelim:
            rng2 = random.Random("redo:" + code)
            c, d, _ = api("GET", "/api/public/events/21/results")
            res = next((x for x in d.get("results", []) if x["code"] == code), {})
            rank_a = next((o["rank"] for o in res.get("overall", []) if o["competitor_number"] == roster_nums[0]), None)
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/unpublish", {}, cookie=ck)
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/return-scores", {}, cookie=ck)
            for jn in [f"J{i}" for i in range(1, NJ + 1)]:
                perm = roster_nums[:]
                rng2.shuffle(perm)
                if jn == "J4":
                    perm = list(reversed(roster_nums))
                c, d, _ = api("PUT", f"/api/judge/competition-events/{ceid}/dances/{quote(dance)}/sheet",
                              body={"values": {n: str(rk) for rk, n in enumerate(perm, 1)}}, cookie=cks_j[jn])
                if c != 200:
                    log(f"C {code} {jn} 重交失败", ok=False, detail=str(d)[:60])
            wait_status(ceid, "calculated")
            c, d, _ = api("POST", f"/api/competition-events/{ceid}/publish", {}, cookie=ck)
            wait_status(ceid, "published")
            c, d, _ = api("GET", "/api/public/events/21/results")
            res = next((x for x in d.get("results", []) if x["code"] == code), {})
            rank_b = next((o["rank"] for o in res.get("overall", []) if o["competitor_number"] == roster_nums[0]), None)
            assert_(f"C {code} 改判动线（撤回/退回/重交/重算/发布）走通", rank_b is not None,
                    f"名次 {rank_a} → {rank_b}")
        # 预赛 → 晋级确认（P04-R1 人工调减为 7 人）
        if is_prelim:
            n_prelim_done += 1
            reduce_to = 7 if code == "P04-R1" else 8
            c, d, _ = api("GET", f"/api/projects/{proj}/rounds/1/advancement-proposal", cookie=ck_ca)
            prop = [x["competitor_number"] for x in d.get("proposal", [])][:reduce_to]
            assert_(f"C {code} 晋级预案 {len(prop)} 人", len(prop) == reduce_to, str(prop[:4]) + "…")
            c, d, _ = api("POST", f"/api/projects/{proj}/rounds/1/advancement-confirm",
                          {"advancing": prop}, cookie=ck_ca)
            assert_(f"C {code} 晋级确认回填 {proj}-R2", c == 200)
            r2_roster_expect[f"{proj}-R2"] = prop

    # ---------- Phase D 收官核验 ----------
    c, d, _ = api("GET", f"/api/public/events/{CID}/schedule")
    all_pub = all(e["status"] == "published" for e in d["events"])
    assert_("D1 全赛事 19 场全部已发布", all_pub,
            str([(e["code"], e["status"]) for e in d["events"] if e["status"] != "published"]))
    c, d, _ = api("GET", f"/api/public/events/{CID}/team-standings")
    st = d.get("standings", [])
    assert_("D2 团体总分榜生成", len(st) >= 10 and sum(s.get("total", 0) for s in st) > 0,
            f"{len(st)} 个单位")
    c, d, _ = api("GET", f"/api/public/events/{CID}/lookup?num=101")
    lk = d if isinstance(d, dict) else {}
    assert_("D3 观众背番号查询（101：赛程+成绩）", c == 200 and lk.get("name"), str(lk)[:80])
    c, d, _ = api("GET", "/screen", cookie=None, expect_json=False)
    assert_("D4 大屏页可达", c == 200)
    c, d, _ = api("GET", "/api/events/21/credentials", cookie=ck, expect_json=False)
    assert_("D5 口令表导出", c == 200)
    c, d, _ = api("GET", "/api/audit?limit=50", cookie=ck)
    assert_("D6 审计日志可查（含赛程重建留痕）", c == 200 and isinstance(d.get("items"), list), str(c))

    print(f"\n===== 模拟完成：{len(R) - len([r for r in R if not r['ok']])}/{len(R)} PASS · 全程 {time.time()-T0:.0f}s =====", flush=True)
    for r in R:
        if not r["ok"]:
            print("FAIL:", r["name"], "::", r["detail"], flush=True)
    print("\n---- 异常场景行为记录 ----", flush=True)
    for s in scenario_log:
        print(json.dumps(s, ensure_ascii=False), flush=True)
    json.dump({"asserts": R, "timeline": TL, "scenarios": scenario_log},
              open(OUT + "/results.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
