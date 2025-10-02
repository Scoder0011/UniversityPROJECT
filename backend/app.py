
from flask import Flask, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import tempfile
from pathlib import Path
from datetime import datetime

# Document processing libraries
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt
from PyPDF2 import PdfMerger, PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from PIL import Image
import io

app = Flask(__name__)
CORS(app)


ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'pptx', 'ppt', 'txt', 'jpg', 'jpeg', 'png', 'gif'}
TEMP_DIR = tempfile.gettempdir()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['pdf']:
        return 'pdf'
    elif ext in ['docx', 'doc']:
        return 'docx'
    elif ext in ['pptx', 'ppt']:
        return 'pptx'
    elif ext in ['txt']:
        return 'txt'
    elif ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'image'
    return 'unknown'

# CONVERTERS TO INTERMEDIATE FORMAT

def docx_to_text_with_formatting(docx_path):
    """Extract text with basic formatting info from DOCX"""
    doc = Document(docx_path)
    content = []
    
    for para in doc.paragraphs:
        if para.text.strip():
            content.append({
                'text': para.text,
                'style': para.style.name,
                'alignment': para.alignment
            })
    
    # Extract tables
    for table in doc.tables:
        table_data = []
        for row in table.rows:
            row_data = [cell.text for cell in row.cells]
            table_data.append(row_data)
        if table_data:
            content.append({'table': table_data})
    
    return content

def pptx_to_text(pptx_path):
    """Extract text from PPTX"""
    prs = Presentation(pptx_path)
    content = []
    
    for slide_num, slide in enumerate(prs.slides, 1):
        slide_content = {'slide_num': slide_num, 'shapes': []}
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                slide_content['shapes'].append(shape.text)
        content.append(slide_content)
    
    return content

def txt_to_text(txt_path):
    """Read text file"""
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def image_to_pdf(image_path, output_pdf):
    """Convert image to PDF properly"""
    img = Image.open(image_path)
    
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    
    # Save as PDF
    img.save(output_pdf, 'PDF', resolution=100.0, quality=95)

