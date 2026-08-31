import os
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

def create_credentials_pdf():
    pdf_path = "d:/ExpertDecisionPlatform/EDRP_User_Credentials_Confidential.pdf"
    
    # Read database records
    db_path = "d:/ExpertDecisionPlatform/backend/edrp.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, role_name FROM roles")
    roles = dict(cur.fetchall())

    cur.execute("SELECT id, full_name, employee_id, role_id, email_original, email, status, is_active FROM users ORDER BY role_id, employee_id")
    users = cur.fetchall()
    conn.close()

    # Create document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#DC2626'),
        spaceAfter=10
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )

    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )

    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    role_admin_style = ParagraphStyle(
        'RoleAdmin',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#7C3AED')
    )
    
    role_mgr_style = ParagraphStyle(
        'RoleMgr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#2563EB')
    )

    role_emp_style = ParagraphStyle(
        'RoleEmp',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#059669')
    )

    role_rev_style = ParagraphStyle(
        'RoleRev',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#D97706')
    )

    pass_style = ParagraphStyle(
        'PassStyle',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#0284C7')
    )

    story = []

    # Title & Header
    story.append(Paragraph("Expert Decision Replay Platform (EDRP)", title_style))
    story.append(Paragraph("CONFIDENTIAL & RESTRICTED — AUTHORIZED ADMINISTRATOR ACCESS ONLY", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceAfter=8, spaceBefore=0))
    
    now_str = datetime.now().strftime("%B %d, %Y - %I:%M %p")
    story.append(Paragraph(f"<b>Document Generated:</b> {now_str} &nbsp;|&nbsp; <b>Total Registered User Accounts:</b> {len(users)} &nbsp;|&nbsp; <b>Platform URL:</b> https://expertdecision.onrender.com", meta_style))
    story.append(Spacer(1, 10))

    # Table Data
    table_data = [
        [
            Paragraph("<b>#</b>", cell_bold),
            Paragraph("<b>Employee ID</b>", cell_bold),
            Paragraph("<b>Full Name</b>", cell_bold),
            Paragraph("<b>Assigned Role</b>", cell_bold),
            Paragraph("<b>Registered Email / Username</b>", cell_bold),
            Paragraph("<b>Status</b>", cell_bold),
            Paragraph("<b>Login Password</b>", cell_bold)
        ]
    ]

    for idx, u in enumerate(users, 1):
        uid, name, emp_id, role_id, email_orig, email_h, status, is_act = u
        role_name = roles.get(role_id, "Employee")
        email = email_orig if email_orig else email_h

        # Style based on role
        if role_name == "Administrator":
            r_st = role_admin_style
        elif role_name == "Manager":
            r_st = role_mgr_style
        elif role_name == "Reviewer":
            r_st = role_rev_style
        else:
            r_st = role_emp_style

        # Password
        # Default system password for seeded users is password123
        pwd_text = "password123"

        status_display = "Active" if status == "Active" or is_act else "Inactive"
        status_color = "#059669" if status_display == "Active" else "#DC2626"
        status_p = Paragraph(f"<font color='{status_color}'><b>{status_display}</b></font>", cell_style)

        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(f"<b>{emp_id}</b>", cell_bold),
            Paragraph(name, cell_style),
            Paragraph(role_name, r_st),
            Paragraph(email, cell_style),
            status_p,
            Paragraph(pwd_text, pass_style)
        ])

    # 720pt printable width on landscape letter (792 - 72 = 720)
    col_widths = [26, 85, 140, 100, 185, 64, 120]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    story.append(t)
    story.append(Spacer(1, 14))

    # Notes section
    note_title = ParagraphStyle('NoteTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#0F172A'))
    note_body = ParagraphStyle('NoteBody', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#475569'))

    story.append(Paragraph("<b>Security & Password Information Notes:</b>", note_title))
    story.append(Paragraph("1. <b>Standard Password:</b> All standard and seeded accounts use the default password <code>password123</code> for login authentication.", note_body))
    story.append(Paragraph("2. <b>Authentication Format:</b> Users can log in using their assigned <b>Employee ID</b> (e.g., <code>AD030120</code>, <code>MN1297</code>, <code>EMP8749</code>, <code>RW1300</code>) and Password.", note_body))
    story.append(Paragraph("3. <b>Password Hashing:</b> Passwords are cryptographically protected in the database using one-way <code>bcrypt</code> hashing (cost factor 12) in compliance with enterprise security governance.", note_body))
    story.append(Paragraph("4. <b>Password Reset:</b> If any user has modified their password or forgotten it, an Administrator can reset it directly from the <b>User Management</b> console or via 6-digit Email OTP.", note_body))

    # Build PDF
    doc.build(story)
    print(f"Successfully created PDF: {pdf_path} (Size: {os.path.getsize(pdf_path)} bytes)")

if __name__ == "__main__":
    create_credentials_pdf()
