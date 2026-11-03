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
        ["① 赛事管理页填名称 / 日期 / 地点",
         "② 展开「同时创建赛事管理员账号」，填用户名口令",
         "③ 点创建：赛事自动激活、账号即时就绪",
         "④ 把赛事专属入口 /competitions/赛事ID/login 发给组织者"],
        images=[("r50/a-create-form.png", "建赛表单"), ("r50/a-create-done.png", "创建结果：已激活+账号就绪")],
        cols=2)

section("筹备向导 ①②：赛事信息与选手", "管理员 · 赛前筹备", "",
        ["向导① 总管理员已填好赛事信息，核对无误点「下一步」",
         "向导② 选手导入：下载模板 → 按列填好 → 上传，页面即时反馈导入结果"],
        images=[("r58/wiz1.png", "向导① 赛事信息"), ("r58/wiz2.png", "向导② 导入选手")],
        cols=2)

section("筹备向导 ③④⑤：裁判、赛程、工作人员", "管理员 · 赛前筹备", "",
        ["向导③ 导入裁判：建议 5 / 7 / 11 名，多数决定名次",
         "向导④ 导入赛程：每行一个场次（编号/名称/舞种/评分制式/晋级名额/参赛选手）",
         "向导⑤ 创建工作人员：为检录台和主持台各建至少一个账号"],
        images=[("r58/wiz3.png", "向导③ 导入裁判"), ("r58/wiz4.png", "向导④ 导入赛程"), ("r58/wiz5.png", "向导⑤ 工作人员")],
        cols=3)

section("筹备向导 ⑥：完成摘要与赛程编排", "管理员 · 赛前筹备", "",
        ["向导⑥ 核对选手/裁判/场次总数，点「开场第一场」直抵比赛",
         "完成后进入赛程编排页：场次树、逐场控制台与编辑入口"],
        images=[("r58/wiz6.png", "向导⑥ 完成摘要"), ("r50/a4-schedule-tree.png", "赛程编排页")],
        cols=2)

section("比赛日开场：勾选上场，一键开赛", "管理员 · 比赛日", "",
        ["控制台「上场选手管理」勾选本场上场名单",
         "「开启评分（按已勾选上场名单）」——裁判即刻可评",
         "场次临时取消：关闭评分（检录台/裁判端即时消失）",
         "重开（清空评分）：误开场的后悔药"],
        images=[("r59/a-console-open.png", "控制台：上场选手管理与开赛")],
        cols=1)

section("盯进度与发布：收齐自动算，发布进大屏", "管理员 · 场次收官", "",
        ["进度矩阵实时看各裁判交卷情况",
         "收齐自动算分；结果中心「发布（进大屏）」",
         "可开「收齐后自动发布」；发错可撤回重发",
         "可查原始打分与滑冰法判定明细"],
        images=[("r50/a-results-publish.png", "结果中心：发布/撤回/明细")],
        cols=1)

header("晋级回填与全赛收官", "管理员 · 全赛收官")
bullets(50, 112, [
    "预赛发布后：生成晋级预案 → 确认并蛇形回填下一轮",
    "决赛发布后本轮收官；逐场推进直到全部场次发布",
    "收官检查逐项打勾：场次全部「已发布」、审计日志核对本场操作",
    "异常处置（退回评分/撤回发布）见速查页",
], size=14, gap=30, maxw=560)
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
        ["专属入口角色已预选「检录长 / 检录员」，账号口令登录",
         "手机即可：每场一张卡，按场次顺序检录",
         "顶部「待检录 / 已完成」筛选 + 编号搜索定位",
         "检录结果实时同步裁判端（未检录背号裁判不可评）"],
        images=[("r50/st-login-marshal.png", "专属登录页（角色已预选）"), ("r50/m-index.png", "检录台：场次卡列表")],
        cols=2)

section("点背号检录：点到即绿", "检录长/检录员 · 场次进行", "",
        ["点背号芯片变绿 = 到场；再点取消",
         "「全部检录」一键全到",
         "「检录 N / M」实时计数，与裁判端同步",
         "已计算/发布的场次锁定，不再接受检录变动"],
        images=[("r50/m-checkin-chips.png", "点芯片检录"), ("r50/m-checkin-locate.png", "编号搜索定位")],
        cols=2)

