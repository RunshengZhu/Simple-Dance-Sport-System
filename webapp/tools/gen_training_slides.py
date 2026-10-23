# -*- coding: utf-8 -*-
"""培训 slides 生成（PPTX 16:9，截图为主，要点为辅）——独立脚本。"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

IMGDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", "static", "manual")
OUT = os.path.dirname(os.path.abspath(__file__))  # 输出到 tools/ 目录

ACC = RGBColor(0xB9, 0x1C, 0x1C)
INK = RGBColor(0x1F, 0x29, 0x37)
MUT = RGBColor(0x6B, 0x72, 0x80)
WHT = RGBColor(0xFF, 0xFF, 0xFF)
CREAM = RGBColor(0xF5, 0xF3, 0xEF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def bg(slide, color=WHT):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def txt(slide, x, y, w, h, text, size=16, bold=False, color=INK, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, ln in enumerate(text.split("\n")):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = ln
        para.alignment = align
        for run in para.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = "PingFang SC"


def bullets(slide, x, y, w, items, size=15, cols=1, colw=None):
    import math
    if cols == 1:
        groups = [(x, items)]
    else:
        per = math.ceil(len(items) / cols)
        colw = colw or w / cols
        groups = [(x + ci * colw, items[ci * per:(ci + 1) * per]) for ci in range(cols)]
    for cx, its in groups:
        tb = slide.shapes.add_textbox(Inches(cx), Inches(y), Inches(colw or w), Inches(len(its) * 0.5))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, ln in enumerate(its):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = "•  " + ln
            para.space_after = Pt(8)
            for run in para.runs:
                run.font.size = Pt(size)
                run.font.color.rgb = INK
                run.font.name = "PingFang SC"


def img(slide, path, x, y, max_w, max_h, border=True):
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
    if border:
        fr = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(px - 0.04), Inches(py - 0.04), Inches(w + 0.08), Inches(h + 0.08))
        fr.fill.solid(); fr.fill.fore_color.rgb = RGBColor(0xE3, 0xDF, 0xD8)
        fr.line.fill.background()
        fr.shadow.inherit = False
    slide.shapes.add_picture(full, Inches(px), Inches(py), Inches(w), Inches(h))


def bar(slide):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, Inches(0.1))
    sh.fill.solid(); sh.fill.fore_color.rgb = ACC
    sh.line.fill.background()
    sh.shadow.inherit = False


# ============ 1 封面 ============
s = prs.slides.add_slide(BLANK)
bg(s, ACC)
txt(s, 0, 2.0, 13.333, 1.2, "体育舞蹈评分系统", 40, True, WHT, PP_ALIGN.CENTER)
txt(s, 0, 3.1, 13.333, 0.8, "赛事组织方培训手册", 20, False, WHT, PP_ALIGN.CENTER)
txt(s, 0, 4.4, 13.333, 0.8, "四角色合订 · 现场讲解用", 26, True, INK, PP_ALIGN.CENTER)
txt(s, 0, 5.3, 13.333, 0.5, "赛事管理员 · 检录长/检录员 · 主持人 · 裁判", 14, False, WHT, PP_ALIGN.CENTER)
txt(s, 0, 6.0, 13.333, 0.5, "dancetkt.com · 免安装，浏览器直接使用", 13, False, WHT, PP_ALIGN.CENTER)

# ============ 2 系统一览 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.4, 12, 0.7, "系统一览", 30, True, INK)
txt(s, 0.7, 1.15, 12, 0.4, "六类入口，各角色各就各位", 13, False, MUT)
rows = [
    ("赛事管理员", "建赛 · 筹备向导 · 开赛 · 发布 · 晋级回填"),
    ("检录长/检录员", "背号芯片点名检录，实时同步裁判端"),
    ("主持人", "补检录 · 展开成绩公告 · 播报标记"),
    ("裁判", "免口令直达 · 三种评分制式 · 自动暂存"),
    ("观众", "免登录看赛程/成绩/团体总分/背番号查询"),
    ("大屏", "自动轮播：欢迎 → 评分中 → 成绩 → 总分榜"),
]
y = 1.85
for name, desc in rows:
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(y), Inches(12), Inches(0.68))
    sh.fill.solid(); sh.fill.fore_color.rgb = CREAM
    sh.line.fill.background()
    sh.shadow.inherit = False
    txt(s, 1.0, y + 0.12, 3.5, 0.45, name, 16, True, ACC)
    txt(s, 4.6, y + 0.14, 8, 0.45, desc, 14, False, INK)
    y += 0.82

# ============ 3 赛事管理员·职责 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.4, 12, 0.7, "赛事管理员", 30, True, ACC)
txt(s, 0.7, 1.2, 12, 0.4, "培训第 1 部分 · 赛前 1~7 天完成筹备", 13, False, MUT)
bullets(s, 0.7, 1.9, 12, [
    "总管理员建赛并发账号（只有总管理员能建赛）",
    "登录：赛事专属入口，角色已预选「赛事管理员」，账号口令登录",
    "登录后浏览器绑定本赛事，自动进入筹备向导或赛程编排",
    "五步向导：赛事信息 → 选手 → 裁判 → 赛程 → 工作人员",
    "比赛日：控制台一键开启评分 → 收齐自动算分 → 发布 → 晋级回填",
    "小型赛事一人多角：检录台、主持台也可由管理员直接使用",
], 15)

# ============ 4-9 向导①~⑥截图页 ============
wizards = [
    ("wiz1", "向导 ① 确认赛事信息", "总管理员已填，核对即可"),
    ("wiz2", "向导 ② 导入选手", "下载模板 → 填好 → 上传，即时反馈结果"),
    ("wiz3", "向导 ③ 导入裁判", "建议 5 或 7 名（顺位法按多数票计算）"),
    ("wiz4", "向导 ④ 导入赛程", "场次 + 评分制式 + 晋级名额 + 参赛选手"),
    ("wiz5", "向导 ⑤ 创建工作人员", "为检录台和主持台各建至少一个账号"),
    ("wiz6", "向导 ⑥ 完成摘要", "核对总数 → 开场第一场 → 进入赛程编排"),
]
for wname, wtitle, wdesc in wizards:
    s = prs.slides.add_slide(BLANK)
    bg(s); bar(s)
    txt(s, 0.7, 0.3, 12, 0.6, wtitle, 26, True, ACC)
    txt(s, 0.7, 0.95, 12, 0.4, wdesc, 14, False, MUT)
    img(s, f"r58/{wname}.png", 0.7, 1.45, 12.0, 5.7)

# ============ 10 比赛日·控制台 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.3, 12, 0.6, "比赛日：控制台", 28, True, ACC)
txt(s, 0.7, 0.95, 12, 0.4, "开赛 · 盯进度 · 发布 · 晋级回填，都在这一页", 14, False, MUT)
bullets(s, 0.7, 1.5, 12.0, [
    "「开启评分」：勾选上场选手后一键开赛",
    "进度矩阵实时看各裁判交卷情况",
    "结果中心「发布」上大屏（可开自动发布）",
    "预赛发布后：晋级确认 → 生成预案 → 确认回填",
    "异常处置：退回评分 → 裁判重交 → 再发布",
], 14, cols=2, colw=6.2)
img(s, "r59/a-console-open.png", 0.7, 4.0, 12.0, 3.0)

# ============ 11 检录 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.35, 12, 0.6, "检录长 / 检录员", 28, True, ACC)
txt(s, 0.7, 1.0, 12, 0.4, "手机即可检录，点背号芯片即完成", 14, False, MUT)
bullets(s, 0.7, 1.7, 5.0, [
    "点背号芯片变绿 = 检录",
    "「全部检录」一键到齐",
    "场次多：索引抽屉跳转 / 编号搜索",
    "已计算/发布后不再接受检录变动",
    "全部完成后裁判端自动收到上场名单",
], 14)
img(s, "r50/m-checkin-chips.png", 6.2, 1.1, 6.4, 5.9)

# ============ 12 主持 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.35, 12, 0.6, "主持人", 28, True, ACC)
txt(s, 0.7, 1.0, 12, 0.4, "控节奏：开场前补检录，赛后照稿宣读", 14, False, MUT)
bullets(s, 0.7, 1.7, 5.4, [
    "开场前确认本场检录齐全",
    "已完成场次原位展开成绩公告",
    "对照宣读：名次 / 背番号 / 队伍",
    "宣读完「标记已播报」打勾备忘",
    "下一场等结果出来自动出现在同一位置",
], 14)
img(s, "r59/m-accordion.png", 6.9, 1.1, 5.7, 5.9)

# ============ 13 裁判·顺位法 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.35, 12, 0.6, "裁判 · 顺位法（预赛/复赛/半决赛）", 28, True, ACC)
txt(s, 0.7, 1.0, 12, 0.4, "只排名次，不打分", 14, False, MUT)
bullets(s, 0.7, 1.7, 4.6, [
    "顺序点选：第 1 次点击 = 第 1 名",
    "直接指定：先点选手，再点名次键盘",
    "未检录背号灰显不可评",
    "全部评完自动提交，可修改重交",
    "过半裁判交卷即出结果",
], 14)
img(s, "r59/j-skating.png", 5.5, 1.1, 5.4, 5.9)

# ============ 14 裁判·Mark制+评分制 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.35, 12, 0.6, "裁判 · Mark 制与评分制", 28, True, ACC)
bullets(s, 0.7, 1.2, 4.6, [
    "Mark 制（预赛）：勾选应晋级的选手",
    "被过半裁判勾选 → 晋级下一轮",
    "评分制（集体舞）：0~10 分一位小数",
    "系统汇总全部裁判分数排名",
], 14)
img(s, "r50/j4-mark-selected.png", 5.5, 1.1, 5.4, 5.9)

# ============ 15 观众+大屏 ============
s = prs.slides.add_slide(BLANK)
bg(s); bar(s)
txt(s, 0.7, 0.3, 12, 0.6, "观众与大屏", 28, True, ACC)
txt(s, 0.7, 0.95, 12, 0.4, "全程免登录，成绩发布即上屏", 14, False, MUT)
bullets(s, 0.7, 1.55, 11.8, [
    "观众：赛程 / 成绩 / 背番号查询 / 团体总分，手机扫码即看",
    "大屏自动轮播：欢迎 → 评分中 → 成绩 → 总分榜（可手动锁定某一屏）",
    "成绩撤回时大屏与观众页同步隐藏，修改后重新发布",
], 14)
img(s, "r50/s-screen-results.png", 0.7, 3.1, 12.0, 3.7)
txt(s, 0.7, 6.85, 12, 0.4, "dancetkt.com —— 祝赛事顺利！", 16, True, ACC, PP_ALIGN.CENTER)

prs.save(os.path.join(OUT, "体育舞蹈评分系统-培训slides.pptx"))
print("PPT 完成，共", len(prs.slides._sldIdLst), "页")
