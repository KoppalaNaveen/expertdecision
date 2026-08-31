import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf():
    pdf_path = "d:/ExpertDecisionPlatform/EDRP_User_Credentials_Confidential.pdf"

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        leftMargin=30,
        rightMargin=30,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#DC2626'),
        spaceAfter=8
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )

    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )

    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )

    cell_emp_id = ParagraphStyle(
        'CellEmpId',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#1E1B4B')
    )

    role_admin = ParagraphStyle('RAdmin', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#7C3AED'))
    role_mgr   = ParagraphStyle('RMgr',   parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#2563EB'))
    role_emp   = ParagraphStyle('REmp',   parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#059669'))
    role_rev   = ParagraphStyle('RRev',   parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#D97706'))

    pass_style = ParagraphStyle(
        'PassStyle',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#0369A1')
    )

    story = []

    # Title & Header
    story.append(Paragraph("Expert Decision Replay Platform (EDRP) — User Credentials Directory", title_style))
    story.append(Paragraph("CONFIDENTIAL &amp; RESTRICTED — AUTHORIZED ADMINISTRATOR ACCESS ONLY", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceAfter=6, spaceBefore=0))

    now_str = datetime.now().strftime("%B %d, %Y - %I:%M %p")
    story.append(Paragraph(f"<b>Generated:</b> {now_str} &nbsp;|&nbsp; <b>Total Accounts:</b> 19 &nbsp;|&nbsp; <b>Platform URL:</b> https://expertdecision.onrender.com", meta_style))
    story.append(Spacer(1, 8))

    # Complete 19 Users Table
    users_data = [
        {"id": 11, "name": "Reviewer",          "emp_id": "RW1300",    "role": "Reviewer",      "email": "reviewer@corp.com",               "designation": "Developer",                      "password": "password123"},
        {"id": 29, "name": "Naveen",            "emp_id": "EMP030120", "role": "Employee",      "email": "naveen@corp.com",                 "designation": "QA & Test Automation Lead",       "password": "ShabhanaaNaveen0320@"},
        {"id": 48, "name": "Koppala Naveen",    "emp_id": "AD030120",  "role": "Administrator", "email": "koppalanaveen@corp.com",          "designation": "Frontend Developer",              "password": "ShabhanaaNaveen0320@"},
        {"id": 59, "name": "Vaibhav Ingle",     "emp_id": "AD741074",  "role": "Administrator", "email": "vif804365@gmail.com",             "designation": "DevOps & SRE Specialist",        "password": "password123"},
        {"id": 60, "name": "anjali",            "emp_id": "EMP789456", "role": "Employee",      "email": "anjalipalli437@gmail.com",        "designation": "Team Member",                    "password": "password123"},
        {"id": 62, "name": "Naga Sai",          "emp_id": "MN198230",  "role": "Manager",       "email": "nagasai@corp.com",                "designation": "Frontend Developer",              "password": "Nagasai#07"},
        {"id": 63, "name": "Kamakshi Medisetty", "emp_id": "RW937213", "role": "Reviewer",      "email": "rd5860447@gmail.com",             "designation": "Reviewer Specialist",            "password": "password123"},
        {"id": 64, "name": "Akhila Kothapalli", "emp_id": "AD000001",  "role": "Administrator", "email": "kothapalliakhila6851@gmail.com", "designation": "Platform Administrator",        "password": "Akhila@6"},
        {"id": 71, "name": "Afsana Honey",      "emp_id": "MN987456",  "role": "Manager",       "email": "afsana.honey@corp.com",           "designation": "Manager Lead",                   "password": "password123"},
        {"id": 77, "name": "Test Employee",     "emp_id": "RW030120",  "role": "Reviewer",      "email": "test.employee@corp.com",          "designation": "Cybersecurity Analyst",           "password": "ShabhanaaNaveen0320@"},
        {"id": 78, "name": "Employee Akhila",   "emp_id": "EMP000001", "role": "Employee",      "email": "akhila.emp@corp.com",             "designation": "Technical Team Lead",             "password": "Akhila@6"},
        {"id": 79, "name": "Reviewer Akhila",   "emp_id": "RW000001",  "role": "Reviewer",      "email": "akhila.rev@corp.com",             "designation": "Review Board Member",             "password": "Akhila@6"},
        {"id": 80, "name": "Manager Akhila",    "emp_id": "MN000001",  "role": "Manager",       "email": "akhila.mgr@corp.com",             "designation": "Operations Manager",              "password": "Akhila@6"},
        {"id": 81, "name": "Abhineswar",        "emp_id": "EMP101105", "role": "Employee",      "email": "abhineswar@corp.com",             "designation": "Team Member",                    "password": "Naveen0320@"},
        {"id": 82, "name": "Narasimha",         "emp_id": "EMP110705", "role": "Employee",      "email": "narasimha@corp.com",              "designation": "Team Member",                    "password": "Narasimha@11"},
        {"id": 84, "name": "Kambham Reddy",     "emp_id": "EMP101104", "role": "Employee",      "email": "kambham.reddy@corp.com",          "designation": "Team Member",                    "password": "Abhineswar@123"},
        {"id": 85, "name": "Mounish",           "emp_id": "RW150206",  "role": "Reviewer",      "email": "mounish@corp.com",                "designation": "QA & Test Verification Reviewer", "password": "Mounish@123"},
        {"id": 86, "name": "Koppala Manasa",    "emp_id": "EMP010320", "role": "Employee",      "email": "manasa.koppala@corp.com",         "designation": "Data Analyst",                    "password": "KoppalaNaveen0320@"},
        {"id": 87, "name": "shana",             "emp_id": "EMP333333", "role": "Employee",      "email": "shana@corp.com",                  "designation": "Frontend Developer",              "password": "password123"}
    ]

    table_data = [
        [
            Paragraph("<b>#</b>", cell_bold),
            Paragraph("<b>Emp ID</b>", cell_bold),
            Paragraph("<b>Full Name</b>", cell_bold),
            Paragraph("<b>Assigned Role</b>", cell_bold),
            Paragraph("<b>Designation</b>", cell_bold),
            Paragraph("<b>Registered Email / Username</b>", cell_bold),
            Paragraph("<b>Original Password</b>", cell_bold)
        ]
    ]

    for idx, u in enumerate(users_data, 1):
        r_name = u["role"]
        if r_name == "Administrator":
            r_st = role_admin
        elif r_name == "Manager":
            r_st = role_mgr
        elif r_name == "Reviewer":
            r_st = role_rev
        else:
            r_st = role_emp

        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(f"<b>{u['emp_id']}</b>", cell_emp_id),
            Paragraph(u["name"], cell_bold),
            Paragraph(r_name, r_st),
            Paragraph(u["designation"], cell_style),
            Paragraph(u["email"], cell_style),
            Paragraph(f"<code>{u['password']}</code>", pass_style)
        ])

    # 732 printable width
    col_widths = [22, 75, 120, 85, 140, 160, 130]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)

    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))

    story.append(t)
    story.append(Spacer(1, 8))

    # Notes
    note_body = ParagraphStyle('NoteBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#475569'))
    story.append(Paragraph("<b>Authentication Guide:</b> Users can log into the platform at <code>https://expertdecision.onrender.com/login</code> using either their <b>Employee ID</b> (e.g. <code>AD030120</code>, <code>MN198230</code>, <code>RW1300</code>) and Password. Passwords can also be updated directly from the Administrator User Management console.", note_body))

    doc.build(story)
    print(f"Successfully generated PDF: {pdf_path} (Size: {os.path.getsize(pdf_path)} bytes)")

if __name__ == "__main__":
    generate_pdf()