def text_to_pdf(text, output_pdf):
    """Convert plain text to PDF with formatting"""
    doc = SimpleDocTemplate(output_pdf, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    for line in text.split('\n'):
        if line.strip():
            story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
    
    doc.build(story)

def docx_to_pdf(docx_path, output_pdf):
    """Convert DOCX to PDF preserving formatting, images, and tables"""
    try:
        # Try using LibreOffice for high-quality conversion
        import subprocess
        
        # Check if LibreOffice is available
        libreoffice_commands = [
            'libreoffice',  # Linux
            'soffice',      # Alternative Linux
            '/Applications/LibreOffice.app/Contents/MacOS/soffice',  # macOS
            'C:\\Program Files\\LibreOffice\\program\\soffice.exe',  # Windows
            'C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe'  # Windows 32-bit
        ]
        
        libreoffice_path = None
        for cmd in libreoffice_commands:
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, 
                                      timeout=5,
                                      text=True,
                                      stdin=subprocess.DEVNULL)  # Prevent stdin prompts
                if result.returncode == 0:
                    libreoffice_path = cmd
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        if libreoffice_path:
            # Use LibreOffice for conversion (best quality)
            output_dir = os.path.dirname(output_pdf)
            
            # Full headless conversion with all safety flags
            result = subprocess.run(
                [
                    libreoffice_path,
                    '--headless',                    # No GUI
                    '--invisible',                   # Don't show window
                    '--nocrashreport',              # Disable crash reporting
                    '--nodefault',                  # Don't start with default document
                    '--nofirststartwizard',         # Skip first-start wizard
                    '--nolockcheck',                # Don't check for file locks
                    '--nologo',                     # Don't show splash screen
                    '--norestore',                  # Don't restore windows
                    '--convert-to', 'pdf',
                    '--outdir', output_dir,
                    docx_path
                ],
                capture_output=True,
                timeout=60,
                stdin=subprocess.DEVNULL,           # No stdin input
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0  # Windows: no console window
            )
            
            # LibreOffice creates PDF with same name as DOCX
            base_name = os.path.splitext(os.path.basename(docx_path))[0]
            temp_pdf = os.path.join(output_dir, f"{base_name}.pdf")
            
            if os.path.exists(temp_pdf):
                os.rename(temp_pdf, output_pdf)
                print(f"✓ LibreOffice conversion successful: {os.path.basename(docx_path)}")
                return
            else:
                print(f"⚠ LibreOffice conversion failed, using fallback")
        
    except Exception as e:
        print(f"⚠ LibreOffice conversion error: {e}, using fallback")
    
    # Fallback: Manual conversion with python-docx + reportlab
    print(f"→ Using manual conversion for: {os.path.basename(docx_path)}")
    try:
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        
        doc = SimpleDocTemplate(output_pdf, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=6
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=14,
            textColor='#1a1a1a',
            spaceAfter=12,
            spaceBefore=12
        )
        
        source_doc = Document(docx_path)
        
        # Process paragraphs and extract images
        for para in source_doc.paragraphs:
            if para.text.strip():
                if 'Heading' in para.style.name:
                    story.append(Paragraph(para.text, heading_style))
                else:
                    story.append(Paragraph(para.text, normal_style))
            
            # Check for inline images in runs
            for run in para.runs:
                if 'graphicData' in run._element.xml:
                    # Try to extract embedded image
                    try:
                        for rel in run.part.rels.values():
                            if "image" in rel.target_ref:
                                image_data = rel.target_part.blob
                                img = Image.open(io.BytesIO(image_data))
                                
                                # Resize if needed
                                max_width = 6 * inch
                                max_height = 8 * inch
                                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                                
                                img_buffer = io.BytesIO()
                                img.save(img_buffer, format='PNG')
                                img_buffer.seek(0)
                                
                                story.append(Spacer(1, 0.1 * inch))
                                story.append(RLImage(img_buffer, width=img.size[0], height=img.size[1]))
                                story.append(Spacer(1, 0.1 * inch))
                    except Exception as e:
                        print(f"Error extracting inline image: {e}")
        
        # Process tables with better formatting
        for table in source_doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)
            
            if table_data:
                # Create reportlab table
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(Spacer(1, 0.2 * inch))
                story.append(t)
                story.append(Spacer(1, 0.2 * inch))
        
        # Extract all images from document
        for rel in source_doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    image_data = rel.target_part.blob
                    img = Image.open(io.BytesIO(image_data))
                    
                    # Resize if needed
                    max_width = 6 * inch
                    max_height = 8 * inch
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    story.append(Spacer(1, 0.2 * inch))
                    story.append(RLImage(img_buffer, width=img.size[0], height=img.size[1]))
                    story.append(Spacer(1, 0.2 * inch))
                except Exception as e:
                    print(f"Error processing image: {e}")
        
        doc.build(story)
        print(f"✓ Manual conversion successful: {os.path.basename(docx_path)}")
        
    except Exception as e:
        print(f"✗ Manual DOCX conversion failed: {e}")
        raise

