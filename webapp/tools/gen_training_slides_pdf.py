# -*- coding: utf-8 -*-
"""培训 slides 最终交付：横版 16:9 PDF（PPT 幻灯片样式，截图为主）。
与 /tmp/gen_training_slides.py 的 PPTX 底稿同一布局。
"""
import os
from reportlab.lib.pagesizes import landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

IMGDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", "static", "manual")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "体育舞蹈评分系统-培训slides.pdf")

pdfmetrics.registerFont(TTFont("HeiL", "/System/Library/Fonts/STHeiti Light.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("HeiM", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))

W, H = 960, 540  # 13.333in x 7.5in @72dpi
ACC = HexColor("#B91C1C")
INK = HexColor("#1F2937")
MUT = HexColor("#6B7280")
WHT = HexColor("#FFFFFF")
CREAM = HexColor("#F5F3EF")
LINE = HexColor("#E3DFD8")

c = canvas.Canvas(OUT, pagesize=(W, H))


def rect(x, y, w, h, color):
    c.setFillColor(color)
    c.rect(x, y, w, h, stroke=0, fill=1)


# pptx 顶部原坐标 -> pdf 底部原坐标
def ty(y_pptx, size):
    return H - y_pptx * 72 - size


def text(x, y_pts, s, size=16, font="HeiL", color=INK, align="l", w=0):
    """y_pts：自页顶的磅数（文本顶对齐位置）。"""
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "c":
        c.drawCentredString(W / 2 if w == 0 else x + w / 2, H - y_pts - size, s)
    elif align == "r":
        c.drawRightString(x + w, H - y_pts - size, s)
    else:
        c.drawString(x, H - y_pts - size, s)


def bullets(x, y_pts, items, size=14, w=9999, gap=30, cols=1):
    import math
    if cols == 1:
        for i, it in enumerate(items):
            text(x, y_pts + i * gap, "•  " + it, size=size, color=INK)
    else:
        per = math.ceil(len(items) / cols)
        colw = 450
        for ci in range(cols):
            for i, it in enumerate(items[ci * per:(ci + 1) * per]):
                text(x + ci * colw, y_pts + i * gap, "•  " + it, size=size, color=INK)


def img(path, x, y_pts, max_w, max_h):
    """全部参数为磅：按给定区域等比缩放居中，带浅色描边框。"""
    full = os.path.join(IMGDIR, path)
    im = Image.open(full)
    ratio = im.width / im.height
    w = max_w
    h = w / ratio
    if h > max_h:
        h = max_h
        w = h * ratio
    px = x + (max_w - w) / 2
    py = y_pts + (max_h - h) / 2
    ry = H - py - h  # pdf 底部原 y
    c.setStrokeColor(LINE)
    c.setLineWidth(1.2)
    c.setFillColor(WHT)
    c.rect(px - 3, ry - 3, w + 6, h + 6, stroke=1, fill=1)
    c.drawImage(full, px, ry, w, h, preserveAspectRatio=True, mask='auto')


def bar():
    rect(0, H - 7, W, 7, ACC)


# ============ 1 封面 ============
rect(0, 0, W, H, ACC)
text(0, 144, "体育舞蹈评分系统", 40, "HeiM", WHT, "c")
text(0, 223, "赛事组织方培训手册", 20, "HeiL", WHT, "c")
text(0, 317, "四角色合订 · 现场讲解用", 26, "HeiM", INK, "c")
text(0, 382, "赛事管理员 · 检录长/检录员 · 主持人 · 裁判", 14, "HeiL", WHT, "c")
text(0, 432, "dancetkt.com · 免安装，浏览器直接使用", 13, "HeiL", WHT, "c")
c.showPage()

# ============ 2 系统一览 ============
bar()
text(50, 28, "系统一览", 30, "HeiM", INK)
text(50, 83, "六类入口，各角色各就各位", 13, "HeiL", MUT)
rows = [
    ("赛事管理员", "建赛 · 筹备向导 · 开赛 · 发布 · 晋级回填"),
    ("检录长/检录员", "背号芯片点名检录，实时同步裁判端"),
    ("主持人", "补检录 · 展开成绩公告 · 播报标记"),
    ("裁判", "免口令直达 · 三种评分制式 · 自动暂存"),
    ("观众", "免登录看赛程/成绩/团体总分/背番号查询"),
    ("大屏", "自动轮播：欢迎 → 评分中 → 成绩 → 总分榜"),
]
y = 133
for name, desc in rows:
    rect(50, H - y - 49, 864, 49, CREAM)
    text(72, y + 10, name, 16, "HeiM", ACC)
    text(330, y + 12, desc, 14, "HeiL", INK)
    y += 59
c.showPage()

# ============ 3 赛事管理员·职责 ============
bar()
text(50, 28, "赛事管理员", 30, "HeiM", ACC)
text(50, 86, "培训第 1 部分 · 赛前 1~7 天完成筹备", 13, "HeiL", MUT)
bullets(50, 137, [
    "总管理员建赛并发账号（只有总管理员能建赛）",
    "登录：赛事专属入口，角色已预选「赛事管理员」，账号口令登录",
    "登录后浏览器绑定本赛事，自动进入筹备向导或赛程编排",
    "五步向导：赛事信息 → 选手 → 裁判 → 赛程 → 工作人员",
    "比赛日：控制台一键开启评分 → 收齐自动算分 → 发布 → 晋级回填",
    "小型赛事一人多角：检录台、主持台也可由管理员直接使用",
], size=15, gap=44)
c.showPage()

# ============ 4-9 向导①~⑥ ============
wizards = [
    ("wiz1", "向导 ① 确认赛事信息", "总管理员已填，核对即可"),
    ("wiz2", "向导 ② 导入选手", "下载模板 → 填好 → 上传，即时反馈结果"),
    ("wiz3", "向导 ③ 导入裁判", "建议 5 或 7 名（顺位法按多数票计算）"),
    ("wiz4", "向导 ④ 导入赛程", "场次 + 评分制式 + 晋级名额 + 参赛选手"),
    ("wiz5", "向导 ⑤ 创建工作人员", "为检录台和主持台各建至少一个账号"),
    ("wiz6", "向导 ⑥ 完成摘要", "核对总数 → 开场第一场 → 进入赛程编排"),
]
for wname, wtitle, wdesc in wizards:
    bar()
    text(50, 24, wtitle, 26, "HeiM", ACC)
    text(50, 68, wdesc, 14, "HeiL", MUT)
    img(f"r58/{wname}.png", 50, 104, 860, 410)
    c.showPage()

# ============ 10 比赛日·控制台 ============
bar()
text(50, 24, "比赛日：控制台", 28, "HeiM", ACC)
text(50, 68, "开赛 · 盯进度 · 发布 · 晋级回填，都在这一页", 14, "HeiL", MUT)
bullets(50, 112, [
    "「开启评分」：勾选上场选手后一键开赛",
    "进度矩阵实时看各裁判交卷情况",
    "结果中心「发布」上大屏（可开自动发布）",
    "预赛发布后：晋级确认 → 生成预案 → 确认回填",
    "异常处置：退回评分 → 裁判重交 → 再发布",
], size=14, gap=30, cols=2)
img("r59/a-console-open.png", 50, 292, 860, 218)
c.showPage()

# ============ 11 检录 ============
bar()
text(50, 24, "检录长 / 检录员", 28, "HeiM", ACC)
text(50, 70, "手机即可检录，点背号芯片即完成", 14, "HeiL", MUT)
bullets(50, 120, [
    "点背号芯片变绿 = 检录",
    "「全部检录」一键到齐",
    "场次多：索引抽屉跳转 / 编号搜索",
    "已计算/发布后不再接受检录变动",
    "全部完成后裁判端自动收到上场名单",
], size=14, gap=42)
img("r50/m-checkin-chips.png", 446, 78, 460, 426)
c.showPage()

# ============ 12 主持 ============
bar()
text(50, 24, "主持人", 28, "HeiM", ACC)
text(50, 68, "控节奏：开场前补检录，赛后照稿宣读", 14, "HeiL", MUT)
bullets(50, 120, [
    "开场前确认本场检录齐全",
    "已完成场次原位展开成绩公告",
    "对照宣读：名次 / 背番号 / 队伍",
    "宣读完「标记已播报」打勾备忘",
    "下一场等结果出来自动出现在同一位置",
], size=14, gap=42)
img("r59/m-accordion.png", 496, 78, 410, 426)
c.showPage()

# ============ 13 裁判·顺位法 ============
bar()
text(50, 24, "裁判 · 顺位法（预赛/复赛/半决赛）", 28, "HeiM", ACC)
text(50, 68, "只排名次，不打分", 14, "HeiL", MUT)
bullets(50, 120, [
    "顺序点选：第 1 次点击 = 第 1 名",
    "直接指定：先点选手，再点名次键盘",
    "未检录背号灰显不可评",
    "全部评完自动提交，可修改重交",
    "过半裁判交卷即出结果",
], size=14, gap=42)
img("r59/j-skating.png", 396, 78, 388, 426)
c.showPage()

# ============ 14 裁判·Mark制+评分制 ============
bar()
text(50, 24, "裁判 · Mark 制与评分制", 28, "HeiM", ACC)
bullets(50, 86, [
    "Mark 制（预赛）：勾选应晋级的选手",
    "被过半裁判勾选 → 晋级下一轮",
    "评分制（集体舞）：0~10 分一位小数",
    "系统汇总全部裁判分数排名",
], size=14, gap=42)
img("r50/j4-mark-selected.png", 396, 78, 388, 426)
c.showPage()

# ============ 15 观众+大屏 ============
bar()
text(50, 24, "观众与大屏", 28, "HeiM", ACC)
text(50, 68, "全程免登录，成绩发布即上屏", 14, "HeiL", MUT)
bullets(50, 112, [
    "观众：赛程 / 成绩 / 背番号查询 / 团体总分，手机扫码即看",
    "大屏自动轮播：欢迎 → 评分中 → 成绩 → 总分榜（可手动锁定某一屏）",
    "成绩撤回时大屏与观众页同步隐藏，修改后重新发布",
], size=15, gap=32)
img("r50/s-screen-results.png", 50, 224, 860, 264)
text(50, 505, "dancetkt.com —— 祝赛事顺利！", 16, "HeiM", ACC, "c", w=860)
c.showPage()

c.save()
print("PDF 完成:", OUT)