section("异常处置与快速跳转", "检录长/检录员 · 场次进行", "",
        ["选手未到场：不点即可——保持灰显，不参与评分与收齐判定",
         "检录后未到场：再点回灰即可",
         "场次临时取消（管理员关闭评分）：检录台即时消失",
         "场次多不慌：「场次索引」抽屉按分组跳转 / 编号搜索高亮定位"],
        images=[("r61/m-p1-partial.png", "灰=未到场示例：未检录不参与评分与收齐判定"),
                ("r50/m-index-drawer.png", "场次索引抽屉")],
        cols=2)

# ============ 13 主持 ============
section("播报流程：展开、宣读、标记", "主持人 · 场次收官", "",
        ["开场前：确认本场检录齐全（缺人先催检录）",
         "已完成场次「查看成绩」原位展开，不跳页不堆底",
         "对照公告宣读：名次 / 背番号 / 队伍",
         "宣读完「标记已播报」打勾备忘；下一场结果自动出现在同一位置",
         "观众问询时用背番号查询快速应答"],
        images=[("r59/m-accordion.png", "展开成绩公告"), ("r61/m-announced-state.png", "已播报状态（可撤销）"),
                ("r50/p-lookup.png", "背番号查询")],
        cols=3)

# ============ 14-17 裁判 ============
section("免口令登录与工作台", "裁判 · 比赛日开场", "",
        ["专属入口角色已预选「裁判」，填 ID 直接登录（免口令）",
         "建议保存裁判专属书签，URL 带 judge=J1 参数免每次输入",
         "工作台页首「待评 N / M」实时计数",
         "点场次卡上的舞种进入评分页"],
        images=[("r50/j-login.png", "登录页（ID 已预填）"),
                ("r50/j-workbench.png", "工作台待评计数（空态示例，场次开启后列出待评）")],
        cols=2)

section("顺位法：只排名次，不打分", "裁判 · 场次进行", "",
        ["顺序点选：第 1 次点击 = 第 1 名，依次点完",
         "直接指定：先点选手，再点名次键盘",
         "未检录背号灰显不可评；已排名次随时可点取消重排",
         "全部排完点「提交名次表」"],
        images=[("r59/j-skating.png", "顺位法评分页"), ("r50/j4-mark-selected.png", "Mark 制勾选（预赛）")],
        cols=2)

section("Mark 制与评分制", "裁判 · 场次进行", "",
        ["Mark 制（预赛）：勾选应晋级的选手即可",
         "被过半裁判勾选 → 晋级下一轮",
         "评分制（集体舞）：给每支队伍 0~10 分，一位小数",
         "三种制式页面布局一致，上手零成本"],
        images=[("r50/j4-mark-selected.png", "Mark 制：勾选晋级"), ("r50/j-score.png", "评分制：0~10 打分")],
        cols=2)

section("提交之后：可改判，可重交", "裁判 · 场次收官", "",
        ["排满才可提交；未排满提交会被拦截提示",
         "提交后场次未关闭前，可随时修改重新提交",
         "评分作废（管理员退回评分）：页面自动刷新清空，重排重交即可",
         "本机暂存自动恢复：误关页/断网不丢已排名次",
         "名次由全体裁判多数决定，个别改判不改大势"],
        images=[("r61/j-resubmitted.png", "改判重交实拍：已提交，等待其他裁判")],
        cols=1)

# ============ 18-19 观众与大屏 ============
section("观众：免登录，扫码即看", "观众 · 全程", "",
        ["公开页：赛程 / 成绩 / 团体总分 / 背番号查询",
         "成绩「发布」即对观众可见；撤回即同步隐藏",
         "背番号查询：输入号码看单位与全部成绩",
         "锚点条快速跳转场次"],
        images=[("r50/p-results.png", "成绩页（锚点条跳转）"), ("r50/p3-public-standings.png", "团体总分榜")],
        cols=2)

section("大屏：自动轮播，可锁定", "大屏 · 全程", "",
        ["自动轮播：欢迎 → 评分中 → 成绩公告 → 团体总分榜",
         "有内容的节才参与轮播；欢迎页兜底",
         "大屏控制可手动锁定某一屏（如决赛成绩常驻）",
         "深色高对比大字号，远距离可读"],
        images=[("r50/s-screen-results.png", "成绩公告屏"), ("r50/a12-screen-control.png", "大屏控制：锁定轮播")],
        cols=2)

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
