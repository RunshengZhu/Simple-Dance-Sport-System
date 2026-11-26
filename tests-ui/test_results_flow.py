#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理员成绩动线（纯 UI，R149 固化）：结果中心折叠卡+一键发布待发布、
晋级页默认落点=待确认轮次、确认回填下一轮、runboard 裁判栏与一键发布可见性。
对应 ci_suite 动线 D/E 的 UI 侧。"""
import pytest
from conftest import ui_login, cookie_login


@pytest.fixture(scope="module")
def comp(client):
    data = client.seed_comp("UI成绩动线赛")
    cid, ceid = data["cid"], data["ceid"]
    # R1A/R1B 跑完并发布（预赛有晋级数据，保持「未确认回填」供晋级页默认落点用）；
    # P02-R1（单项决赛，自带名单）算分但不发布 →「已计算 · 未发布」供一键发布用
    client.run_mark_round(ceid["P01Z01-R1A"], {"101", "102", "103", "104"})
    client.run_mark_round(ceid["P01Z01-R1B"], {"107", "108", "109", "110"})
    p2 = ceid["P02-R1"]
    client.open(p2, client.roster_of(p2))
    client.checkin_all(p2)
    for j in ("J1", "J2", "J3"):
        client.submit_sheet(p2, "华尔兹", {"201": "1", "202": "2", "203": "3", "204": "4"},
                            client.login_judge(j))
    client.calc(p2)
    return data


def test_results_cards_and_bulk_publish(as_admin, client, comp):
    page = as_admin
    cid, ceid = comp["cid"], comp["ceid"]
    page.goto("/events/%d/results" % cid)
    page.wait_for_timeout(800)

    # 已发布场次默认折叠（summary 可展开）；已计算默认展开
    pub = page.query_selector('.res-card[data-ceid="%d"]' % ceid["P01Z01-R1A"])
    assert pub.get_attribute("open") is None, "已发布场次卡应默认折叠"
    calc = page.query_selector('.res-card[data-ceid="%d"]' % ceid["P02-R1"])
    assert calc.get_attribute("open") is not None, "已计算未发布卡应默认展开"
    pub.query_selector("summary").click()
    page.wait_for_timeout(300)
    assert pub.get_attribute("open") is not None, "点击 summary 应展开已发布卡"

    # 一键发布待发布（1）→ 确认 → 全部发布
    page.on("dialog", lambda d: d.accept())
    bulk = page.query_selector("#bulk-publish-btn")
    assert bulk, "存在待发布场次时应有一键发布按钮"
    assert "1" in bulk.text_content(), "一键发布应标注数量 1"
    bulk.click()
    page.wait_for_timeout(1500)
    assert page.query_selector('.res-card[data-ceid="%d"] .tag:has-text("已发布")' % ceid["P02-R1"]), \
        "一键发布后 P02-R1 应翻转为已发布"


def test_advancement_default_landing_and_confirm(as_admin, client, comp):
    page = as_admin
    cid, ceid = comp["cid"], comp["ceid"]
    # 两场预赛已发布且未回填 → 默认落点应为 P01Z01 第 1 轮（而非决赛空白页）
    page.goto("/events/%d/advancement" % cid)
    page.wait_for_timeout(800)
    assert page.input_value("#proj") == "P01Z01", "项目下拉应默认待确认项目"
    assert page.input_value("#rnd") == "1", "轮次应默认待确认轮次（1），实际 %s" % page.input_value("#rnd")

    # 项目下拉显示名称或码，但可切换；确认按钮存在
    assert page.is_visible("#confirm-btn"), "待确认轮次应有确认按钮"
    boxes = page.query_selector_all(".adv-check")
    assert boxes, "预案应给出晋级勾选行"
    page.on("dialog", lambda d: d.accept())
    for bx in boxes:
        bx.check()
    page.click("#confirm-btn")
    page.wait_for_timeout(2000)
    # 确认后页面会随 SSE 自动刷新（默认落点切走），以回填结果为准断言
    ra = client.roster_of(ceid["P01Z01-R2A"])
    rb = client.roster_of(ceid["P01Z01-R2B"])
    assert ra and rb and not (set(ra) & set(rb)), "确认后 R2A/R2B 应各获名单且互斥 (%s / %s)" % (ra, rb)


def test_runboard_judge_bar_and_publish_all_visibility(as_admin, comp):
    page = as_admin
    cid = comp["cid"]
    page.goto("/events/%d/runboard" % cid)
    page.wait_for_timeout(900)

    # 裁判启用栏默认折叠一行（R149），可展开
    bar = page.query_selector("#judge-bar")
    toggle = page.query_selector("#judge-bar-toggle")
    assert bar and toggle, "总表应有裁判启用栏"
    assert not page.is_visible("#judge-chips"), "默认裁判芯片应折叠"
    toggle.click()
    page.wait_for_timeout(300)
    assert page.is_visible("#judge-chips"), "展开后应显示裁判芯片"
    assert "收起" in toggle.text_content(), "展开后按钮应翻转为收起"

    # 全部已发布 → 「一键发布」按钮应隐藏（常亮红按钮防误点）
    assert not page.is_visible("#rb-publish-all"), "无已计算场次时一键发布应隐藏"

    # 行内晋级状态（同模块内 advancement 测试可能已确认回填，两种状态都算正确渲染）
    row = page.query_selector('.rb-row[data-ceid="%d"]' % comp["ceid"]["P01Z01-R1A"])
    assert row, "总表应渲染 R1A 行"
    metrics = row.query_selector(".rb-metrics").text_content()
    assert ("待确认" in metrics) or ("已回填" in metrics), \
        "晋级指标应显示「待确认/已回填」之一: %s" % metrics
