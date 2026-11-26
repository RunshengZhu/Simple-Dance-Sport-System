#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""筹备动线（管理员，纯 UI）：超管登录 → 建赛激活 → 向导导入选手/裁判 →
赛程页 → 执行总表行展开与开场。对应 ci_suite 动线 A 的 UI 侧。"""
import csv
import io
import os

COMP_NAME = "UI筹备动线赛"


def _csv_file(tmp_path, name, header, rows):
    p = tmp_path / name   # 每类独立文件名——同名会被后写覆盖，set_input_files 读到错文件
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    p.write_text(buf.getvalue(), encoding="utf-8")
    return str(p)


def test_admin_setup_flow(page, base_url, tmp_path):
    # ─── 超管登录页（环境口令）→ /events
    page.goto("/login")
    page.wait_for_timeout(300)
    page.fill("#password", "admin123")
    page.click("#btn")
    page.wait_for_url("**/events**")
    page.wait_for_timeout(400)

    # ─── 建赛（创建后自动激活）
    page.fill("#name", COMP_NAME)
    page.click("#create-btn")
    page.wait_for_selector("text=%s" % COMP_NAME, timeout=6000)
    assert COMP_NAME in page.content(), "建赛后列表应出现新赛事"

    # 取新 cid（列表首行激活态）
    cid = page.evaluate("""() => {
      const links = [...document.querySelectorAll('a')];
      const m = links.map(a => (a.getAttribute('href')||'').match(/\\/events\\/(\\d+)/)).find(Boolean);
      return m ? parseInt(m[1], 10) : null;
    }""")
    assert cid, "应能从列表拿到新赛事 cid"

    # ─── 筹备向导：第2步导入选手 → 第3步导入裁判（向导格式=报名总表 9 列 / 裁判 2 列）
    page.goto("/events/%d/setup" % cid)
    page.wait_for_timeout(500)
    page.click('button[data-go="2"]')   # 进入报项导入窗格
    page.wait_for_timeout(300)
    comp_csv = _csv_file(tmp_path, "competitors.csv",
                         ["项目编号", "项目名称", "背番号", "选手姓名", "选手身份", "选手单位",
                          "搭档姓名", "搭档身份", "搭档单位"],
                         [["P01A", "测试单项", "%d" % n, "选手%d" % n, "新生", "甲院", "", "", ""]
                          for n in range(101, 109)])
    judges_csv = _csv_file(tmp_path, "judges.csv", ["姓名", "单位"],
                           [["裁判甲", "甲院"], ["裁判乙", "乙院"], ["裁判丙", "丙院"]])
    page.set_input_files(".wiz-file[data-kind='competitors']", comp_csv)
    page.click(".wiz-upload-btn[data-kind='competitors']")
    page.wait_for_timeout(1200)
    assert "导入成功 8" in page.text_content(".wiz-result[data-kind='competitors']"), "选手导入成功 8 条"
    page.click('button[data-go="3"]')   # 进入导入裁判窗格
    page.wait_for_timeout(300)
    page.set_input_files(".wiz-file[data-kind='judges']", judges_csv)
    page.click(".wiz-upload-btn[data-kind='judges']")
    page.wait_for_timeout(1200)
    assert "导入成功 3" in page.text_content(".wiz-result[data-kind='judges']"), "裁判导入成功 3 条"

    # ─── 向导第4步：生成默认赛程（competitors 导入不自动建场）
    page.click('button[data-go="4"]')
    page.wait_for_timeout(300)
    page.click("#wiz-gen-schedule")
    page.wait_for_timeout(1500)
    assert "已生成" in page.text_content(".wiz-result[data-kind='schedule']"), "默认赛程应生成成功"

    # ─── 赛程页可访问
    page.goto("/events/%d/schedule" % cid)
    page.wait_for_timeout(600)
    assert "P01A" in page.content() or "场次" in page.content(), "赛程页应呈现项目/场次"

    # ─── 执行总表：行展开 + 开场
    page.goto("/events/%d/runboard" % cid)
    page.wait_for_timeout(800)
    row = page.query_selector(".rb-row")
    assert row, "总表应至少有一行"
    page.click(".rb-row .rb-main")   # 展开行详情
    page.wait_for_timeout(300)
    assert page.is_visible(".rb-row .rb-detail"), "行展开应显示上场名单与检录区"

    open_btn = page.query_selector(".rb-row button:has-text('开场')")
    if open_btn:   # 导入生成的首轮场次的名单就绪时可直接开场
        page.on("dialog", lambda d: d.accept())
        open_btn.click()
        page.wait_for_timeout(1200)
        assert page.query_selector(".rb-row .tag:has-text('评分中')"), "开场后该行应显示评分中"
