import json, urllib.request, urllib.parse, http.cookiejar
BASE = "http://127.0.0.1:8321"
def sess(role, pw=None, jid=None):
    jar = http.cookiejar.CookieJar()
    body = {"role": role}
    if role == "judge": body["judge_id"] = jid
    else: body["password"] = pw
    r = urllib.request.Request(BASE+"/api/login", data=json.dumps(body).encode(), headers={"Content-Type":"application/json"}, method="POST")
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    code = op.open(r, timeout=8).status
    return {"op": op}
def call(s, method, path, body=None):
    r = urllib.request.Request(BASE+path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type":"application/json"}, method=method)
    try:
        return json.loads(s["op"].open(r, timeout=8).read())
    except urllib.error.HTTPError as e:
        try: return {"status": e.code, "detail": json.loads(e.read()).get("detail")}
        except Exception: return {"status": e.code}
admin = sess("admin", pw="admin123")
judges = {j: sess("judge", jid=j) for j in ("J1","J2","J3")}
m = sess("marshal", pw="marshal123")
CEID = 621
DANCE = urllib.parse.quote("华尔兹")
checked = [str(101+i) for i in range(8)]
for i, j in enumerate(("J1","J2","J3")):
    vals = {num: ((idx + i*2) % 8) + 1 for idx, num in enumerate(checked)}
    r = call(judges[j], "PUT", f"/api/judge/competition-events/{CEID}/dances/{DANCE}/sheet", {"values": vals})
    print(f"J{i+1} 提交:", "200" if isinstance(r, dict) and r.get("ok") else r)
r = call(admin, "POST", f"/api/competition-events/{CEID}/calculate", {})
res = call(admin, "GET", f"/api/competition-events/{CEID}/results")
nums = [x["competitor_number"] for x in res["data"]["overall_results"]]
print("基线名册:", nums, "| 缺席者未入结果:", all(n not in nums for n in ("109","110","116")))
r = call(m, "POST", f"/api/competition-events/{CEID}/checkin", {"numbers": ["109"], "state": True})
print("E1 计算后补检录109:", r)
r = call(m, "POST", f"/api/competition-events/{CEID}/checkin", {"numbers": ["101"], "state": False})
print("E2 评分中撤销101检录:", r)
r = call(admin, "POST", f"/api/competition-events/{CEID}/calculate", {})
res = call(admin, "GET", f"/api/competition-events/{CEID}/results")
nums = [x["competitor_number"] for x in res["data"]["overall_results"]]
det = call(admin, "GET", f"/api/competition-events/{CEID}/detail-scores")
j1_nums = sorted(set(x["number"] for x in det.get("records", []) if x["judge"] == "J1"))
print("E2 重算后名册:", nums)
print("E2 101已撤销但仍在结果:", "101" in nums, "| J1 记录仍含101:", "101" in j1_nums)
r = call(m, "POST", f"/api/competition-events/{CEID}/checkin", {"numbers": checked + ["109"], "state": False})
print("E3 全部撤销:", r)
r = call(admin, "POST", f"/api/competition-events/{CEID}/calculate", {})
print("E3 全缺席计算:", r)
r = call(m, "POST", f"/api/competition-events/{CEID}/checkin", {"numbers": checked, "state": True})
print("恢复检录8人:", r)
