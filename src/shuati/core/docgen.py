"""
文档生成：把数据库中的题目生成 Word 文档。
"""
import os
import json
import re
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from shuati.core.database import get_threads_by_date_range, get_questions_by_thread, get_blocks_by_thread
from shuati.core.config import DATA_DIR
from shuati.core.ocr_utils import analyze_image_text

LARGE_IMAGE_TRIGGER_WIDTH = Cm(12)
LARGE_IMAGE_TRIGGER_HEIGHT = Cm(10)
EXPORT_IMAGE_MAX_WIDTH = Cm(10.5)
EXPORT_IMAGE_MAX_HEIGHT = Cm(8.5)


def generate_word(start_date: str, end_date: str, output_path: str = None, source_thread_ids: list[str] | None = None) -> str:
    threads = get_threads_by_date_range(start_date, end_date)
    if source_thread_ids:
        picked = set(source_thread_ids)
        threads = [t for t in threads if t["thread_id"] in picked]
    if not threads:
        raise ValueError(f"在 {start_date} 到 {end_date} 之间没有题目")

    doc = Document()
    _setup_page(doc)

    doc.add_paragraph()

    for thread in threads:
        source_title = doc.add_paragraph(style='Heading 1')
        source_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        source_title_run = source_title.add_run(f"{thread['subject']}")
        source_title_run.bold = True
        try:
            source_title_run.font.size = Pt(20)
            source_title_run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        except Exception:
            pass
        doc.add_paragraph()

        questions = get_questions_by_thread(thread["thread_id"])
        blocks = get_blocks_by_thread(thread["thread_id"])

        image_marks = {}
        for q in questions:
            seq = q.get("seq", 0)
            for img in json.loads(q.get("images") or "[]"):
                if img:
                    key = os.path.normpath(os.path.abspath(img))
                    if key not in image_marks:
                        image_marks[key] = (seq, "配图")
            for ans in json.loads(q.get("answers") or "[]"):
                if ans:
                    key = os.path.normpath(os.path.abspath(ans))
                    image_marks[key] = (seq, "答案")

        in_answer_section = False
        for block in blocks:
            ctype = block.get("content_type")
            if ctype == 11:
                text = (block.get("text") or "").strip()
                if text:
                    if any(k in text for k in ["解答", "答案", "答：", "答:"]):
                        in_answer_section = True
                    first_line = next((s.strip() for s in text.splitlines() if s.strip()), "")
                    if re.match(r"^\d+[、\.\)]", first_line):
                        in_answer_section = False
                    p = doc.add_paragraph(text)
                    p.paragraph_format.space_after = Pt(6)
            elif ctype == 4:
                local = block.get("image_local")
                key = os.path.normpath(os.path.abspath(local)) if local else ""
                seq, mark = image_marks.get(key, (0, "图片"))
                answer_by_mark = mark == "答案"
                looks_like_question = False
                answer_by_ocr = False
                if local:
                    meta = analyze_image_text(local)
                    if isinstance(meta, dict) and (
                        meta.get("is_answer")
                        or any(k in str(meta.get("text_head") or "") for k in ["解答", "答案", "答：", "答:"])
                        or any(k in str(meta.get("text_full") or "")[:80] for k in ["解答", "答案", "答：", "答:"])
                    ):
                        answer_by_ocr = True
                    looks_like_question = bool(meta.get("looks_like_question")) if isinstance(meta, dict) else False
                if answer_by_mark:
                    # 明确标记为答案图片（来自 questions.answers）才跳过
                    in_answer_section = True
                    continue
                # 只要图片被标记为配图（或没有明确标记为答案），就显示
                # 不再依赖 OCR 判断来跳过，因为 OCR 判断可能不准确
                if in_answer_section and mark == "图片" and not looks_like_question:
                    # 只有在答案区域内的未分类图片才跳过
                    continue
                if local and os.path.exists(local):
                    shape = doc.add_picture(local)
                    if shape.width > LARGE_IMAGE_TRIGGER_WIDTH or shape.height > LARGE_IMAGE_TRIGGER_HEIGHT:
                        shape.width = int(shape.width * 0.5)
                        shape.height = int(shape.height * 0.5)
                    if shape.width > EXPORT_IMAGE_MAX_WIDTH or shape.height > EXPORT_IMAGE_MAX_HEIGHT:
                        ratio = min(float(EXPORT_IMAGE_MAX_WIDTH) / float(shape.width), float(EXPORT_IMAGE_MAX_HEIGHT) / float(shape.height))
                        shape.width = int(float(shape.width) * ratio)
                        shape.height = int(float(shape.height) * ratio)
                doc.add_paragraph()

        doc.add_page_break()

    # 保存文件
    if not output_path:
        date_list = [str(t.get("date_str") or "")[:10] for t in threads if t.get("date_str")]
        if date_list:
            start_day = min(date_list).replace("-", "")
            end_mmdd = max(date_list)[5:7] + max(date_list)[8:10]
        else:
            start_day = start_date.replace("-", "")
            end_mmdd = end_date[5:7] + end_date[8:10] if len(end_date) >= 10 else end_date.replace("-", "")
        filename = f"{start_day}-{end_mmdd}打卡题.docx"
        output_path = os.path.join(DATA_DIR, filename)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc.save(output_path)
    print(f"[Doc] 已生成：{output_path}")
    return output_path


