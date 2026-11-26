#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印·公众动线（纯 UI，R149 固化）：打印台紧凑表勾选+合并打印弹窗、
公众首页状态条/分区锚点/行展开/成绩查询、大屏锁定场次与去内部编号。
对应 ci_suite 动线 F/G 的 UI 侧。"""
import pytest
from conftest import ui_login, cookie_login


@pytest.fixture(scope="module")
def comp(client):
    """全链路推进到「全部发布」：预赛→确认回填→复赛→决赛，团体分可复算。"""
    data = client.seed_comp("UI打印公众动线赛")
    cid, ceid = data["cid"], data["ceid"]
    client.run_mark_round(ceid["P01Z01-R1A"], {"101", "102", "103", "104"})
    client.run_mark_round(ceid["P01Z01-R1B"], {"107", "108", "109", "110"})
    client.confirm_adv(cid, "P01Z01", 1, {"P01Z01-R2A": ["101", "102", "103", "104"],
                                          "P01Z01-R2B": ["107", "108", "109", "110"]})
    client.run_mark_round(ceid["P01Z01-R2A"], {"101", "102"})
    client.run_mark_round(ceid["P01Z01-R2B"], {"107", "108"})
    client.confirm_adv(cid, "P01Z01", 2, {"P01Z01-R3": ["101", "102", "107", "108"]})
    client.open(ceid["P01Z01-R3"], client.roster_of(ceid["P01Z01-R3"]))
    client.checkin_all(ceid["P01Z01-R3"])
    for j in ("J1", "J2", "J3"):
        client.submit_sheet(ceid["P01Z01-R3"], "平四",
                            {"101": "1", "107": "2", "102": "3", "108": "4"}, client.login_judge(j))
    client.publish(ceid["P01Z01-R3"])
    client.open(ceid["P02-R1"], client.roster_of(ceid["P02-R1"]))
    client.checkin_all(ceid["P02-R1"])
    for j in ("J1", "J2", "J3"):
        client.submit_sheet(ceid["P02-R1"], "华尔兹",
                            {"201": "1", "202": "2", "203": "3", "204": "4"}, client.login_judge(j))
    client.publish(ceid["P02-R1"])
    return data


def test_print_desk_and_batch_view(page, ctx, base_url, comp):
    cid = comp["cid"]
    from conftest import Api
    pc = Api(base_url)
    st, d = pc.req("POST", "/api/login", body={"role": "printer", "username": "ui-printer",
                                               "password": "print123", "competition_id": cid})
    assert st == 200, d
    cookie_login(ctx, base_url, pc.cookie)
    page.goto("/print")
    page.wait_for_timeout(800)

    # 紧凑表：勾选已发布场次 → 计数 → 合并打印弹窗
    boxes = page.query_selector_all(".pt-ck")
    assert len(boxes) >= 6, "紧凑表应为已发布场次提供勾选框（6 场），实际 %d" % len(boxes)
    page.click("#pt-sel-all")
    page.wait_for_timeout(200)
    assert "6" in page.text_content("#pt-count"), "全选后应显示已选 6 场"
    assert not page.is_disabled("#pt-batch"), "勾选后合并打印应可用"
    with page.context.expect_page() as popup_info:
        page.click("#pt-batch")
    popup = popup_info.value
    popup.wait_for_load_state()
    assert "print/view?ids=" in popup.url, "合并打印应打开批量视图: %s" % popup.url
    assert popup.query_selector_all(".pv-sec"), "批量视图应包含多节公示表"


def test_public_home_and_lookup(page, comp):
    cid = comp["cid"]
    page.goto("/competitions/%d" % cid)
    page.wait_for_timeout(800)

    # 状态条（已收官态）+ 分区锚点
    assert page.is_visible(".home-status"), "公众首页应有赛事状态条"
    chips = page.eval_on_selector_all(".anchor-bar .anchor-chip", "els => els.map(e => e.textContent)")
    assert "赛程" in chips and "成绩公告" in chips and "团体总分" in chips, "分区锚点应齐备: %s" % chips
    assert not page.query_selector(".ev-code"), "公众赛程表不得显示内部编号"

    # 赛程行点击展开成绩
    row = page.query_selector(".ev-row.clickable")
    row.click()
    page.wait_for_timeout(300)
    assert page.query_selector(".ev-detail:not([hidden])"), "点击赛程行应展开成绩详情"

    # 成绩查询：背番号 → 晋级/成绩
    page.fill("#lookup-input", "101")
    page.keyboard.press("Enter")
    page.wait_for_timeout(900)
    assert "101" in page.content() and ("晋级" in page.content() or "名次" in page.content()), \
        "成绩查询应返回选手 101 的动线信息"


def test_screen_pin_and_no_internal_codes(as_admin, page, comp):
    cid, ceid = comp["cid"], comp["ceid"]
    r1a = ceid["P01Z01-R1A"]
    as_admin.goto("/screen?comp=%d" % cid)
    as_admin.wait_for_timeout(1000)
    body = as_admin.evaluate("document.body.innerText")   # innerText 不含 script 源码
    # 大屏观众口径：不露场次内部编号（P01Z01-R1A 类码）；团体榜项目名可能因
    # 测试数据集项目码形状回退为码（生产可解析），此处只断言场次码不出现。
    assert "P01Z01-R1A" not in body, "大屏不得露出内部场次编号"

    # 锁定后大屏成绩节只显示该场并标注已锁定
    r = as_admin.evaluate("""async (arg) => {
      const r = await fetch('/api/screen-control', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode: 'results', event_id: arg.ceid})});
      return r.status;
    }""", {"ceid": r1a})
    assert r == 200, "锁定场次接口应 200"
    as_admin.reload()
    as_admin.wait_for_timeout(1500)
    body = as_admin.evaluate("document.body.innerText")
    assert "已锁定" in body, "锁定模式大屏应显示「已锁定」"
    assert "P01Z01-R1A" not in body, "锁定后大屏仍不得露内部场次编号"
