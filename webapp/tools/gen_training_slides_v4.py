# -*- coding: utf-8 -*-
"""R64 培训幻灯片 v2.2：按角色 × 赛事全生命周期（21 页）。
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


def data_table(x, y_top, widths, headers, rows, row_h=36, size=13.5, last_accent=None):
    """精确对位表格：表头带 + 数据行（单元格 rect 与文字同一几何）。返回表底 y。"""
    total = sum(widths)
    c.setFillColor(CREAM)
    c.rect(x, H - y_top - 30, total, 30, stroke=0, fill=1)
    cx = x
    for w, hd in zip(widths, headers):
        text(cx + 10, y_top + 8, hd, 13, "HeiM", STAGE)
        cx += w
    ry = y_top + 34
    for r in rows:
        cx = x
        for xi, cell in enumerate(r):
            c.setFillColor(WHT)
            c.setStrokeColor(LINE)
            c.rect(cx, H - ry - row_h, widths[xi], row_h, stroke=1, fill=1)
            accent = (xi == 0) or (last_accent is not None and xi == last_accent)
            text(cx + 10, ry + (row_h - size) / 2, str(cell), size, "HeiM" if accent else "HeiL",
                 ACC if xi == 0 else (STAGE if last_accent is not None and xi == last_accent else INK))
            cx += widths[xi]
        ry += row_h
    return ry


def example_box(x, y, w, textline):
    """「例」实例框：红徽章 + 奶油底 + 换行文本。返回占用高度。"""
    lines = wrap(textline, "HeiL", 13, w - 64)
    h = 20 + len(lines) * 19 + 12
    c.setFillColor(CREAM)
    c.setStrokeColor(LINE)
    c.roundRect(x, H - y - h, w, h, 8, stroke=1, fill=1)
    c.setFillColor(ACC)
    c.circle(x + 24, H - y - h / 2, 13, stroke=0, fill=1)
    c.setFillColor(WHT)
    c.setFont("HeiM", 12.5)
    c.drawCentredString(x + 24, H - y - h / 2 - 4.5, "例")
    for li, line in enumerate(lines):
        text(x + 48, y + 12 + li * 19, line, 13, "HeiL", INK)
    return h + 10


def section(title, stage, sub, items, images=None, cols=1, maxw=860, size=14, gap=30, example=None):
    """标准内容页：页头 + 要点块 + 实例框(可选) + 图片区，全部动态测高。"""
    bar()
    header(title, stage, sub)
    end_y = bullets(50, 112, items, size=size, gap=gap, maxw=maxw)
    ey = end_y + 8
    if example:
        ey += example_box(50, ey, 860, example)
    img_y = ey + 10
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
        cols=2, size=15, example="例：填「2026 北京新生赛」，创建后秒级激活，同时拿到账号 bjtu-organizer 和专属入口链接。")

section("筹备向导 ①②：赛事信息与选手", "管理员 · 赛前筹备", "",
        ["向导① 信息已填好，核对即可",
          "向导② 选手：下载模板 → 填好 → 上传"],
        images=[("r58/wiz1.png", "向导① 赛事信息"), ("r58/wiz2.png", "向导② 导入选手")],
        cols=2, size=15)

section("筹备向导 ③④⑤：裁判、赛程、工作人员", "管理员 · 赛前筹备", "",
        ["向导③ 裁判：建议 5 / 7 / 11 名",
          "向导④ 赛程：每行一场（编号/舞种/制式/晋级名额/选手）",
          "向导⑤ 工作人员：检录台、主持台各建一号"],
        images=[("r58/wiz3.png", "向导③"), ("r58/wiz4.png", "向导④"), ("r58/wiz5.png", "向导⑤")],
        cols=3, size=15)

section("筹备向导 ⑥：完成摘要与赛程编排", "管理员 · 赛前筹备", "",
        ["向导⑥ 核对总数，点「开场第一场」直达比赛",
          "之后从赛程编排页管理全部场次"],
        images=[("r58/wiz6.png", "向导⑥ 完成摘要"), ("r50/a4-schedule-tree.png", "赛程编排页")],
        cols=2, size=15)

section("比赛日开场：勾选上场，一键开赛", "管理员 · 比赛日", "",
        ["勾选上场名单 →「开启评分」，裁判即刻可评",
          "取消场次：关闭评分；误开：重开清空"],
        images=[("r59/a-console-open.png", "控制台")],
        cols=1, size=15, example="例：第 1 场勾选 8 人开启评分 → 裁判手机立刻出现待评卡；收齐即自动算分。")

section("盯进度与发布：收齐自动算，发布进大屏", "管理员 · 场次收官", "",
        ["进度矩阵盯交卷；收齐自动算分",
          "结果中心「发布（进大屏）」，发错可撤回重发",
          "可查原始打分与判定明细（见计分规则章）"],
        images=[("r50/a-results-publish.png", "结果中心")],
        cols=1, size=15, example="例：P1 裁判交齐 → 自动算出名次 → 点「发布」→ 大屏与观众页立刻出现成绩。")

header("晋级回填与全赛收官", "管理员 · 全赛收官")
bullets(50, 112, [
    "预赛发布后：生成预案 → 确认回填下一轮",
    "逐场推进，直到全部场次「已发布」",
    "收官核对：场次状态 + 审计日志（右侧清单）",
], size=15, gap=30, maxw=560)
img("r50/a6-advancement.png", 50, 296, 540, 206, cap="晋级确认与预案")
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
        cols=2, size=15, example="例：P1 报名 12 人、实际到场 9 人 → 点 9 个芯片，3 个保持灰色。")

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
section("播报流程：展开、宣读、标记", "主持人 · 场次收官", "",
        ["开场前确认检录齐全",
          "已完成场次「查看成绩」原位展开，照单宣读",
          "宣读完「标记已播报」；下一场自动就位"],
        images=[("r59/m-accordion.png", "展开公告"), ("r61/m-announced-state.png", "已播报"),
                ("r61/p-lookup-ok.png", "查询 207：命中，显示姓名与单位")],
        cols=3, size=15, example="例：P1F 发布后，主持台出现 P1F 卡 → 展开 → 照读「第 1 名 201」→ 点标记已播报。")

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
        images=[("r59/j-skating.png", "顺位法评分页（顺序点选 + 名次键盘两种模式）")],
        cols=1, size=15, example="例：第 1 次点击 201 → 201 得第 1 名；再点 207 → 207 得第 2 名；点错再点即取消。")

section("Mark 制与评分制", "裁判 · 场次进行", "",
        ["Mark 制：勾选应晋级的选手",
          "评分制：每队 0~10 分（一位小数）",
          "三种制式页面布局一致"],
        images=[("r50/j4-mark-selected.png", "Mark 制"), ("r50/j-score.png", "评分制")],
        cols=2, size=15)

section("提交之后：可改判，可重交", "裁判 · 场次收官", "",
        ["提交后可随时修改重交",
          "被「退回评分」：重排重交即可",
          "误关页不丢名次（本机自动暂存）"],
        images=[("r61/j-resubmitted.png", "改判重交实拍")],
        cols=1, size=15)

# ============ 18-19 观众与大屏 ============
# ============ 计分规则章：贯穿式实例（7 裁判 × 选手 201~205，顺位法名额 3） ============
header("计分规则 · 贯穿实例（一）：评分与收齐", "计分规则 · 实例")
text(50, 62, "设定：7 名裁判 J1~J7，选手 201~205，顺位法，晋级名额 3。全体裁判提交如下名次：", 13.5, "HeiL", MUT)
# 投票矩阵
ballots = [
    ["J1", "1", "2", "3", "4", "5"],
    ["J2", "1", "2", "3", "4", "5"],
    ["J3", "1", "2", "3", "4", "5"],
    ["J4", "1", "2", "3", "4", "5"],
    ["J5", "1", "2", "3", "4", "5"],
    ["J6", "1", "2", "3", "4", "5"],
    ["J7", "1", "2", "3", "4", "5"],
]
text(50, 94, "每位裁判的名次表：", 13, "HeiL", MUT)
data_table(50, 108, [74, 74, 74, 74, 74, 74], ["裁判", "201", "202", "203", "204", "205"], ballots, row_h=34)
# 右侧要点
text(560, 108, "收齐判定：已检录选手 × 每舞 × 每裁判", 14, "HeiL", INK)
text(560, 136, "都有记录 → 本例 5×1×7 = 35 条，提交即收齐。", 14, "HeiL", INK)
text(560, 176, "未检录选手（本例无）不参与评分，", 14, "HeiL", INK)
text(560, 204, "也不计入收齐——没人评也能收齐。", 14, "HeiL", INK)
text(560, 244, "最后一位裁判（J7）提交的瞬间，", 14, "HeiL", INK)
text(560, 272, "系统自动计算出名次，无需任何人点「计算」。", 14, "HeiL", INK)
text(560, 320, "退回评分 = 全部作废：", 14, "HeiM", ACC)
text(560, 348, "观众页成绩同步隐藏，裁判页清空后重排重交。", 14, "HeiL", INK)
text(50, 448, "接下来三页：这张名次表如何一步步算出名次（多数决 → 并列 → Mark/评分制）。", 13.5, "HeiL", MUT)
c.showPage()

header("计分规则 · 贯穿实例（二）：多数决分配名次", "计分规则 · 顺位法")
text(50, 62, "从第 1 名开始逐位分配：累计「获得该名次及以内」的票数，先过半（7÷2+1 = 4 票）者得该名次。", 13.5, "HeiL", MUT)
# 累计票数表
rows2 = [
    ["201", "7", "7", "7", "第 1 名"],
    ["202", "0", "7", "7", "第 2 名"],
    ["203", "0", "0", "7", "第 3 名"],
    ["204", "0", "0", "0", "第 4 名"],
    ["205", "0", "0", "0", "第 5 名"],
]
data_table(50, 108, [132, 132, 132, 132, 132], ["选手", "≤1 票", "≤2 票", "≤3 票", "结果"], rows2,
           row_h=40, size=14, last_accent=4)
text(50, 368, "读法：201 的「≤1 票」= 7（全体都给 201 第 1 名），7 ≥ 4 过半 → 201 即第 1 名；", 13.5, "HeiL", INK)
text(50, 392, "去掉 201 后继续分第 2 名：202 的「≤2 票」= 7 → 第 2 名；如此到第 5 名。", 13.5, "HeiL", INK)
text(50, 432, "晋级名额 3 → 201、202、203 晋级下一轮；204、205 止步。", 14, "HeiM", ACC)
text(50, 460, "每一步的票数与名次和：结果中心「滑冰判定表」可查，全程可追溯。", 13.5, "HeiL", MUT)
c.showPage()

header("计分规则 · 贯穿实例（三）：并列怎么破", "计分规则 · 并列处理")
text(50, 62, "6 名裁判（偶数裁判团最易出并列）：J1~J3 把 201 排第 1、202 排第 2；J4~J6 反过来。", 13.5, "HeiL", MUT)
tie_rows = [
    ["201", "3", "6", "并列第 1"],
    ["202", "3", "6", "并列第 1"],
    ["203", "0", "0", "第 3 名起"],
]
data_table(50, 108, [180, 180, 180, 260], ["选手", "≤1 票", "≤2 票", "结果"], tie_rows,
           row_h=40, size=14)
bullets(50, 330, [
    "第 1 名：201、202 各 3 票，都不过半（需 6÷2+1 = 4）→ 无人锁定，继续累计",
    "第 2 名：两人「≤2 票」各 6，同时过半 → 同位并列",
    "三轮决胜：段内多数票 6=6 平 → 段内名次和 9=9 平 → 总名次和 9=9 平",
    "终局：并列第 1（下一位直接是第 3 名）——系统自动完成",
], size=14.5, gap=30, maxw=860)
c.showPage()

header("计分规则 · 贯穿实例（四）：Mark 制与评分制", "计分规则 · 其他制式")
text(50, 66, "Mark 制（预赛，7 裁，名额 3）：勾选应晋级者，按得票排序取前 3。", 13.5, "HeiL", MUT)
mrows = [["201", "7 票", "晋级"], ["202", "6 票", "晋级"], ["203", "3 票", "晋级"], ["204", "2 票", "止步"], ["205", "0 票", "止步"]]
data_table(50, 100, [110, 130, 120], ["选手", "得票", "结果"], mrows, row_h=34, size=13.5, last_accent=2)
text(560, 66, "评分制（集体舞，3 裁）：全部裁判分数求和，高者前。", 13.5, "HeiL", MUT)
srows = [["A 队", "9.5+9.0+9.2", "27.7"], ["B 队", "8.9+8.8+9.1", "26.8"]]
data_table(520, 100, [110, 170, 100], ["队伍", "三裁分数", "总分"], srows, row_h=34, size=13.5, last_accent=2)
# 底部：两种「多数」口径对比
c.setFillColor(CREAM)
c.roundRect(50, H - 386, 860, 76, 10, stroke=0, fill=1)
text(70, 318, "两种「多数」口径：顺位法=名次被过半数裁判认可即锁定（名次×裁判矩阵，三轮决胜）；", 13.5, "HeiL", INK)
text(70, 342, "Mark 制=按票数排序取名额，不要求过半；评分制=没有票，只加总分。", 13.5, "HeiL", INK)
c.showPage()

header("计分规则 · 贯穿实例（五）：团体总分", "计分规则 · 团体总分")
text(50, 66, "单位 A 的两个项目成绩 → 合计团体分：", 13.5, "HeiL", MUT)
grows = [["华尔兹决赛", "201 = 第 1 名", "9 分"], ["恰恰预赛 L1", "205 = 第 2 名", "7 分"]]
data_table(50, 100, [200, 220, 120], ["项目", "最末轮名次", "赋分"], grows, row_h=40, size=14)
c.setFillColor(CREAM)
c.roundRect(50, H - 320, 450, 44, 8, stroke=0, fill=1)
text(64, 288, "单位 A = 9 + 7 = 16 分", 16, "HeiM", ACC)
bullets(50, 356, [
    "只计各项目的最末轮（预赛成绩不算数）",
    "同单位同项目多项成绩 → 只计最高一项",
    "双人跨单位组合 → 归主报单位；集体队伍 → 归队伍单位",
    "赋分表：第 1~8 名 = 9、7、6、5、4、3、2、1，第 8 名后 = 0",
], size=14, gap=26, maxw=860)
c.showPage()

section("观众：免登录，扫码即看", "观众 · 全程", "",
        ["免登录：赛程 / 成绩 / 团体总分 / 背号查询",
          "成绩发布即可见，撤回即隐藏"],
        images=[("r50/p-results.png", "成绩页"), ("r50/p3-public-standings.png", "团体总分榜")],
        cols=2, size=15, example="例：输入背番号 201 → 立刻看到单位与全部轮次名次。")

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
