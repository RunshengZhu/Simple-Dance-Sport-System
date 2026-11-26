#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""裁判动线（纯 UI，R148/R149 固化）：工作台默认「待评」过滤+快速进入横幅 →
Mark 制点选（picked 绿、名额徽章、收齐提交、提交后下一步引导）→
顺位法直接模式点行排名 → 评分制输入分值。对应 ci_suite 动线 C 的 UI 侧。"""
import pytest
from conftest import ui_login


@pytest.fixture(scope="module")
def comp(client):
    data = client.seed_comp("UI裁判动线赛")
    return data


@pytest.fixture()
def j1(page, base_url, comp):
    """J1 走真实登录页（角色感知表单），落地裁判工作台。"""
    url = ui_login(page, role="judge", cid=comp["cid"], judge_id="J1")
    assert "/judge" in url, "裁判登录后应落地工作台"
    page.wait_for_timeout(600)
    return page


def _open_and_checkin(client, ceid):
    client.open(ceid, client.roster_of(ceid))
    return client.checkin_all(ceid)


def test_workbench_filter_and_banner(j1, client, comp):
    page = j1
    cid = comp["cid"]
    r1a = comp["ceid"]["P01Z01-R1A"]
    _open_and_checkin(client, r1a)   # 开 R1A（scoring），其余全部 pending
    page.reload()
    page.wait_for_timeout(900)

    # 默认过滤 = 待评/进行中：pending 卡隐藏
    active = page.get_attribute("#jh-seg .seg-btn.seg-on", "data-f")
    assert active == "todo", "工作台默认应过滤到「待评/进行中」"
    visible = page.eval_on_selector_all(
        ".jh-card", "els => els.filter(e => e.style.display !== 'none').length")
    assert visible == 1, "默认视图只应见 1 张评分中场次卡，实际 %d" % visible
    assert page.is_visible(".jh-scoreable"), "评分中场次卡应有高亮类"

    # 快速进入横幅：直达未完成舞种
    banner = page.query_selector(".judge-now .jn-btn")
    assert banner and "平四" in banner.text_content(), "快速进入横幅应指向未完成舞种"
    banner.click()
    page.wait_for_timeout(800)
    assert "/dances/" in page.url, "横幅应直达评分页"


def test_mark_sheet_pick_and_submit(j1, client, comp):
    page = j1
    r1a = comp["ceid"]["P01Z01-R1A"]
    _open_and_checkin(client, r1a)
    page.goto("/judge/competition-events/%d/dances/平四" % r1a)
    page.wait_for_timeout(700)

    # 名额徽章 + 未选时提交禁用
    badge = page.text_content(".quota-badge")
    assert "晋级名额" in badge and "4" in badge, "Mark 制名额徽章应显示晋级名额 4：%s" % badge
    assert page.is_disabled("#submit"), "未收齐名额时提交应禁用"

    # 点选 4 对 → picked 绿色 → 提交可用
    cells = page.query_selector_all(".mark-cell:not(.off)")
    for c in cells[:4]:
        c.click()
    page.wait_for_timeout(300)
    picked = page.eval_on_selector_all(
        ".mark-cell.picked", "els => els.length")
    assert picked == 4, "点选 4 对后应有 4 个 picked（绿=选中晋级），实际 %d" % picked
    assert not page.is_disabled("#submit"), "收齐名额后提交应可用"
    page.click("#submit")
    page.wait_for_timeout(1200)

    # 提交后下一步引导：本舞种已提交 ✓ + 返回待评场次
    assert "已提交" in page.text_content("#submit"), "提交键应翻转为已提交态"
    assert page.is_visible("#next-btn"), "应出现下一步引导链接"
    # 三裁收齐 → 自动算分（其余两裁 API 补交）
    for j in ("J2", "J3"):
        client.submit_sheet(r1a, "平四", {"101": True, "102": True, "103": True, "104": True},
                            client.login_judge(j))
    st, d = client.req("GET", "/api/competition-events/%d/progress" % r1a)
    assert d.get("status") == "calculated", "三裁收齐应自动算分"


def test_skating_sheet_direct_mode(j1, client, comp):
    page = j1
    p2 = comp["ceid"]["P02-R1"]
    _open_and_checkin(client, p2)
    page.add_init_script("try{localStorage.setItem('judge-skate-mode','seq')}catch(e){}")
    page.goto("/judge/competition-events/%d/dances/%s" % (p2, "华尔兹"))
    page.wait_for_timeout(700)
    assert page.is_visible("#skate-mode-bar"), "顺位法应有模式切换条"

    # 顺序点选模式：按名次依次点行（1=最优）
    for num in ("201", "202", "203", "204"):
        page.click('.rank-row[data-num="%s"]' % num)
        page.wait_for_timeout(150)
    vals = page.eval_on_selector_all(
        ".rank-row .val", "els => els.map(e => e.value)")
    assert vals == ["1", "2", "3", "4"], "顺序点选应按序给名次: %s" % vals
    page.click("#submit")
    page.wait_for_timeout(1000)
    for j in ("J2", "J3"):
        client.submit_sheet(p2, "华尔兹", {"201": "1", "202": "2", "203": "3", "204": "4"},
                            client.login_judge(j))
    st, d = client.req("GET", "/api/competition-events/%d/progress" % p2)
    assert d.get("status") == "calculated", "顺位法三裁收齐应自动算分"


def test_score_sheet_input(j1, client, comp):
    page = j1
    p3 = comp["ceid"]["P03-R1"]
    client.open(p3, ["301", "302"])   # schedule/add 场次无名单，显式开场
    client.checkin_all(p3)
    page.goto("/judge/competition-events/%d/dances/现代舞" % p3)
    page.wait_for_timeout(700)

    # 评分制（0~10）：逐队输入分值
    for num, val in (("301", "9.5"), ("302", "8.0")):
        page.fill('input.val[data-num="%s"]' % num, val)
    page.click("#submit")
    page.wait_for_timeout(1000)
    assert "已提交" in page.text_content("#submit"), "评分制提交后应翻转已提交态"