def pptx_to_pdf(pptx_path, output_pdf):
    """Convert PPTX to PDF"""
    doc = SimpleDocTemplate(output_pdf, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    slide_title_style = ParagraphStyle(
        'SlideTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='#2c3e50',
        spaceAfter=12,
        alignment=1  # Center
    )
    
    prs = Presentation(pptx_path)
    
    for slide_num, slide in enumerate(prs.slides, 1):
        # Slide number
        story.append(Paragraph(f"Slide {slide_num}", slide_title_style))
        story.append(Spacer(1, 0.2 * inch))
        
        # Extract text from shapes
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                story.append(Paragraph(shape.text, styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
        
        # Page break between slides
        if slide_num < len(prs.slides):
            story.append(PageBreak())
    
    doc.build(story)

# COMBINERS FOR DIFFERENT OUTPUT FORMATS

def combine_to_pdf(files, output_path):
    """Combine all files into a PDF - PRESERVING ORIGINAL PDF FORMATTING"""
    merger = PdfMerger()
    temp_pdfs = []
    
    try:
        for idx, file_info in enumerate(files):
            file_path = file_info['path']
            file_type = file_info['type']
            filename = file_info['name']
            
            if file_type == 'pdf':
                # For PDFs, merge directly without conversion to preserve formatting
                merger.append(file_path)
            
            else:
                # For non-PDF files, convert to PDF first
                temp_pdf = os.path.join(TEMP_DIR, f"temp_{idx}_{datetime.now().timestamp()}.pdf")
                temp_pdfs.append(temp_pdf)
                
                try:
                    if file_type == 'image':
                        image_to_pdf(file_path, temp_pdf)
                    elif file_type == 'txt':
                        text = txt_to_text(file_path)
                        text_to_pdf(text, temp_pdf)
                    elif file_type == 'docx':
                        docx_to_pdf(file_path, temp_pdf)
                    elif file_type == 'pptx':
                        pptx_to_pdf(file_path, temp_pdf)
                    
                    # Append the converted PDF
                    merger.append(temp_pdf)
                
                except Exception as e:
                    print(f"Error converting {filename}: {e}")
                    # Create error page
                    error_pdf = os.path.join(TEMP_DIR, f"error_{idx}.pdf")
                    temp_pdfs.append(error_pdf)
                    c = canvas.Canvas(error_pdf, pagesize=letter)
                    c.setFont("Helvetica", 12)
                    c.drawString(100, 750, f"Error processing file: {filename}")
                    c.drawString(100, 730, f"Error: {str(e)}")
                    c.save()
                    merger.append(error_pdf)
        
        # Write the merged PDF
        merger.write(output_path)
        merger.close()
    
    finally:
        # Cleanup temporary PDFs
        for temp_pdf in temp_pdfs:
            try:
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
            except:
                pass

def combine_to_docx(files, output_path):
    """Combine all files into a DOCX"""
    doc = Document()
    
    # Add title
    title = doc.add_heading('Combined Document', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    for idx, file_info in enumerate(files):
        file_path = file_info['path']
        file_type = file_info['type']
        filename = file_info['name']
        
        # Add file header
        heading = doc.add_heading(f'File {idx + 1}: {filename}', level=1)
        heading_para = heading.runs[0]
        heading_para.font.color.rgb = RGBColor(102, 126, 234)
        
        try:
            if file_type == 'pdf':
                reader = PdfReader(file_path)
                for page_num, page in enumerate(reader.pages):
                    doc.add_heading(f'Page {page_num + 1}', level=2)
                    text = page.extract_text()
                    if text.strip():
                        # Preserve line breaks
                        for para in text.split('\n'):
                            if para.strip():
                                doc.add_paragraph(para)
            
            elif file_type == 'docx':
                source_doc = Document(file_path)
                
                # Copy paragraphs
                for para in source_doc.paragraphs:
                    if para.text.strip():
                        new_para = doc.add_paragraph(para.text)
                        # Try to preserve some formatting
                        if para.style.name.startswith('Heading'):
                            new_para.style = para.style.name
                
                # Copy tables
                for table in source_doc.tables:
                    # Create new table
                    new_table = doc.add_table(rows=len(table.rows), cols=len(table.columns))
                    new_table.style = 'Light Grid Accent 1'
                    
                    for i, row in enumerate(table.rows):
                        for j, cell in enumerate(row.cells):
                            new_table.rows[i].cells[j].text = cell.text
            
            elif file_type == 'pptx':
                content = pptx_to_text(file_path)
                for slide_info in content:
                    doc.add_heading(f"Slide {slide_info['slide_num']}", level=2)
                    for shape_text in slide_info['shapes']:
                        doc.add_paragraph(shape_text)
            
            elif file_type == 'txt':
                text = txt_to_text(file_path)
                for line in text.split('\n'):
                    if line.strip():
                        doc.add_paragraph(line)
            
            elif file_type == 'image':
                try:
                    doc.add_picture(file_path, width=Inches(6))
                except Exception as e:
                    doc.add_paragraph(f'[Image: {filename}]')
        
        except Exception as e:
            doc.add_paragraph(f'Error processing this file: {str(e)}')
        
        # Add page break between files
        if idx < len(files) - 1:
            doc.add_page_break()
    
    doc.save(output_path)

def combine_to_pptx(files, output_path):
    """Combine all files into a PPTX"""
    prs = Presentation()
    prs.slide_width = PptxInches(10)
    prs.slide_height = PptxInches(7.5)
    
    # Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    title.text = "Combined Presentation"
    subtitle.text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    for idx, file_info in enumerate(files):
        file_path = file_info['path']
        file_type = file_info['type']
        filename = file_info['name']
        
        # Add section slide
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        title = slide.shapes.title
        title.text = f'File {idx + 1}: {filename}'
        
        try:
            if file_type == 'pdf':
                reader = PdfReader(file_path)
                for page_num, page in enumerate(reader.pages):
                    slide = prs.slides.add_slide(prs.slide_layouts[5])
                    
                    left = top = PptxInches(0.5)
                    width = PptxInches(9)
                    height = PptxInches(6.5)
                    
                    txBox = slide.shapes.add_textbox(left, top, width, height)
                    tf = txBox.text_frame
                    tf.word_wrap = True
                    tf.text = f"Page {page_num + 1}\n\n"
                    
                    text = page.extract_text()
                    if text.strip():
                        tf.text += text[:2000]  # Increased limit
            
            elif file_type == 'docx':
                content = docx_to_text_with_formatting(file_path)
                slide = prs.slides.add_slide(prs.slide_layouts[5])
                
                left = top = PptxInches(0.5)
                width = PptxInches(9)
                height = PptxInches(6.5)
                
                txBox = slide.shapes.add_textbox(left, top, width, height)
                tf = txBox.text_frame
                tf.word_wrap = True
                
                text_content = []
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        text_content.append(item['text'])
                
                tf.text = '\n'.join(text_content)[:2000]
            
            elif file_type == 'pptx':
                source_prs = Presentation(file_path)
                # Copy slides directly
                for source_slide in source_prs.slides:
                    # Create new slide
                    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
                    
                    # Copy shapes
                    for shape in source_slide.shapes:
                        if hasattr(shape, "text") and shape.text:
                            left = PptxInches(0.5)
                            top = PptxInches(0.5)
                            width = PptxInches(9)
                            height = PptxInches(6.5)
                            
                            txBox = slide.shapes.add_textbox(left, top, width, height)
                            tf = txBox.text_frame
                            tf.text = shape.text
            
            elif file_type == 'txt':
                text = txt_to_text(file_path)
                slide = prs.slides.add_slide(prs.slide_layouts[5])
                
                left = top = PptxInches(0.5)
                width = PptxInches(9)
                height = PptxInches(6.5)
                
                txBox = slide.shapes.add_textbox(left, top, width, height)
                tf = txBox.text_frame
                tf.word_wrap = True
                tf.text = text[:2000]
            
            elif file_type == 'image':
                slide = prs.slides.add_slide(prs.slide_layouts[6])
                
                img = Image.open(file_path)
                img_width, img_height = img.size
                
                max_width = PptxInches(9)
                max_height = PptxInches(6.5)
                
                aspect = img_width / img_height
                if img_width > img_height:
                    width = max_width
                    height = width / aspect
                else:
                    height = max_height
                    width = height * aspect
                
                left = (prs.slide_width - width) / 2
                top = (prs.slide_height - height) / 2
                
                slide.shapes.add_picture(file_path, left, top, width, height)
        
        except Exception as e:
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            left = top = PptxInches(1)
            width = PptxInches(8)
            height = PptxInches(5)
            
            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = f'Error processing this file: {str(e)}'
    
    prs.save(output_path)

@app.route('/combine', methods=['POST'])
def combine_files():
    """Main endpoint to combine files"""
    if 'files' not in request.files:
        return {'error': 'No files uploaded'}, 400
    
    files = request.files.getlist('files')
    output_format = request.form.get('output_format', 'pdf')
    
    if not files or files[0].filename == '':
        return {'error': 'No files selected'}, 400
    
    # Validate files
    for file in files:
        if not allowed_file(file.filename):
            return {'error': f'File type not allowed: {file.filename}'}, 400
    
    # Save uploaded files temporarily
    temp_files = []
    output_path = None
    
    try:
        for file in files:
            filename = secure_filename(file.filename)
            temp_path = os.path.join(TEMP_DIR, f"{datetime.now().timestamp()}_{filename}")
            file.save(temp_path)
            
            temp_files.append({
                'path': temp_path,
                'name': filename,
                'type': get_file_type(filename)
            })
        
        # Create output file
        output_filename = f'combined_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{output_format}'
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        # Combine based on output format
        if output_format == 'pdf':
            combine_to_pdf(temp_files, output_path)
        elif output_format == 'docx':
            combine_to_docx(temp_files, output_path)
        elif output_format == 'pptx':
            combine_to_pptx(temp_files, output_path)
        else:
            return {'error': 'Invalid output format'}, 400
        
        # Send file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype=f'application/{output_format}'
        )
        
        return response
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error: {error_details}")
        return {'error': str(e), 'details': error_details}, 500
    
    finally:
        # Cleanup temporary files
        for file_info in temp_files:
            try:
                if os.path.exists(file_info['path']):
                    os.remove(file_info['path'])
            except:
                pass 
import json
import time
from PyPDF2 import PdfMerger
from reportlab.pdfgen import canvas

def create_divider_pdf(title, output_path):
    """Create a one-page divider PDF with title and timestamp."""
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 2 * inch, title)
    c.setFont("Helvetica", 10)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.drawCentredString(width / 2, height - 2 * inch - 20, f"Generated: {timestamp}")
    c.showPage()
    c.save()

@app.route('/combine-checklist', methods=['POST'])
def combine_checklist():
    """
    Expect form-data:
      - 'checklist_data': JSON array [{name: "...", files: ["checklist_0_file_0", ...]}, ...]
      - files uploaded under keys referenced in checklist_data
    """
    if 'checklist_data' not in request.form:
        return {'error': 'Missing checklist_data'}, 400

    try:
        checklist_data = json.loads(request.form['checklist_data'])
    except Exception as e:
        return {'error': 'Invalid checklist_data JSON', 'details': str(e)}, 400

    merger = PdfMerger()
    temp_to_cleanup = []       # raw uploads + divider PDFs + converted PDFs

    try:
        # Build ordered list and append to merger as we go
        for sec_idx, checklist in enumerate(checklist_data):
            section_name = checklist.get('name') or f"Section {sec_idx+1}"

            # 1) Divider page
            divider_fp = os.path.join(TEMP_DIR, f"divider_{int(time.time()*1000)}_{sec_idx}.pdf")
            create_divider_pdf(section_name, divider_fp)
            temp_to_cleanup.append(divider_fp)
            merger.append(divider_fp)

            # 2) Process files for this section in the provided order
            for file_key in checklist.get('files', []):
                if file_key not in request.files:
                    print(f"Warning: missing file key {file_key}")
                    # Insert a warning page so order is preserved
                    warn_fp = os.path.join(TEMP_DIR, f"warn_{int(time.time()*1000)}.pdf")
                    c = canvas.Canvas(warn_fp, pagesize=letter)
                    c.setFont("Helvetica", 12)
                    c.drawString(60, 750, f"Missing file for: {file_key}")
                    c.save()
                    temp_to_cleanup.append(warn_fp)
                    merger.append(warn_fp)
                    continue

                fs = request.files[file_key]
                if fs.filename == '':
                    # skip empty
                    continue

                if not allowed_file(fs.filename):
                    # create error page and append
                    err_fp = os.path.join(TEMP_DIR, f"not_allowed_{int(time.time()*1000)}.pdf")
                    c = canvas.Canvas(err_fp, pagesize=letter)
                    c.setFont("Helvetica", 12)
                    c.drawString(60, 750, f"File type not allowed: {fs.filename}")
                    c.save()
                    temp_to_cleanup.append(err_fp)
                    merger.append(err_fp)
                    continue

                # Save original uploaded file
                safe_name = secure_filename(fs.filename)
                saved_raw = os.path.join(TEMP_DIR, f"{int(time.time()*1000)}_{safe_name}")
                fs.save(saved_raw)
                temp_to_cleanup.append(saved_raw)

                # Determine type and convert if needed
                ftype = get_file_type(safe_name)
                try:
                    if ftype == 'pdf':
                        merger.append(saved_raw)
                    else:
                        # create a temp pdf path to hold converted result
                        converted_pdf = os.path.join(TEMP_DIR, f"converted_{int(time.time()*1000)}.pdf")
                        # Route to appropriate converter (these functions exist in your app)
                        if ftype == 'image':
                            image_to_pdf(saved_raw, converted_pdf)
                        elif ftype == 'txt':
                            text = txt_to_text(saved_raw)
                            text_to_pdf(text, converted_pdf)
                        elif ftype == 'docx':
                            # try using your docx_to_pdf which prefers LibreOffice, fallback exists
                            docx_to_pdf(saved_raw, converted_pdf)
                        elif ftype == 'pptx':
                            pptx_to_pdf(saved_raw, converted_pdf)
                        else:
                            # unknown types -> create placeholder PDF
                            c = canvas.Canvas(converted_pdf, pagesize=letter)
                            c.setFont("Helvetica", 12)
                            c.drawString(60, 750, f"[{safe_name}] - unsupported type, could not convert.")
                            c.save()

                        # Append converted PDF
                        temp_to_cleanup.append(converted_pdf)
                        merger.append(converted_pdf)

                except Exception as conv_err:
                    # Conversion failed — insert an error page to preserve order
                    error_pdf = os.path.join(TEMP_DIR, f"conv_error_{int(time.time()*1000)}.pdf")
                    c = canvas.Canvas(error_pdf, pagesize=letter)
                    c.setFont("Helvetica", 12)
                    c.drawString(60, 750, f"Error converting file: {safe_name}")
                    c.drawString(60, 730, f"Error: {str(conv_err)}")
                    c.save()
                    temp_to_cleanup.append(error_pdf)
                    merger.append(error_pdf)
                    print(f"Conversion error for {safe_name}:", conv_err)

        # Write merged output
        output_filename = f'checklist_combined_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        output_path = os.path.join(TEMP_DIR, output_filename)
        merger.write(output_path)
        merger.close()

        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        import traceback
        print("ERROR in /combine-checklist:", traceback.format_exc())
        return {'error': str(e)}, 500

    finally:
        # cleanup raw files, converters, dividers (NOT the final output which we returned already)
        for p in temp_to_cleanup:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API info"""
    return {
        'service': 'Universal File Combiner API',
        'version': '2.0.0',
        'endpoints': {
            '/combine': 'POST - Combine multiple files (preserves PDF formatting)',
            '/health': 'GET - Health check'
        },
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'output_formats': ['pdf', 'docx', 'pptx'],
        'features': [
            'Preserves original PDF formatting (tables, layouts, fonts)',
            'Direct PDF merging without text extraction',
            'Smart conversion for other formats'
        ]
    }
import os, sys, subprocess

def docx_to_pdf(input_path, output_path):
    """Convert DOCX to PDF using LibreOffice headless mode (no terminal popups)."""
    soffice = r"C:\Program Files\LibreOffice\program\soffice.exe"  # adjust if your path is different
    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        "--invisible",
        "--convert-to", "pdf",
        "--outdir", os.path.dirname(output_path),
        input_path
    ]
    # prevent "Press Enter to continue" windows on Windows
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run(cmd, check=True, creationflags=creationflags)
    # output will be created automatically by LibreOffice in the outdir
    # ensure it's at expected location
    generated_pdf = os.path.join(os.path.dirname(output_path),
                                 os.path.splitext(os.path.basename(input_path))[0] + ".pdf")
    if os.path.exists(generated_pdf):
        os.replace(generated_pdf, output_path)

def pptx_to_pdf(input_path, output_path):
    """Convert PPTX to PDF using LibreOffice headless mode (no terminal popups)."""
    soffice = r"C:\Program Files\LibreOffice\program\soffice.exe"  # adjust path if needed
    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        "--invisible",
        "--convert-to", "pdf",
        "--outdir", os.path.dirname(output_path),
        input_path
    ]
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.run(cmd, check=True, creationflags=creationflags)
    generated_pdf = os.path.join(os.path.dirname(output_path),
                                 os.path.splitext(os.path.basename(input_path))[0] + ".pdf")
    if os.path.exists(generated_pdf):
        os.replace(generated_pdf, output_path)



    

if __name__ == '__main__':
    print("=" * 60)
    print("Universal File Combiner Backend v2.0")
    print("=" * 60)
    port = int(os.environ.get("PORT", 5000))  # use Render's PORT, fallback to 5000 locally
    app.run(debug=False, host='0.0.0.0', port=port)
