#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机端关键布局（390×844，R148/R149 固化）：总览步骤 Tab 单行不换行（横向滑动）、
评分页首屏网格起点 <400px（首屏可见打分格）、检录台芯片可点。"""
import pytest
from conftest import ui_login, cookie_login


@pytest.fixture(scope="module")
def comp(client):
    data = client.seed_comp("UI手机端动线赛")
    ceid = data["ceid"]
    client.open(ceid["P01Z01-R1A"], client.roster_of(ceid["P01Z01-R1A"]))   # 留在评分中供裁判页测量
    return data


@pytest.fixture()
def phone_ctx(browser, base_url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, base_url=base_url,
                              device_scale_factor=2, is_mobile=True, has_touch=True)
    ctx._js_errors = []
    ctx.on("pageerror", lambda e: ctx._js_errors.append(str(e)))
    ctx.add_init_script(   # 预关 onboarding 首访弹层（不遮挡触点）
        "try{['judge','marshal','host','admin'].forEach(function(k){localStorage.setItem('onb:'+k,'1')})}catch(e){}")
    yield ctx
    errs = ctx._js_errors
    ctx.close()
    assert not errs, "页面 JS 异常：%s" % errs


def test_overview_step_tabs_single_line(phone_ctx, base_url, client, comp):
    cookie_login(phone_ctx, base_url, client.cookie)
    page = phone_ctx.new_page()
    page.goto("/events/%d/overview" % comp["cid"])
    page.wait_for_timeout(800)
    heights = page.eval_on_selector_all(
        ".nav-level2 .nav-sub-item", "els => els.map(e => e.getBoundingClientRect().height)")
    assert heights, "手机总览应有步骤 Tab"
    assert max(heights) < 45, "步骤 Tab 应单行（≤45px），实际 %s" % heights
    assert len(set(round(h) for h in heights)) == 1, "各 Tab 高度应一致（不换行挤压）: %s" % heights


def test_judge_sheet_first_screen(phone_ctx, base_url, client, comp):
    r1a = comp["ceid"]["P01Z01-R1A"]
    cookie_login(phone_ctx, base_url, client.login_judge("J1"))
    page = phone_ctx.new_page()
    page.goto("/judge/competition-events/%d/dances/平四" % r1a)
    page.wait_for_timeout(900)
    top = page.evaluate("""() => {
      const g = document.querySelector('.mark-grid, .mark-wrap, #mark-grid') ||
                document.querySelector('.mark-row');
      return g ? g.getBoundingClientRect().top : null;
    }""")
    assert top is not None, "应找到打分网格"
    assert top < 400, "手机评分页首屏应可见打分格（起点 <400px），实际 %.0f" % top


def test_staff_chip_tap(phone_ctx, base_url, client, comp):
    cid, ceid = comp["cid"], comp["ceid"]
    cookie_login(phone_ctx, base_url, _staff_cookie(client))
    page = phone_ctx.new_page()
    page.goto("/staff")
    page.wait_for_timeout(800)
    chip = page.query_selector('.st-event[data-ceid="%d"] .chip.off' % ceid["P01Z01-R1A"])
    assert chip, "手机检录台应见未检录芯片"
    chip.tap()
    page.wait_for_timeout(600)
    chip2 = page.query_selector('.st-event[data-ceid="%d"] .chip' % ceid["P01Z01-R1A"])
    assert "on" in chip2.get_attribute("class"), "触点芯片应就地变绿"


def _staff_cookie(client):
    from conftest import Api
    api = Api(client.base)
    api.req("POST", "/api/login", body={"role": "marshal", "username": "marshal",
                                        "password": "marshal123", "competition_id": 0}, expect=200)
    return api.cookie
