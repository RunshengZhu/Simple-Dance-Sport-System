# -*- coding: utf-8 -*-
"""R109 培训幻灯片 v4：两级导航 + 赛程执行总表 + 场次总表导入 + 裁判指派（26 页）
版式引擎：要点块动态测高 → 截图区自动下移（杜绝图文重叠）；
全部文本自动换行；胶囊 stringWidth 精确定宽；资产图边缘预修边（去半截行）。
"""
import os
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image

IMGDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "server", "static", "manual")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "体育舞蹈评分系统-培训slides.pdf")

pdfmetrics.registerFont(TTFont("HeiL", "/System/Library/Fonts/STHeiti Light.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("HeiM", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))

W, H = 960, 540
ACC = HexColor("#B91C1C")
INK = HexColor("#1F2937")
MUT = HexColor("#6B7280")
WHT = HexColor("#FFFFFF")
CREAM = HexColor("#F5F3EF")
LINE = HexColor("#E3DFD8")
STAGE = HexColor("#8A6D1D")

c = canvas.Canvas(OUT, pagesize=(W, H))


def text(x, y, s, size=16, font="HeiL", color=INK, align="l", w=0):
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "c":
        c.drawCentredString(W / 2 if w == 0 else x + w / 2, H - y - size, s)
    else:
        c.drawString(x, H - y - size, s)


def wrap(s, font, size, maxw):
    lines, cur = [], ""
    for ch in s:
        if stringWidth(cur + ch, font, size) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def bar():
    c.setFillColor(ACC)
    c.rect(0, H - 7, W, 7, stroke=0, fill=1)


def header(title, stage, sub=""):
    bar()
    pw = stringWidth(stage, "HeiM", 12.5) + 20
    c.setFillColor(STAGE)
    c.roundRect(50, H - 44, pw, 26, 13, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 12.5)
    c.drawCentredString(50 + pw / 2, H - 36.5, stage)
    text(50 + pw + 16, 20, title, 23, "HeiM", ACC)
    if sub:
        text(50, 60, sub, 13, "HeiL", MUT)


def bullets(x, y, items, size=14, gap=30, maxw=None):
    """绘制要点块，返回块底 y（供截图区动态跟随）。"""
    maxw = maxw or (W - x - 60)
    for it in items:
        lines = wrap(it, "HeiL", size, maxw - 20)
        for li, line in enumerate(lines):
            text(x + (0 if li == 0 else 14), y, ("•  " if li == 0 else "") + line, size=size, color=INK)
            y += size * 1.45
        y += gap * 0.42
    return y


def draw_img_region(images, y_top, area_h, cols, total_w=860, x0=50):
    """在 y_top..y_top+area_h 区域内按 cols 列排布图片（含图注）。images=[(path,cap)]"""
    if not images or area_h < 60:
        return
    colw = (total_w - (cols - 1) * 16) / cols
    cap_h = 18 if any(cap for _, cap in images) else 0
    img_h = area_h - cap_h
    per = (len(images) + cols - 1) // cols
    rows = (len(images) + cols - 1) // cols
    row_h = (img_h - (rows - 1) * 10) / rows if rows else img_h
    for i, (path, cap) in enumerate(images):
        r, col = divmod(i, cols)
        x = x0 + col * (colw + 16)
        yy = y_top + r * (row_h + 10)
        img_h_i = row_h - (18 if cap else 0)
        full = os.path.join(IMGDIR, path)
        im = Image.open(full)
        ratio = im.width / im.height
        w = colw
        h = w / ratio
        if h > img_h_i:
            h = img_h_i
            w = h * ratio
        px = x + (colw - w) / 2
        ry = H - yy - img_h_i
        c.setStrokeColor(LINE)
        c.setLineWidth(1.2)
        c.setFillColor(WHT)
        c.rect(px - 3, ry - 3, w + 6, h + 6, stroke=1, fill=1)
        c.drawImage(full, px, ry, w, h, preserveAspectRatio=True, mask='auto')
        if cap:
            for li, line in enumerate(wrap(cap, "HeiL", 11.5, colw)):
                text(x, yy + img_h_i + 4 + li * 13, line, 11.5, "HeiL", MUT)


def section(title, stage, sub, items, images=None, cols=1, maxw=860, size=14, gap=30):
    """标准内容页：页头 + 要点块（动态测高）+ 图片区自动下移。"""
    bar()
    header(title, stage, sub)
    end_y = bullets(50, 112, items, size=size, gap=gap, maxw=maxw)
    img_y = end_y + 10
    area_h = H - img_y - 14
    draw_img_region(images or [], img_y, area_h, cols)
    c.showPage()


def caption(x, y, s):
    text(x, y, s, 12, "HeiL", MUT)


def img(path, x, y, max_w, max_h, cap=None):
    full = os.path.join(IMGDIR, path)
    im = Image.open(full)
    ratio = im.width / im.height
    w = max_w
    h = w / ratio
    if h > max_h:
        h = max_h
        w = h * ratio
    px = x + (max_w - w) / 2
    py = y + (max_h - h) / 2
    ry = H - py - h
    c.setStrokeColor(LINE)
    c.setLineWidth(1.2)
    c.setFillColor(WHT)
    c.rect(px - 3, ry - 3, w + 6, h + 6, stroke=1, fill=1)
    c.drawImage(full, px, ry, w, h, preserveAspectRatio=True, mask='auto')
    if cap:
        text(x, y + max_h + 6, cap, 12, "HeiL", MUT)


# ============ 1 封面 ============
c.setFillColor(ACC)
c.rect(0, 0, W, H, stroke=0, fill=1)
text(0, 140, "体育舞蹈评分系统", 40, "HeiM", WHT, "c")
text(0, 216, "培训手册 · 按角色 × 赛事全生命周期", 20, "HeiL", WHT, "c")
text(0, 306, "赛事管理员 · 检录长/检录员 · 主持人 · 裁判 · 观众/大屏", 24, "HeiM", INK, "c")
text(0, 372, "从赛前筹备到比赛收官，每个角色的每一步", 14, "HeiL", WHT, "c")
text(0, 430, "dancetkt.com · 免安装，浏览器直接使用", 13, "HeiL", WHT, "c")
c.showPage()

# ============ 2 全生命周期泳道总览 ============
bar()
text(50, 24, "赛事全生命周期：谁在什么时候做什么", 25, "HeiM", INK)
text(50, 62, "五阶段 × 五角色。后续章节按角色展开，配实机截图。", 13, "HeiL", MUT)
cols_name = [["赛前 1~7 天", "筹备"], ["比赛日", "开场"], ["场次进行", ""], ["场次收官", ""], ["全赛收官", ""]]
RX, RW = 50, 148
CW, CG = 140, 6
CX0 = RX + RW + 12
head_y, cell_h, stride = 102, 56, 64
for ci, cname in enumerate(cols_name):
    x = CX0 + ci * (CW + CG)
    c.setFillColor(CREAM)
    c.roundRect(x, H - head_y - 40, CW, 40, 8, stroke=0, fill=1)
    text(x + 10, head_y + 4, cname[0], 13, "HeiM", STAGE)
    if cname[1]:
        text(x + 10, head_y + 21, cname[1], 13, "HeiM", STAGE)
roles = [
    ("赛事管理员", [["建赛+发账号", "五步向导"], ["勾选上场", "开启评分"], ["盯进度", "退回处置"], ["发布进大屏", "晋级回填"], ["收官检查", "审计日志"]]),
    ("检录长/检录员", [["账号就绪"], ["逐场检录"], ["异常处置", "未到场留灰"], None, None]),
    ("主持人", [None, ["开场确认", "检录齐全"], ["控节奏"], ["展开公告", "宣读+标记"], None]),
    ("裁判", [["名单导入"], ["免口令登录", "待命"], ["评分提交"], ["可改判重交"], None]),
    ("观众 / 大屏", [None, ["开屏欢迎"], ["实时查询", "大屏轮播"], ["成绩可见"], ["团体总分榜"]]),
]
y = head_y + 46
for rname, cells in roles:
    c.setFillColor(ACC)
    c.roundRect(RX, H - y - cell_h, RW, cell_h, 8, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 13.5)
    c.drawCentredString(RX + RW / 2, H - y - cell_h / 2 - 5, rname)
    for ci, cell in enumerate(cells):
        x = CX0 + ci * (CW + CG)
        c.setStrokeColor(LINE)
        c.setFillColor(WHT)
        c.roundRect(x, H - y - cell_h, CW, cell_h, 8, stroke=1, fill=1)
        if cell:
            for li, line in enumerate(cell):
                text(x + 10, y + 11 + li * 19, line, 12, "HeiL", INK)
        else:
            text(x + 10, y + 19, "—", 13, "HeiL", MUT)
    y += stride
c.showPage()

# ============ 3-9 赛事管理员 ============
section("建赛与发账号", "管理员 · 赛前筹备", "",
        ["① 填名称 / 日期 / 地点，展开子表单填管理员账号口令",
          "② 点创建：自动激活、账号即时就绪",
          "③ 把专属入口 /competitions/赛事ID/login 发给组织者"],
        images=[("r50/a-create-form.png", "建赛表单"), ("r50/a-create-done.png", "创建结果")],
        cols=2, size=15)

section("筹备向导 ①②：赛事信息与选手", "管理员 · 赛前筹备", "",
        ["向导① 信息已填好，核对即可",
          "向导② 选手：下载模板 → 填好 → 上传"],
        images=[("r58/wiz1.png", "向导① 赛事信息"), ("r58/wiz2.png", "向导② 导入选手")],
        cols=2, size=15)

section("筹备向导 ③④⑤：裁判、赛程、工作人员", "管理员 · 赛前筹备", "",
        ["向导③ 裁判：建议 5 / 7 / 9 名（可指派子集上场）",
          "向导④ 赛程：一键默认编排；正式编排推荐「场次总表导入」",
          "向导⑤ 工作人员：检录台、主持台各建一号"],
        images=[("r58/wiz3.png", "向导③"), ("r58/wiz4.png", "向导④"), ("r58/wiz5.png", "向导⑤")],
        cols=3, size=15)

section("筹备向导 ⑥：完成摘要与赛程编排", "管理员 · 赛前筹备", "",
        ["向导⑥ 核对总数，点「开场第一场」直达比赛",
          "之后从赛程编排页管理全部场次"],
        images=[("r58/wiz6.png", "向导⑥ 完成摘要"), ("r109/p-schedule-projects.png", "项目管理页")],
        cols=2, size=15)

section("场次总表导入：秩序册编排一次进系统", "管理员 · 赛前筹备", "",
        ["秩序册/编排表整理成 CSV（场次/项目/轮次/背番号/姓名/单位/搭档…）",
          "替换式导入：需全部场次待开始；同项目同轮多场自动 A/B/C 场标",
          "名称含「不计入团体总分」→ 该项目自动不计入团体总分"],
        images=[("r109/a-schedule-import.png", "场次总表导入")],
        cols=1, size=15)

section("项目管理：参数与团体计分", "管理员 · 赛前筹备", "",
        ["每场上限 / 决赛人数 / 晋级模式 / 分配策略统一设置",
          "团体计分三态：标准、老带新半分（按选手身份）、不计入总分",
          "单项目覆盖表单独配置；报项人数不足的项目不提供按参数重建"],
        images=[("r109/p-schedule-projects.png", "项目管理页")],
        cols=1, size=15)

section("两级导航与赛程执行总表", "管理员 · 比赛日", "",
        ["顶栏一级=阶段（筹备工作台 / 比赛控制 / 展示与公开），二级=功能页",
          "比赛控制 → 赛程执行总表：全部场次一行一卡，一页搞定",
          "行内动作：开场 / 检录 / 发布 / 撤回 / 播报 / 手动计算 / PDF 导出"],
        images=[("r109/a-runboard.png", "赛程执行总表")],
        cols=1, size=15)

section("展开行卡：名单、裁判矩阵、指派、导出", "管理员 · 比赛日", "",
        ["点行卡展开：上场名单 chip 代检录、裁判 × 舞种进度矩阵",
          "上场裁判指派：勾选本场裁判，收齐判定按指派名单（9 登记可用 7）",
          "快捷 PDF：Mark 场导明细表、决赛场导名次表，直接下载公示"],
        images=[("r109/a-runboard-detail.png", "展开行卡")],
        cols=1, size=15)

section("结果中心：核对与发布", "管理员 · 场次收官", "",
        ["结果中心核对综合名次与判定明细（见计分规则章）",
          "「发布（进大屏）」上大屏，发错可撤回重发",
          "赛程执行总表也可直接发布/导出 PDF"],
        images=[("r109/a-runboard.png", "赛程执行总表行内发布")],
        cols=1, size=15)

header("晋级回填与全赛收官", "管理员 · 全赛收官")
bullets(50, 112, [
    "预赛发布后：生成预案 → 确认回填下一轮",
    "逐场推进，直到全部场次「已发布」",
    "收官核对：场次状态 + 审计日志（右侧清单）",
], size=15, gap=30, maxw=560)
img("r109/a-advancement.png", 50, 296, 540, 206, cap="晋级确认：合并预案默认全勾，可人工调减")
# 收官检查清单卡（绘制，替代整页截图）
CX, CY, CWD, CHT = 620, 296, 290, 208
c.setFillColor(CREAM)
c.setStrokeColor(STAGE)
c.setLineWidth(1.5)
c.roundRect(CX, H - CY - CHT, CWD, CHT, 10, stroke=1, fill=1)
text(CX + 16, CY + 12, "收官检查清单", 15, "HeiM", STAGE)
checks = ["全部场次状态 = 已发布", "审计日志核对本场操作", "团体总分榜数据正确", "导出成绩册归档"]
yy = CY + 52
for item in checks:
    c.setFillColor(STAGE)
    c.circle(CX + 22, H - yy - 7, 3.5, stroke=0, fill=1)
    text(CX + 34, yy, item, 12.5, "HeiL", INK)
    yy += 34
c.showPage()

# ============ 10-12 检录 ============
section("登录与检录列表", "检录长/检录员 · 比赛日开场", "",
        ["专属入口登录（角色已预选），手机即可",
          "每场一张卡；「待检录/已完成」筛选 + 编号搜索",
          "检录实时同步裁判端"],
        images=[("r50/st-login-marshal.png", "专属登录页"), ("r50/m-index.png", "检录台")],
        cols=2, size=15)

section("点背号检录：点到即绿", "检录长/检录员 · 场次进行", "",
        ["点背号变绿 = 到场，再点取消",
          "「全部检录」一键全到；计数实时同步"],
        images=[("r50/m-checkin-chips.png", "点芯片检录"), ("r50/m-checkin-locate.png", "编号搜索")],
        cols=2, size=15)

section("异常处置与快速跳转", "检录长/检录员 · 场次进行", "",
        ["未到场：不点即可（保持灰显）",
          "检录后不到：再点回灰",
          "场次多：「场次索引」抽屉跳转 / 搜索定位"],
        images=[("r61/m-p1-partial.png", "灰=未到场"),
                ("r50/m-index-drawer.png", "场次索引")],
        cols=2, size=15)

# ============ 13 主持 ============
section("名单页三视图：参赛名单与导入同步", "管理员 · 赛前筹备", "",
        ["参赛名单（默认）：按实际场次编排列出每项目上场选手与搭档",
          "报项名单：报名总表原始数据；单位与队伍：单位统计与集体舞"],
        images=[("r109/p-roster-parts.png", "参赛名单")],
        cols=1, size=15)

section("播报流程：展开、宣读、标记", "主持人 · 场次收官", "",
        ["开场前确认检录齐全",
          "已完成场次「查看成绩」原位展开，照单宣读",
          "宣读完「标记已播报」；下一场自动就位"],
        images=[("r59/m-accordion.png", "展开公告"), ("r61/m-announced-state.png", "已播报"),
                ("r50/p-lookup.png", "背番号查询")],
        cols=3, size=15)

# ============ 14-17 裁判 ============
section("免口令登录与工作台", "裁判 · 比赛日开场", "",
        ["填 ID 直接登录，免口令（可保存书签）",
          "工作台「待评 N / M」实时计数",
          "点舞种进入评分页"],
        images=[("r50/j-login.png", "登录页"), ("r50/j-workbench.png", "工作台（空态示例）")],
        cols=2, size=15)

section("顺位法：只排名次，不打分", "裁判 · 场次进行", "",
        ["顺序点选：第 1 次点击 = 第 1 名",
          "也可先点选手再点名次键盘",
          "排完点「提交名次表」"],
        images=[("r59/j-skating.png", "顺位法"), ("r50/j4-mark-selected.png", "Mark 制")],
        cols=2, size=15)

section("Mark 制：默认全选，名额门禁", "裁判 · 场次进行", "",
        ["打开评分页默认全选已检录选手，快捷按钮一键调整",
          "全选 / 清空 / 按名额选前 N；点行可单独勾选或取消",
          "勾选数不足晋级名额时提交键置灰（旁注还差几人），补满可交"],
        images=[("r109/j-mark-quick.png", "Mark 制快捷操作")],
        cols=1, size=15)

section("评分制：0~10 分", "裁判 · 场次进行", "",
        ["点输入框给 0~10 分（一位小数），系统汇总排名"],
        images=[("r50/j-score.png", "评分制")],
        cols=1, size=15)

section("提交之后：可改判，可重交", "裁判 · 场次收官", "",
        ["提交后可随时修改重交",
          "被「退回评分」：重排重交即可",
          "误关页不丢名次（本机自动暂存）"],
        images=[("r61/j-resubmitted.png", "改判重交实拍")],
        cols=1, size=15)

# ============ 18-19 观众与大屏 ============
# ============ 计分规则章（R65 新增，口径取自 core/scoring_service 实际实现） ============
header("三种评分制式总览", "计分规则 · 总览")
colx = [50, 250, 470, 690]
colw = [190, 210, 210, 170]
c.setFillColor(CREAM)
c.roundRect(50, H - 100, 860, 34, 8, stroke=0, fill=1)
for xi, htxt in enumerate(["", "顺位法 SKATING", "Mark 制 MARK", "评分制 SCORE"]):
    text(colx[xi] + 8, 88, htxt, 13.5, "HeiM", STAGE)
rows_t = [
    ("裁判做什么", "给每个选手排名次 1~N", "勾选应晋级的选手", "每队 0~10 分一位小数"),
    ("系统怎么算", "滑冰法多数决（见下页）", "得票数排序，票多者前", "全部裁判分数求和，高者前"),
    ("怎么晋级", "名次 ≤ 晋级名额", "前 N 名晋级（N=名额）", "名次 ≤ 晋级名额"),
    ("用于哪轮", "预/复/半决赛、决赛", "预赛", "集体舞"),
]
yy = 142
for r in rows_t:
    for xi, cell in enumerate(r):
        text(colx[xi] + 8, yy, cell, 13, "HeiL", INK if xi else STAGE)
    yy += 62
c.setStrokeColor(LINE)
c.line(50, H - yy + 30, 910, H - yy + 30)
text(50, yy + 44, "三种制式页面布局一致；收齐判定与自动计算规则相同（见后页）。", 13, "HeiL", MUT)
c.showPage()

header("顺位法：滑冰法多数决四步", "计分规则 · 顺位法")
steps = [
    ("1", "每位裁判给 1~N 名次（无分数）"),
    ("2", "收齐后从第 1 名逐位分配：累计票数先过半者得该名次"),
    ("3", "过半阈值 = 裁判数 ÷ 2 + 1（11 裁 = 6 票，7 裁 = 4 票）"),
    ("4", "多舞种时：综合名次 = 各舞多数决名次的中位数"),
]
yy = 118
for num, line in steps:
    c.setFillColor(ACC)
    c.circle(66, H - yy - 10, 14, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 15)
    c.drawCentredString(66, H - yy - 15.5, num)
    text(94, yy, line, 15.5, "HeiL", INK)
    yy += 62
img("r50/j-skating.png", 620, 96, 290, 320)
text(50, yy + 6, "举例（7 裁判，第 1 名）：201 得 4 票先过半 → 201 是第 1 名；", 13.5, "HeiL", MUT)
text(50, yy + 26, "剩余选手继续累计第 2 名及以内票数，先过半者得第 2 名，依次类推。", 13.5, "HeiL", MUT)
c.showPage()

header("并列怎么破：三轮决胜与同分并列", "计分规则 · 并列处理")
steps2 = [
    ("1", "多人同时过半 → 比较该名次段内多数票数，多者列前"),
    ("2", "仍平 → 比较全部名次之和，小者列前"),
    ("3", "再平 → 并列（名次 1、1、3 式跳号）"),
    ("+", "Mark 制 / 评分制同分：直接并列，边界同进同退"),
]
yy = 118
for num, line in steps2:
    c.setFillColor(STAGE)
    c.circle(66, H - yy - 10, 14, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 15)
    c.drawCentredString(66, H - yy - 15.5, num)
    text(94, yy, line, 15.5, "HeiL", INK)
    yy += 62
c.setFillColor(CREAM)
c.roundRect(50, H - yy - 108, 860, 96, 10, stroke=0, fill=1)
text(70, yy + 26, "决胜全部由系统自动完成，裁判无需干预。", 14.5, "HeiL", INK)
text(70, yy + 54, "每一步的票数与名次和明细，在结果中心「滑冰判定表」可查。", 14.5, "HeiL", INK)
c.showPage()

header("收齐、自动计算与重算", "计分规则 · 流程")
flow = [
    ("收齐判定", "已检录选手 × 每舞 × 每裁判都有记录（Mark 制=每裁判有提交即可）"),
    ("未检录者", "不参与评分，也不计入收齐——没人评也能收齐"),
    ("自动计算", "最后一位裁判提交的瞬间自动算分出名次"),
    ("退回评分", "管理员可作废全部评分：观众页成绩同步隐藏，裁判重排重交"),
    ("发布可见", "只有「已发布」场次进入公开页、大屏、导出与团体总分"),
]
yy = 116
for k, v in flow:
    c.setFillColor(STAGE)
    c.roundRect(50, H - yy - 26, 108, 26, 13, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 12.5)
    c.drawCentredString(104, H - yy - 18.5, k)
    text(176, yy, v, 14, "HeiL", INK)
    yy += 52
c.showPage()

header("团体总分怎么算", "计分规则 · 团体总分")
steps3 = [
    ("1", "按名次赋分：第 1~8 名 = 9、7、6、5、4、3、2、1 分"),
    ("2", "只计各项目的最末轮（决赛轮）成绩"),
    ("3", "双人跨单位组合 → 归主报单位；集体队伍 → 归队伍单位"),
    ("4", "同单位同项目有多项成绩 → 只计最高一项"),
]
yy = 122
for num, line in steps3:
    c.setFillColor(ACC)
    c.circle(66, H - yy - 10, 14, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 15)
    c.drawCentredString(66, H - yy - 15.5, num)
    text(94, yy, line, 15.5, "HeiL", INK)
    yy += 66
img("r50/p3-public-standings.png", 640, 100, 270, 330)
c.showPage()

section("观众：免登录，扫码即看", "观众 · 全程", "",
        ["免登录：赛程 / 成绩 / 团体总分 / 背号查询",
          "成绩发布即可见，撤回即隐藏"],
        images=[("r50/p-results.png", "成绩页"), ("r50/p3-public-standings.png", "团体总分榜")],
        cols=2, size=15)

section("大屏：自动轮播，可锁定", "大屏 · 全程", "",
        ["自动轮播：欢迎 → 评分中 → 成绩 → 总分榜",
          "可手动锁定某一屏"],
        images=[("r50/s-screen-results.png", "成绩公告屏"), ("r50/a12-screen-control.png", "大屏控制")],
        cols=2, size=15)

# ============ 20 异常速查 ============
bar()
text(50, 24, "异常处置速查", 25, "HeiM", INK)
text(50, 60, "现场出状况不怕：高频异常的处置动作与系统联动。", 13, "HeiL", MUT)
colx = [50, 200, 420, 700]
colw = [140, 210, 270, 200]
rows = [
    ("选手未到场", "检录员不点即可（保持灰显）", "裁判不可评；不参与收齐判定", "成绩/晋级自然不含该选手"),
    ("检录后未到场", "检录员再点回灰", "裁判端即时灰显", "—"),
    ("场次临时取消", "管理员：控制台「关闭评分」", "检录台/裁判端即时消失", "可另择期重开"),
    ("误开场次", "管理员：「重开（清空评分）」", "已有评分清空", "重新检录评分"),
    ("裁判评分作废", "管理员：「退回评分」", "观众页同步隐藏；裁判页清空重交", "名次由多数决定"),
    ("发错成绩", "管理员：结果中心「撤回发布」", "大屏/观众页同步隐藏", "修正后重新发布"),
]
y = 92
c.setFillColor(CREAM)
c.roundRect(50, H - y - 28, 860, 28, 6, stroke=0, fill=1)
for xi, htxt in enumerate(["异常情况", "处置人 · 动作", "系统联动", "结果"]):
    text(colx[xi] + 10, y + 6, htxt, 13, "HeiM", STAGE)
y += 36
for r in rows:
    cells_lines = [wrap(cell, "HeiL", 12.5, colw[xi] - 16) for xi, cell in enumerate(r)]
    maxlines = max(len(ls) for ls in cells_lines)
    rh = maxlines * 17 + 12
    for xi, ls in enumerate(cells_lines):
        for li, line in enumerate(ls):
            text(colx[xi] + 10, y + 4 + li * 17, line, 12.5, "HeiL", INK)
    c.setStrokeColor(LINE)
    c.line(50, H - y - rh + 4, 910, H - y - rh + 4)
    y += rh + 8
c.showPage()

# ============ 21 封底 ============
c.setFillColor(ACC)
c.rect(0, 0, W, H, stroke=0, fill=1)
text(0, 120, "入口速查", 34, "HeiM", WHT, "c")
entries = [
    ("赛事专属入口", "/competitions/赛事ID/login（按角色预选）"),
    ("观众页", "/public/results · /public/schedule"),
    ("大屏", "/screen"),
    ("使用手册", "/manual"),
]
yy = 200
for k, v in entries:
    text(0, yy, k, 16, "HeiM", INK, "c")
    text(0, yy + 34, v, 15, "HeiL", WHT, "c")
    yy += 84
text(0, 580, "口令请向赛事管理员领取 · 祝赛事顺利！", 14, "HeiL", WHT, "c")
text(0, 620, "dancetkt.com", 13, "HeiL", WHT, "c")
c.showPage()

c.save()
print("v2.2 PDF 完成:", OUT)
