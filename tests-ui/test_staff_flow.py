#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检录·主持动线（纯 UI，R149 固化）：检录台默认「待检录」视图、当前场次条与定位、
场次索引（第N场+名称，不露内部编号）、芯片点检录、主持人开赛、
已完成场次「查看成绩」Mark 数+晋级表、标记已播报。对应 ci_suite 动线 B 的 UI 侧。"""
import pytest
from conftest import ui_login


@pytest.fixture(scope="module")
def comp(client):
    data = client.seed_comp("UI检录动线赛")
    return data


def _dismiss_onboarding(page):
    page.add_init_script("try{localStorage.setItem('onb:marshal','1');localStorage.setItem('onb:host','1')}catch(e){}")


def test_staff_landing_and_index(page, client, comp):
    cid, ceid = comp["cid"], comp["ceid"]
    # 检录长走真实登录页（角色感知表单）
    ui_login(page, role="marshal", cid=cid, username="marshal", password="marshal123")
    assert "/staff" in page.url, "检录长登录后应落地检录台"
    _dismiss_onboarding(page)
    page.reload()
    page.wait_for_timeout(700)

    # 默认筛选 = 待检录（43 张卡不再一屏铺开）
    active = page.get_attribute(".status-filter .sf-btn.active", "data-f")
    assert active == "need", "默认筛选应为「待检录」，实际 %s" % active

    # 当前场次条：首场待开始场次 + 定位按钮
    assert page.is_visible("#st-now"), "当前场次条应可见"
    assert "定位到场次" in page.text_content("#st-now")
    page.click("#st-now-locate")
    page.wait_for_timeout(400)
    assert page.query_selector(".st-event.flash"), "定位后目标场次应闪烁高亮"

    # 场次索引抽屉：芯片=名称口径（有出场序时带「第N场」前缀），不露内部编号
    page.click("#scene-index-btn")
    page.wait_for_timeout(400)
    chips = page.eval_on_selector_all(".si-chip", "els => els.map(e => e.textContent.trim())")
    assert chips, "索引应列出全部场次"
    assert any("平四初赛A" in c for c in chips), "芯片应为场次名称口径: %s" % chips[:3]
    assert not any("P01Z01" in c for c in chips), "芯片不得露内部编号: %s" % chips[:3]
    page.keyboard.press("Escape")


def test_marshal_chip_checkin(page, client, comp):
    cid, ceid = comp["cid"], comp["ceid"]
    ui_login(page, role="marshal", cid=cid, username="marshal", password="marshal123")
    _dismiss_onboarding(page)
    page.goto("/staff")
    page.wait_for_timeout(700)
    card = page.query_selector('.st-event[data-ceid="%d"]' % ceid["P01Z01-R1A"])
    assert card, "待检录视图下应能看到 R1A 场次卡"
    chip = card.query_selector(".chip.off")
    prog_before = page.text_content("#prog-%d" % ceid["P01Z01-R1A"])
    chip.click()
    page.wait_for_timeout(600)
    chip2 = page.query_selector('.st-event[data-ceid="%d"] .chip' % ceid["P01Z01-R1A"])
    assert "on" in chip2.get_attribute("class"), "点击芯片应变为已检录（绿）"
    prog_after = page.text_content("#prog-%d" % ceid["P01Z01-R1A"])
    assert prog_before != prog_after, "检录计数应就地更新（%s → %s）" % (prog_before, prog_after)


def test_host_open_and_done_card(page, client, comp):
    cid, ceid = comp["cid"], comp["ceid"]
    r1a = ceid["P01Z01-R1A"]

    # 主持人开赛（staff 页 [data-open]，确认弹窗接受）
    ui_login(page, role="host", cid=cid, username="host", password="host123")
    _dismiss_onboarding(page)
    page.goto("/staff")
    page.wait_for_timeout(700)
    page.on("dialog", lambda d: d.accept())
    page.click('[data-open="%d"]' % r1a)
    page.wait_for_timeout(1500)
    card = page.query_selector('.st-event[data-ceid="%d"]' % r1a)
    assert "scoring" in card.get_attribute("data-status"), "开赛后 R1A 应为评分中"

    # 三裁 Mark（API）→ 管理员发布 → 检录台 done-card「查看成绩」
    client.checkin_all(r1a)
    for j in ("J1", "J2", "J3"):
        client.submit_sheet(r1a, "平四", {"101": True, "102": True, "103": True, "104": True},
                            client.login_judge(j))
    client.publish(r1a)
    page.reload()
    page.wait_for_timeout(900)
    # 默认「待检录」筛选会隐藏已完成卡——切到「已完成」视图再展开
    page.click('.status-filter .sf-btn[data-f="done"]')
    page.wait_for_timeout(400)
    done = page.query_selector('.done-card[data-ceid="%d"]' % r1a)
    assert done, "已发布场次应渲染为 done-card"
    done.query_selector(".toggle-done").click()
    page.wait_for_timeout(300)
    headers = page.eval_on_selector_all(
        '.done-card[data-ceid="%d"] th' % r1a, "els => els.map(e => e.textContent)")
    assert headers == ["背番号", "选手 / 队伍", "Mark数", "晋级"], \
        "Mark 制预赛成绩表应显 Mark数+晋级（不显名次）: %s" % headers

    # 标记已播报（就地翻转）
    ann = done.query_selector(".ann-btn")
    ann.click()
    page.wait_for_timeout(600)
    assert "已播报 ✓" in done.text_content(), "标记已播报后徽章应翻转"