def _setup_page(doc: Document):
    for section in doc.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2)


def _docx_to_pdf(docx_path: str, pdf_path: str) -> str:
    """Convert DOCX to PDF using Pandoc + Chrome headless."""
    import subprocess
    import shutil
    import tempfile
    import sys
    import os

    print("[Doc] 使用 Pandoc + Chrome 转换 (样式可能不完全一致)...")
    html_dir = tempfile.mkdtemp(prefix="shuati_doc_")
    html_path = os.path.join(html_dir, "output.html")

    # Convert DOCX to HTML using pandoc
    subprocess.run(
        ["pandoc", "--standalone", docx_path, "-o", html_path, "--extract-media=" + html_dir],
        check=True,
        capture_output=True,
    )

    # 注入 CSS 模拟 Word 样式
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        css = """
        <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: "Songti SC", "SimSun", "Times New Roman", serif;
            font-size: 13pt;
            line-height: 1.5;
            color: #000;
            margin: 0;
            padding: 0;
            max-width: none;
        }
        h1 {
            font-size: 24pt;
            text-align: center;
            color: #000;
            page-break-before: always;
            break-before: page;
            margin-top: 0;
            margin-bottom: 24pt;
        }
        h1:first-of-type {
            page-break-before: auto;
            break-before: auto;
        }
        p { margin-bottom: 6pt; text-align: justify; }
        img { max-width: 100%; height: auto; }
        .center { text-align: center; }
        </style>
        """
        html_content = html_content.replace("</head>", f"{css}</head>")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        print(f"[Doc] 注入 CSS 失败: {e}")

    # Convert HTML to PDF using Chrome headless
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/opt/homebrew/bin/chromium", 
        "/usr/bin/google-chrome"
    ]
    chrome = next((p for p in chrome_paths if os.path.exists(p)), chrome_paths[0])
    
    abs_pdf_path = os.path.abspath(pdf_path)
    subprocess.run(
        [
            chrome, 
            "--headless", 
            "--disable-gpu", 
            "--no-pdf-header-footer", 
            f"--print-to-pdf={abs_pdf_path}", 
            html_path
        ],
        check=True,
        capture_output=True,
        cwd=html_dir,
    )

    # Cleanup temp dir
    shutil.rmtree(html_dir)

    print(f"[Doc] 已转换：{pdf_path}")
    return pdf_path


def generate_pdf(start_date: str, end_date: str, output_path: str = None, source_thread_ids: list[str] | None = None) -> str:
    """Generate PDF document from questions."""
    final_pdf_path = output_path
    if output_path and output_path.lower().endswith(".pdf"):
        docx_output_path = output_path[:-4] + ".docx"
    else:
        docx_output_path = output_path
        final_pdf_path = None

    docx_path = generate_word(start_date, end_date, docx_output_path, source_thread_ids)

    if final_pdf_path is None:
        final_pdf_path = docx_path.replace(".docx", ".pdf")

    _docx_to_pdf(docx_path, final_pdf_path)
    return final_pdf_path
