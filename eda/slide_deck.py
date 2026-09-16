#!/usr/bin/env python3
"""Slide.pptx(사내 발표용 템플릿) 기반 팀 미팅 덱 빌더.

deck.py(client-report-pptx, Report.pptx 세로형 보고서 양식)와 별개로, 이 모듈은
16:9 와이드스크린 발표 템플릿(Slide.pptx)을 대상으로 한다. 실측 기반 줄바꿈/높이
계산으로 레이아웃 이탈·글자색 충돌·도형 겹침을 방지하는 원칙은 deck.py와 동일하게
따른다.

필요 패키지: python-pptx, Pillow  (conda base: /home/jieun/miniconda3/bin/python3)
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_CONNECTOR
from PIL import ImageFont

# ---- 텍스트 줄바꿈 실측(폰트 기반, deck.py와 동일 원리) ----
_KFONT_PATH = "/home/jieun/.fonts/NotoSansKR-Regular.ttf"  # 맑은 고딕 대역 근사(서버에 맑은고딕 없음)
_FONT_CACHE = {}


def _font(pt):
    key = int(pt)
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = ImageFont.truetype(_KFONT_PATH, key * 4)
        except Exception:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def _text_width_in(text, pt):
    if not text:
        return 0.0
    f = _font(pt)
    bbox = f.getbbox(text)
    return (bbox[2] - bbox[0]) / (4 * 72)


def _wrap_lines(text, pt, width_in, safety=0.90):
    if not text:
        return 1
    avail = max(width_in * safety, 0.1)
    total = 0
    for line in str(text).split("\n"):
        if not line:
            total += 1
            continue
        words = line.split(" ")
        cur = ""
        lines = 1
        for w in words:
            trial = (cur + " " + w).strip()
            if _text_width_in(trial, pt) <= avail:
                cur = trial
            else:
                lines += 1
                cur = w
        total += lines
    return max(total, 1)


TEMPLATE = "/home/jieun/personal_docs/Slide.pptx"

# ---- 양식에서 실측한 값 ----
PAGE_W      = 13.333
PAGE_H      = 7.5
BAR_BOTTOM  = 0.745   # '제목만' 레이아웃 상단 남색 바 하단 — 이 위는 흰 글씨만 보인다
FOOTER_TOP  = 7.05    # 하단 날짜/페이지 번호 시작 — 본문은 이 위에서 끝나야 한다
CONTENT_TOP = 0.98
MARGIN      = 0.5
WIDTH       = PAGE_W - MARGIN * 2   # 12.33in

LAYOUT_TITLE   = 0   # TITLE
LAYOUT_SECTION = 2   # SECTION_HEADER
LAYOUT_CONTENT = 4   # 제목만 — 상단 남색 바 + 제목
LAYOUT_BLANK   = 5   # BLANK

_ASSETS_DIR = __import__("pathlib").Path(__file__).resolve().parent / "assets"

# ---- 팔레트 (Slide.pptx 예시 슬라이드에서 실측: Color source 슬라이드 + 실제 사용례) ----
NAVY       = RGBColor(0x00, 0x26, 0x32)   # 상단 바·본문 기본색
TEAL       = RGBColor(0x40, 0xCD, 0xDC)   # 액센트(강조 바·숫자·헤더)
CYAN_LIGHT = RGBColor(0x9C, 0xE4, 0xFE)   # 보조 액센트
LIGHT      = RGBColor(0xF3, 0xF6, 0xF6)   # 박스·표 짝수행 배경
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
GREY       = RGBColor(0x5B, 0x6B, 0x70)   # 캡션·부연설명
GREEN      = RGBColor(0x1E, 0x7A, 0x3C)
RED        = RGBColor(0xC0, 0x39, 0x2B)
AMBER      = RGBColor(0xB1, 0x76, 0x0A)

KFONT = "맑은 고딕"

_ROW_H  = 0.30
_HEAD_H = 0.34


def _style(run, size, bold, color):
    run.font.size, run.font.bold, run.font.name = Pt(size), bold, KFONT
    run.font.color.rgb = color


def _left(para):
    para.alignment = PP_ALIGN.LEFT


class _Section:
    """본문 슬라이드 한 장. y 커서를 들고 위에서 아래로 쌓는다."""

    def __init__(self, slide):
        self.slide = slide
        self.y = Inches(CONTENT_TOP)

    def gap(self, inches=0.22):
        self.y += Inches(inches)
        return self

    def subhead(self, text, size=13):
        lines = _wrap_lines(text, size, WIDTH)
        h_in = (size * 1.25 / 72) * lines + 0.08
        tb = self.slide.shapes.add_textbox(Inches(MARGIN), self.y, Inches(WIDTH), Inches(h_in))
        p = tb.text_frame.paragraphs[0]
        _style(p.add_run(), size, True, NAVY)
        p.runs[0].text = text
        _left(p)
        self.y += Inches(h_in + 0.06)
        return self

    def paragraph(self, text, size=11, color=NAVY, width_in=None, left_in=None):
        w = width_in if width_in is not None else WIDTH
        left = Inches(left_in) if left_in is not None else Inches(MARGIN)
        lines = _wrap_lines(text, size, w)
        h_in = 0.10 + (size * 1.42 / 72) * lines
        tb = self.slide.shapes.add_textbox(left, self.y, Inches(w), Inches(h_in))
        tb.text_frame.word_wrap = True
        p = tb.text_frame.paragraphs[0]
        _style(p.add_run(), size, False, color)
        p.runs[0].text = text
        p.line_spacing = 1.3
        _left(p)
        self.y += Inches(h_in)
        return self

    def table(self, headers, rows, widths, note=None, tint=None, font_pt=10, row_h=None, head_h=None):
        """행 높이는 font_pt에서 자동 계산한다(고정 상수를 쓰다가, 폰트 크기를 줄이면서 행 높이는
        그만큼 못 줄여서 실제 PowerPoint 렌더가 셀 높이를 초과해 다음 요소와 겹치는 버그가 2026-09-03
        발견됨 — 셀 세로 여백도 명시적으로 고정해 렌더가 이 계산과 어긋나지 않게 한다).
        row_h/head_h: 1줄 기준 행 높이(in)를 자동계산값 대신 쓰고 싶을 때만 지정(추가 줄은 자동 가산)."""
        CELL_MARGIN_IN = 0.14   # 좌우 여백 합(줄바꿈 폭 계산용)
        CELL_VPAD_IN = 0.09     # 상하 여백 합 — 아래에서 셀에 실제로도 이만큼만 지정한다
        LINE_H_IN = font_pt * 1.4 / 72 + 0.045   # 안전 여유 포함 1줄 높이(실측 기반, 폰트 근사 오차 대비)
        auto_h = LINE_H_IN + CELL_VPAD_IN
        row_h_base = row_h if row_h is not None else auto_h
        head_h_base = head_h if head_h is not None else auto_h

        def _rh(base_h, n_lines):
            return base_h + max(0, n_lines - 1) * LINE_H_IN

        nr, nc = len(rows) + 1, len(headers)

        header_lines = [max(1, _wrap_lines(htxt, font_pt, widths[c] - CELL_MARGIN_IN))
                         for c, htxt in enumerate(headers)]
        row_line_counts = [max(header_lines)]
        for row in rows:
            lines = [max(1, _wrap_lines(str(val), font_pt, widths[c] - CELL_MARGIN_IN))
                     for c, val in enumerate(row)]
            row_line_counts.append(max(lines))
        row_heights_in = [_rh(head_h_base, row_line_counts[0])] + \
                          [_rh(row_h_base, row_line_counts[i]) for i in range(1, nr)]
        h = Inches(sum(row_heights_in))

        t = self.slide.shapes.add_table(nr, nc, Inches(MARGIN), self.y, Inches(sum(widths)), h).table
        for i, w in enumerate(widths):
            t.columns[i].width = Inches(w)
        for i, rh in enumerate(row_heights_in):
            t.rows[i].height = Inches(rh)

        vpad = Inches(CELL_VPAD_IN / 2)
        for c, htxt in enumerate(headers):
            cell = t.cell(0, c)
            cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = vpad
            p = cell.text_frame.paragraphs[0]
            _style(p.add_run(), font_pt, True, WHITE)
            p.runs[0].text = htxt
            p.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT

        for r, row in enumerate(rows, start=1):
            for c, val in enumerate(row):
                cell = t.cell(r, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT if r % 2 else WHITE
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.margin_left = cell.margin_right = Inches(0.08)
                cell.margin_top = cell.margin_bottom = vpad
                p = cell.text_frame.paragraphs[0]
                col = (tint or {}).get((r - 1, c))
                _style(p.add_run(), font_pt, col is not None, col or NAVY)
                p.runs[0].text = str(val)
                p.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT

        self.y += h
        if note:
            gap_before = 0.10
            note_lines = _wrap_lines(note, 9, WIDTH)
            note_h_in = 0.18 * note_lines + 0.08
            tb = self.slide.shapes.add_textbox(Inches(MARGIN), self.y + Inches(gap_before),
                                               Inches(WIDTH), Inches(note_h_in))
            tb.text_frame.word_wrap = True
            p = tb.text_frame.paragraphs[0]
            _style(p.add_run(), 9, False, GREY)
            p.runs[0].text = note
            _left(p)
            self.y += Inches(gap_before + note_h_in)
        return self

    def bullets(self, title, items, accent=TEAL, width_in=None, left_in=None):
        w = width_in if width_in is not None else WIDTH
        left = Inches(left_in) if left_in is not None else Inches(MARGIN)
        inner_w = w - 0.36
        item_heights_in = []
        for lab, txt in items:
            full = f"· {lab}  {txt}"
            lines = _wrap_lines(full, 10.5, inner_w - 0.14)
            item_heights_in.append(0.22 * lines + 0.10)
        title_h = (0.28 if title else 0.0)
        h_in = 0.20 + title_h + sum(item_heights_in)
        box = self.slide.shapes.add_shape(5, left, self.y, Inches(w), Inches(h_in))
        box.fill.solid(); box.fill.fore_color.rgb = LIGHT
        box.line.color.rgb = accent; box.line.width = Pt(1.25)
        box.shadow.inherit = False
        tf = box.text_frame; tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.18)
        tf.margin_top = Inches(0.12); tf.margin_bottom = Inches(0.10)

        first = True
        if title:
            p = tf.paragraphs[0]
            _style(p.add_run(), 11.5, True, NAVY); p.runs[0].text = title
            _left(p); p.space_after = Pt(6)
            first = False

        for lab, txt in items:
            b = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            _style(b.add_run(), 10.5, True, NAVY); b.runs[0].text = f"· {lab}  "
            _style(b.add_run(), 10.5, False, GREY); b.runs[1].text = txt
            _left(b); b.space_after = Pt(4); b.line_spacing = 1.25
            b._p.get_or_add_pPr().set("marL", str(int(Inches(0.12))))
        self.y += Inches(h_in)
        return self

    def callout(self, title, body, accent=TEAL, width_in=None, left_in=None):
        w = width_in if width_in is not None else WIDTH
        left = Inches(left_in) if left_in is not None else Inches(MARGIN)
        inner_w = w - 0.36
        body_lines = _wrap_lines(body, 10.5, inner_w)
        h_in = max(0.85, 0.24 + 0.10 + 0.205 * body_lines + 0.18)
        box = self.slide.shapes.add_shape(5, left, self.y, Inches(w), Inches(h_in))
        box.fill.solid(); box.fill.fore_color.rgb = LIGHT
        box.line.color.rgb = accent; box.line.width = Pt(1.25)
        box.shadow.inherit = False
        tf = box.text_frame; tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.18)
        tf.margin_top = tf.margin_bottom = Inches(0.12)
        p = tf.paragraphs[0]
        _style(p.add_run(), 11, True, accent if accent != TEAL else NAVY); p.runs[0].text = title
        _left(p); p.space_after = Pt(4)
        p2 = tf.add_paragraph()
        _style(p2.add_run(), 10.5, False, NAVY); p2.runs[0].text = body
        _left(p2); p2.line_spacing = 1.3
        self.y += Inches(h_in)
        return self

    def image(self, path, width_in, caption=None, left_in=None, center=True):
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        height_in = width_in * ih / iw
        if left_in is not None:
            left = Inches(left_in)
        elif center:
            left = Inches(MARGIN + (WIDTH - width_in) / 2)
        else:
            left = Inches(MARGIN)
        self.slide.shapes.add_picture(path, left, self.y, width=Inches(width_in))
        top_before = self.y
        self.y += Inches(height_in)
        if caption:
            gap_before = 0.06
            cap_lines = _wrap_lines(caption, 9, width_in)
            cap_h_in = 0.16 * cap_lines + 0.06
            tb = self.slide.shapes.add_textbox(left, self.y + Inches(gap_before),
                                               Inches(width_in), Inches(cap_h_in))
            tb.text_frame.word_wrap = True
            p = tb.text_frame.paragraphs[0]
            _style(p.add_run(), 9, False, GREY)
            p.runs[0].text = caption
            _left(p)
            self.y += Inches(gap_before + cap_h_in)
        return self

    def image_centered(self, path, caption=None, max_width_in=None, top_in=None, bottom_in=None):
        """슬라이드에 그림 하나만 들어갈 때 쓴다 — 남색 제목 바 아래~하단 여백 위 공간 전체를
        기준으로 가로·세로 모두 가운데 정렬한다(위쪽 title bar, 아래쪽 footer 여백을 고려해서
        '진짜 비어 있는 영역'의 중앙에 놓는다는 뜻 — 슬라이드 전체 중앙이 아님).
        캡션이 있으면 그 높이만큼 아래쪽을 먼저 비워두고 남는 영역에서 그림을 다시 가운데 정렬한다."""
        from PIL import Image
        # top_in/bottom_in에 self.y(EMU 정수, Length)를 실수로 그대로 넘기는 실수를 방지 — 이 클래스의
        # 다른 *_in 인자는 전부 inch 단위 float인데 self.y만 Length(int 서브클래스)라 헷갈리기 쉽다
        # (2026-09-03 실제로 이 버그로 그림이 화면 밖으로 튕겨나간 적 있음).
        if isinstance(top_in, int) and not isinstance(top_in, bool):
            top_in = top_in / 914400
        if isinstance(bottom_in, int) and not isinstance(bottom_in, bool):
            bottom_in = bottom_in / 914400
        top = top_in if top_in is not None else CONTENT_TOP
        bottom = bottom_in if bottom_in is not None else FOOTER_TOP
        avail_w = max_width_in if max_width_in is not None else WIDTH
        avail_h = bottom - top

        cap_h_in = 0.0
        cap_gap = 0.08
        if caption:
            cap_lines = _wrap_lines(caption, 9, avail_w)
            cap_h_in = 0.16 * cap_lines + 0.06
            avail_h -= (cap_gap + cap_h_in)

        # 프레임에 꽉 채우면 세로로 긴 그림은 위/아래 여백이 0이 되어 바로 위 남색 바·아래 여백선에
        # 딱 붙어 보인다(2026-09-03 확인) — fit 계산은 살짝 줄인 크기로 하고, 가운데 정렬은 원래
        # 프레임 기준으로 해서 가로/세로 어느 쪽이 꽉 차든 항상 여백이 남게 한다.
        PAD = 0.92
        with Image.open(path) as im:
            iw, ih = im.size
        aspect_h_per_w = ih / iw
        width_in = min(avail_w, avail_h / aspect_h_per_w) * PAD
        height_in = width_in * aspect_h_per_w

        left = Inches(MARGIN + (WIDTH - width_in) / 2)
        img_top_in = top + max(0.0, (avail_h - height_in) / 2)
        self.slide.shapes.add_picture(path, left, Inches(img_top_in), width=Inches(width_in))
        self.y = img_top_in + height_in

        if caption:
            tb = self.slide.shapes.add_textbox(Inches(MARGIN + (WIDTH - avail_w) / 2), Inches(self.y + cap_gap),
                                               Inches(avail_w), Inches(cap_h_in))
            tb.text_frame.word_wrap = True
            p = tb.text_frame.paragraphs[0]
            _style(p.add_run(), 9, False, GREY)
            p.runs[0].text = caption
            p.alignment = PP_ALIGN.CENTER
            self.y += cap_gap + cap_h_in
        # self.y는 이 메서드 내내 inch 단위 plain float로 계산했는데, 다른 모든 메서드(gap/table/
        # callout 등)는 self.y가 Inches() Length(EMU 정수)라고 가정한다 - 여기서 Length로 되돌려
        # 놓지 않으면 다음 호출에서 float와 EMU가 뒤섞여 좌표가 완전히 깨진다(2026-09-03 실제로
        # 겪음: 캡션 바로 뒤에 이어붙인 callout이 슬라이드 맨 위로 튀어 남색 바와 겹쳤다).
        self.y = Inches(self.y)
        return self

    def stat_cards(self, cards, width_in=None, left_in=None, height_in=1.15):
        """cards = [(큰 숫자, 라벨)] — 발표용 핵심 수치 카드 n개를 가로로 나열."""
        w = width_in if width_in is not None else WIDTH
        left0 = left_in if left_in is not None else MARGIN
        n = len(cards)
        gap = 0.20
        card_w = (w - gap * (n - 1)) / n
        for i, (num, label) in enumerate(cards):
            x = Inches(left0 + i * (card_w + gap))
            box = self.slide.shapes.add_shape(5, x, self.y, Inches(card_w), Inches(height_in))
            box.fill.solid(); box.fill.fore_color.rgb = NAVY
            box.line.fill.background()
            box.shadow.inherit = False
            tf = box.text_frame; tf.word_wrap = True
            tf.margin_left = tf.margin_right = Inches(0.10)
            tf.margin_top = Inches(0.10); tf.margin_bottom = Inches(0.08)
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            _style(p.add_run(), 22, True, TEAL); p.runs[0].text = num
            p.alignment = PP_ALIGN.CENTER
            p2 = tf.add_paragraph()
            _style(p2.add_run(), 9.5, False, WHITE); p2.runs[0].text = label
            p2.alignment = PP_ALIGN.CENTER; p2.line_spacing = 1.15
        self.y += Inches(height_in)
        return self


class Deck:
    def __init__(self, template=TEMPLATE):
        self.prs = Presentation(template)
        self._clear()

    def _clear(self):
        # 원본 슬라이드를 참조(재사용)가 아니라 전부 제거하고 새로 만든다 — 일부 슬라이드의
        # sldId만 목록에서 뺐다가 나중에 재삽입하는 방식은 python-pptx의 파트 이름 재사용 로직과
        # 충돌해 저장된 pptx에 동일 파일명(ppt/slides/slideN.xml)이 중복 기록되는 손상을 일으켰다
        # (2026-09-03 발견) — 그래서 Q&A 마무리 슬라이드도 closing_qa()로 처음부터 다시 그린다.
        lst = self.prs.slides._sldIdLst
        for sld in list(lst):
            self.prs.part.drop_rel(sld.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
            lst.remove(sld)

    def _slide(self, layout_idx, keep=()):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[layout_idx])
        for ph in list(s.placeholders):
            idx = ph.placeholder_format.idx
            if idx not in keep:
                ph._element.getparent().remove(ph._element)
        return s

    def cover(self, title_lines, subtitle, eyebrow="TEAM MEETING", date_text=""):
        s = self._slide(LAYOUT_TITLE, keep=(0, 1, 13, 15, 16))
        tb = s.shapes.add_textbox(Inches(0.7), Inches(2.05), Inches(10.5), Inches(0.45))
        p = tb.text_frame.paragraphs[0]
        # 흰 배경 위 텍스트라 TEAL(저대비)은 피하고 NAVY로 고정한다 — 남색 바 위(section 제목 등)에서만 TEAL/CYAN 사용
        _style(p.add_run(), 15, True, NAVY); p.runs[0].text = eyebrow
        _left(p)

        tf = s.shapes.title.text_frame; tf.word_wrap = True
        tf.paragraphs[0].text = ""
        for i, line in enumerate(title_lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            _style(p.add_run(), 32, True, NAVY); p.runs[0].text = line
            _left(p)

        sub_ph = [ph for ph in s.placeholders if ph.placeholder_format.idx == 1]
        if sub_ph:
            stf = sub_ph[0].text_frame; stf.word_wrap = True
            stf.paragraphs[0].text = ""
            _style(stf.paragraphs[0].add_run(), 15, False, GREY)
            stf.paragraphs[0].runs[0].text = subtitle
            _left(stf.paragraphs[0])

        for ph in s.placeholders:
            if ph.placeholder_format.idx == 16 and date_text:  # DATE
                ph.text_frame.paragraphs[0].runs[0].text if ph.text_frame.paragraphs[0].runs else None
                ph.text_frame.text = date_text
                _style(ph.text_frame.paragraphs[0].runs[0], 11, False, GREY)
        return s

    def section(self, title, part=None):
        """본문 슬라이드. 남색 바 위 제목은 흰 글씨로 강제한다."""
        s = self._slide(LAYOUT_CONTENT, keep=(0,))
        t = s.shapes.title
        t.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = t.text_frame.paragraphs[0]
        p.text = ""
        _style(p.add_run(), 20, True, WHITE)
        p.runs[0].text = title

        if part:
            tb = s.shapes.add_textbox(Inches(PAGE_W - 2.6), Inches(0.24), Inches(2.2), Inches(0.3))
            pe = tb.text_frame.paragraphs[0]
            _style(pe.add_run(), 10.5, True, TEAL); pe.runs[0].text = part
            pe.alignment = PP_ALIGN.RIGHT
        return _Section(s)

    def section_divider(self, eyebrow, title, subtitle=None):
        """PART 구분용 큰 타이틀 슬라이드(SECTION_HEADER 레이아웃)."""
        s = self._slide(LAYOUT_SECTION, keep=(0, 1))
        tf = s.shapes.title.text_frame; tf.word_wrap = True
        tf.paragraphs[0].text = ""
        # SECTION_HEADER 레이아웃도 흰 배경이라 TEAL(저대비) 대신 NAVY 사용
        _style(tf.paragraphs[0].add_run(), 12, True, NAVY)
        tf.paragraphs[0].runs[0].text = eyebrow
        _left(tf.paragraphs[0])
        p2 = tf.add_paragraph()
        _style(p2.add_run(), 26, True, NAVY)
        p2.runs[0].text = title
        _left(p2)
        body_ph = [ph for ph in s.placeholders if ph.placeholder_format.idx == 1]
        if subtitle and body_ph:
            btf = body_ph[0].text_frame; btf.word_wrap = True
            btf.paragraphs[0].text = ""
            _style(btf.paragraphs[0].add_run(), 13, False, GREY)
            btf.paragraphs[0].runs[0].text = subtitle
            _left(btf.paragraphs[0])
        return s

    def closing_qa(self, subtitle="환자마다 다른 면역 반응을 이해하는 정밀의료",
                   email="info@innowl.io", phone="02-3662-2582", website="https://innowl.io"):
        """Slide.pptx 원본의 Q&A 마무리 슬라이드와 동일한 구도로 새로 그린다.
        (원본 슬라이드를 sldIdLst에서 뺐다가 재삽입하는 방식은 python-pptx 파트 이름 재사용과
        충돌해 zip 안에 동일 파일명이 중복 기록되는 손상을 일으켰다 — 2026-09-03 발견 후 이 방식으로 교체)
        연락처 텍스트는 원본이 40CDDC(저대비)였으나, 밝은 배경 위 텍스트 대비 확보를 위해 NAVY로 조정했다."""
        s = self._slide(LAYOUT_BLANK, keep=(13, 16))
        tb = s.shapes.add_textbox(Emu(2893102), Emu(2344287), Emu(6220918), Emu(769441))
        p = tb.text_frame.paragraphs[0]
        _style(p.add_run(), 32, True, NAVY)
        p.runs[0].text = "Questions & Answers"
        p.alignment = PP_ALIGN.CENTER

        stb = s.shapes.add_textbox(Emu(2741950), Emu(3160500), Emu(6708099), Emu(307777))
        sp = stb.text_frame.paragraphs[0]
        _style(sp.add_run(), 14, False, GREY)
        sp.runs[0].text = subtitle
        sp.alignment = PP_ALIGN.CENTER

        x0, y0 = Emu(3123575), Emu(3730749)
        line = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x0, y0, x0 + Emu(5944850), y0)
        line.line.color.rgb = TEAL
        line.line.width = Pt(2)

        items = [(email, 2518348, 2260036, 3895669, "icon_email.png"),
                 (phone, 5008622, 4756621, 3895669, "icon_phone.png"),
                 (website, 7498895, 7246895, 3899974, "icon_globe.png")]
        for text, tx, ix, iy, icon_name in items:
            ctb = s.shapes.add_textbox(Emu(tx), Emu(3852392), Emu(2181069), Emu(338554))
            cp = ctb.text_frame.paragraphs[0]
            _style(cp.add_run(), 13, True, NAVY)
            cp.runs[0].text = text
            cp.alignment = PP_ALIGN.CENTER
            icon_path = _ASSETS_DIR / icon_name
            if icon_path.exists():
                s.shapes.add_picture(str(icon_path), Emu(ix), Emu(iy), width=Emu(252000), height=Emu(252000))
        return s

    def validate(self):
        issues = []
        for i, s in enumerate(self.prs.slides, 1):
            mine = [sh for sh in s.shapes if not sh.is_placeholder]
            if mine:
                bottom = max(sh.top + sh.height for sh in mine) / 914400
                if bottom > FOOTER_TOP:
                    issues.append(f"슬라이드 {i}: 본문이 {bottom:.2f}in 까지 내려가 "
                                  f"하단 장식({FOOTER_TOP}in)과 겹칩니다")
                right = max(sh.left + sh.width for sh in mine) / 914400
                if right > PAGE_W - 0.05:
                    issues.append(f"슬라이드 {i}: 본문이 {right:.2f}in 까지 뻗어 슬라이드 폭({PAGE_W}in)을 벗어납니다")
            for sh in s.shapes:
                if not sh.has_text_frame or not sh.text_frame.text.strip():
                    continue
                if sh.name.startswith("Google Shape"):
                    continue  # 원본 템플릿(예: Q&A 마무리 슬라이드)에서 그대로 가져온 도형 - 내가 만든 게 아니므로 재검사하지 않는다
                top = sh.top / 914400
                runs = sh.text_frame.paragraphs[0].runs
                if not runs:
                    continue
                col = runs[0].font.color
                hexv = str(col.rgb) if col and col.type == 1 else None
                on_navy_bar = s.slide_layout.name == "제목만" and top < BAR_BOTTOM
                if on_navy_bar and hexv and hexv not in ("FFFFFF", "40CDDC", "9CE4FE"):
                    issues.append(f"슬라이드 {i}: 남색 바 위 글자가 #{hexv} 라 묻힙니다")
                # TEAL/CYAN_LIGHT는 밝은 색이라 흰/밝은 배경 위 텍스트로 쓰면 저대비다.
                # 남색 바 위(위에서 이미 허용) 또는 NAVY 채움 도형(스탯 카드 등) 내부일 때만 허용한다.
                if not on_navy_bar and hexv in ("40CDDC", "9CE4FE") and sh.shape_type != 1:
                    issues.append(f"슬라이드 {i}: 밝은 배경 위 글자가 #{hexv}(저대비)입니다")
                if not on_navy_bar and hexv in ("40CDDC", "9CE4FE") and sh.shape_type == 1:
                    try:
                        fill_rgb = str(sh.fill.fore_color.rgb) if sh.fill.type == 1 else None
                    except Exception:
                        fill_rgb = None
                    if fill_rgb != "002632":
                        issues.append(f"슬라이드 {i}: 밝은 배경(#{fill_rgb}) 위 글자가 #{hexv}(저대비)입니다")

            boxes = []
            for sh in mine:
                if sh.top is None or sh.height is None or sh.left is None or sh.width is None:
                    continue
                label = (sh.text_frame.text[:24].replace("\n", "/") if sh.has_text_frame and sh.text_frame.text
                         else ("[표]" if sh.has_table else "[도형]"))
                boxes.append((sh.top / 914400, sh.left / 914400, sh.width / 914400, sh.height / 914400, label))
            for a in range(len(boxes)):
                t1, l1, w1, h1, n1 = boxes[a]
                for b in range(a + 1, len(boxes)):
                    t2, l2, w2, h2, n2 = boxes[b]
                    y_ov = min(t1 + h1, t2 + h2) - max(t1, t2)
                    x_ov = min(l1 + w1, l2 + w2) - max(l1, l2)
                    if y_ov > 0.05 and x_ov > 0.05:
                        issues.append(f"슬라이드 {i}: '{n1}' 와 '{n2}' 가 {y_ov:.2f}in 겹칩니다")
        return issues

    def save(self, path):
        issues = self.validate()
        for m in issues:
            print(f"[경고] {m}")
        self.prs.save(path)
        print(f"[OK] {len(self.prs.slides._sldIdLst)}장 → {path}")
        return issues
