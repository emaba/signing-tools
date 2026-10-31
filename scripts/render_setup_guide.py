"""Build the human PDF and unsigned sample from the shareable Markdown guide."""

import argparse
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Preformatted,
                                PageBreak)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--date', required=True)
parser.add_argument('--sans-font', type=Path, required=True)
parser.add_argument('--bold-font', type=Path, required=True)
parser.add_argument('--mono-font', type=Path, required=True)
args = parser.parse_args()
BUNDLE = args.bundle
BUILD_DATE = args.date
WIDTH = A4[0] - 80
pdfmetrics.registerFont(TTFont('GuideSans',str(args.sans_font)))
pdfmetrics.registerFont(TTFont('GuideSans-Bold',str(args.bold_font)))
pdfmetrics.registerFont(TTFont('GuideMono',str(args.mono_font),subfontIndex=0))
pdfmetrics.registerFontFamily('GuideSans',normal='GuideSans',bold='GuideSans-Bold')
ink = colors.HexColor('#17324D')
accent = colors.HexColor('#2457A7')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyGuide', fontName='GuideSans',fontSize=10,leading=13.4,
                          spaceAfter=7,textColor=colors.HexColor('#243446')))
styles.add(ParagraphStyle(name='GuideTitle',fontName='GuideSans-Bold',fontSize=26,leading=30,
                          spaceAfter=12,textColor=ink))
styles.add(ParagraphStyle(name='GuideH2',fontName='GuideSans-Bold',fontSize=18,leading=22,
                          spaceBefore=2,spaceAfter=12,textColor=ink,keepWithNext=True))
styles.add(ParagraphStyle(name='GuideH3',fontName='GuideSans-Bold',fontSize=12,leading=16,
                          spaceBefore=10,spaceAfter=7,textColor=accent,keepWithNext=True))
styles.add(ParagraphStyle(name='GuideList',parent=styles['BodyGuide'],leftIndent=12,firstLineIndent=-10,
                          spaceAfter=5))

def markup(text):
    text=escape(text)
    text=re.sub(r'`([^`]+)`',r'<font name="GuideMono" size="9">\1</font>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'(https://[^\s<>]+)',lambda m:f'<link href="{m[1]}" color="#2457A7">{m[1]}</link>',text)
    return text

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#D7DFE9'))
    canvas.line(40,35,A4[0]-40,35)
    canvas.setFont('GuideSans',8)
    canvas.setFillColor(colors.HexColor('#596A7D'))
    canvas.drawString(40,23,'Signing tools | macOS setup | '+BUILD_DATE)
    canvas.drawRightString(A4[0]-40,23,str(doc.page))
    if doc.page>1:
        canvas.setFont('GuideSans',8)
        canvas.drawString(40,A4[1]-24,'Signing tools - installation and first use')
    canvas.restoreState()

lines=(BUNDLE/'START-HERE.md').read_text().splitlines()
story=[]
index=0
while index<len(lines):
    line=lines[index]
    if not line.strip():
        index+=1;continue
    if line=='<!-- pagebreak -->':
        story.append(PageBreak());index+=1;continue
    if line.startswith('```'):
        index+=1;code=[]
        while index<len(lines) and not lines[index].startswith('```'):
            code.append(lines[index]);index+=1
        size=min(8.6,(WIDTH-20)/(max(map(len,code),default=1)*.602))
        assert size>=7.5, 'A command needs explicit safe wrapping before PDF export.'
        style=ParagraphStyle(name='Code',fontName='GuideMono',fontSize=size,leading=size*1.3,
                             borderColor=colors.HexColor('#DFE5EC'),borderWidth=.5,borderPadding=9,
                             backColor=colors.HexColor('#F4F6F9'),spaceBefore=3,spaceAfter=11)
        story.append(Preformatted('\n'.join(code),style));index+=1;continue
    if line.startswith('# '):
        story.append(Paragraph(markup(line[2:]),styles['GuideTitle']));index+=1;continue
    if line.startswith('## '):
        story.append(Paragraph(markup(line[3:]),styles['GuideH2']));index+=1;continue
    if line.startswith('### '):
        story.append(Paragraph(markup(line[4:]),styles['GuideH3']));index+=1;continue
    list_line=line.startswith('- ') or re.match(r'^\d+\. ',line)
    parts=[line]
    index+=1
    while index<len(lines) and lines[index].strip() and not lines[index].startswith(('#','```','<!--','- ')) and not re.match(r'^\d+\. ',lines[index]):
        parts.append(lines[index].strip());index+=1
    text=' '.join(parts)
    if list_line and text.startswith('- '):text='- '+text[2:]
    story.append(Paragraph(markup(text),styles['GuideList' if list_line else 'BodyGuide']))

destination=BUNDLE/'START-HERE.pdf'
doc=SimpleDocTemplate(str(destination),pagesize=A4,leftMargin=40,rightMargin=40,
                      topMargin=43,bottomMargin=47,title='Signing tools for macOS - installation guide',
                      author='Signing tools project', invariant=1)
doc.build(story,onFirstPage=footer,onLaterPages=footer)

sample=Canvas(str(BUNDLE/'sample.pdf'),pagesize=A4,invariant=1)
sample.setTitle('Unsigned signing-tool sample')
sample.setAuthor('Signing tools project')
for number in range(1,4):
    sample.setFillColor(ink)
    sample.setFont('Helvetica-Bold',23)
    sample.drawString(20*mm,270*mm,'Signing tools - sample document')
    sample.setFillColor(colors.HexColor('#596A7D'))
    sample.setFont('Helvetica',11)
    sample.drawString(20*mm,259*mm,f'Unsigned test PDF | Page {number} of 3')
    sample.setStrokeColor(colors.HexColor('#D7DFE9'))
    sample.line(20*mm,250*mm,190*mm,250*mm)
    sample.setFillColor(colors.HexColor('#243446'))
    sample.setFont('Helvetica',12)
    for row,text in enumerate(('This document contains no personal or confidential information.',
                               'Use it for the first PAdES and CAdES signing tests.',
                               'Place a visible signature in the blank area near the bottom.')):
        sample.drawString(20*mm,(228-row*11)*mm,text)
    sample.setFont('Helvetica',9)
    sample.setFillColor(colors.HexColor('#596A7D'))
    sample.drawString(85*mm,58*mm,'Suggested signature area (110 x 27 mm)')
    sample.setDash(3,3)
    sample.rect(85*mm,25*mm,110*mm,27*mm)
    sample.setDash()
    sample.showPage()
sample.save()
print('Human guide and unsigned three-page sample created.')
