import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)

def create_project_pdf():
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AI_Attendance_System_Documentation.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    COLOR_PRIMARY = colors.HexColor("#0f172a")    # Deep Slate
    COLOR_CYAN = colors.HexColor("#0891b2")       # Cyan
    COLOR_EMERALD = colors.HexColor("#059669")    # Emerald Green
    COLOR_TEXT = colors.HexColor("#1e293b")       # Dark Charcoal
    COLOR_MUTED = colors.HexColor("#64748b")      # Slate Muted
    COLOR_BG_LIGHT = colors.HexColor("#f8fafc")   # Off-white
    COLOR_BORDER = colors.HexColor("#cbd5e1")     # Light Border

    # Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=COLOR_PRIMARY,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=COLOR_CYAN,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=COLOR_PRIMARY,
        spaceBefore=12,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=COLOR_CYAN,
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=COLOR_TEXT,
        spaceAfter=6
    )

    body_bold = ParagraphStyle(
        'Body_Bold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=body_style,
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=COLOR_TEXT
    )

    story = []

    # Document Header
    story.append(Paragraph("Face Attendance AI", title_style))
    story.append(Paragraph("Production-Ready AI Face Recognition Attendance System — Project Documentation", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=COLOR_CYAN, spaceAfter=14))

    # Section 1: Executive Summary
    story.append(Paragraph("1. Executive Summary & Problem Statement", h1_style))
    story.append(Paragraph(
        "Traditional attendance methods like paper registers, RFID cards, or fingerprint scanners suffer from critical drawbacks: "
        "they are time-consuming, prone to 'buddy punching' (proxy attendance), and unhygienic in post-pandemic work environments. "
        "<b>Face Attendance AI</b> is an automated, contactless attendance solution combining Computer Vision, Deep Learning, and "
        "a high-performance Web application to identify faces in real-time, log timestamps, prevent duplicate entries, and visualize analytics.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Section 2: Technology Stack
    story.append(Paragraph("2. Complete Technology Stack", h1_style))
    
    tech_data = [
        [Paragraph("<b>Component</b>", body_bold), Paragraph("<b>Technology / Library</b>", body_bold), Paragraph("<b>Key Responsibility & Justification</b>", body_bold)],
        [
            Paragraph("<b>Backend Server</b>", body_style),
            Paragraph("Python 3.14 + FastAPI + Uvicorn", body_style),
            Paragraph("High-performance asynchronous REST API, WebSockets handler, static file server, and background processing.", body_style)
        ],
        [
            Paragraph("<b>Computer Vision & AI</b>", body_style),
            Paragraph("OpenCV + Face Recognition", body_style),
            Paragraph("Extracts 128-dimensional deep facial landmarks, calculates Euclidean metric distance, and verifies identities.", body_style)
        ],
        [
            Paragraph("<b>Web Frontend (SPA)</b>", body_style),
            Paragraph("HTML5 + Vanilla CSS3 + JavaScript", body_style),
            Paragraph("Cyber-luxe glassmorphic dashboard, responsive layout, theme toggle (Dark/Light), zero bulky frontend build dependencies.", body_style)
        ],
        [
            Paragraph("<b>Live Video & HUD</b>", body_style),
            Paragraph("HTML5 WebRTC + Canvas API", body_style),
            Paragraph("Browser-level 60 FPS live video stream, dynamic corner reticles, laser scanning overlay, and bounding boxes.", body_style)
        ],
        [
            Paragraph("<b>Real-Time Live Sync</b>", body_style),
            Paragraph("WebSockets (/ws/live)", body_style),
            Paragraph("Instant multi-client live updates without page refresh upon every attendance event.", body_style)
        ],
        [
            Paragraph("<b>Audio & Speech Engine</b>", body_style),
            Paragraph("Web Audio API + Web Speech API", body_style),
            Paragraph("Synthesizes futuristic check-in audio chimes and speaks automated welcome greetings aloud to employees.", body_style)
        ],
        [
            Paragraph("<b>Persistence Layer</b>", body_style),
            Paragraph("Attendence.csv + JSON Storage", body_style),
            Paragraph("Direct two-way compatibility with Excel/payroll CSV files, enriched with photo snapshots and role metadata.", body_style)
        ]
    ]

    t_tech = Table(tech_data, colWidths=[110, 150, 270])
    t_tech.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_BG_LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 10))

    # Section 3: Architecture & Flow
    story.append(Paragraph("3. System Architecture & Workflow", h1_style))
    story.append(Paragraph(
        "<b>Step 1: Face Enrollment:</b> Face images are uploaded via the dashboard or placed in the <code>Images/</code> directory. "
        "The system generates a unique 128-dimensional embedding vector for each person.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Step 2: Live Detection:</b> When a person approaches the camera, WebRTC captures video frames at 60 FPS. The browser HUD "
        "locks a tracking reticle over their face.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Step 3: Matching & Verification:</b> The live face vector is compared against known roster vectors using Euclidean distance. "
        "If distance &lt; 0.55 (confidence &gt; 95%), a match is confirmed.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Step 4: Anti-Duplicate Cooldown:</b> The backend validates an in-memory timer (e.g. 300s). Redundant check-ins within the cooldown "
        "period are gracefully acknowledged without logging duplicate lines.",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Step 5: Status Tagging (On-Time vs Late):</b> The check-in time is compared against the configured Official Start Time (e.g. 09:00 AM) "
        "+ Grace Period (15m). Arrivals before 09:15 AM receive <b>On Time</b> (green); arrivals after receive <b>Late</b> (red).",
        bullet_style
    ))
    story.append(Paragraph(
        "<b>Step 6: Real-Time Sync & Audio Feedback:</b> The event is appended to <code>Attendence.csv</code>, broadcasted via WebSockets "
        "to all dashboards, and an audible greeting speaks: <i>'Welcome [Name]! Attendance registered.'</i>",
        bullet_style
    ))
    story.append(Spacer(1, 10))

    # Section 4: Multi-View Dashboard Features
    story.append(Paragraph("4. Core Dashboard Modules", h1_style))
    story.append(Paragraph("• <b>AI Scanner Kiosk:</b> Live webcam viewport with cyber laser HUD, device selector, FPS meter, and live feed.", bullet_style))
    story.append(Paragraph("• <b>Attendance Audit Table:</b> Searchable, filterable by date/department/status, with instant CSV/Excel export.", bullet_style))
    story.append(Paragraph("• <b>Staff Face Directory:</b> Visual employee cards with photo avatars, last seen timestamps, and '+ Enroll' modal.", bullet_style))
    story.append(Paragraph("• <b>Analytics Hub:</b> Real-time KPI tiles (Total Enrolled, Present Today, Attendance %, On-Time %) and 24H traffic charts.", bullet_style))
    story.append(Paragraph("• <b>Settings Panel:</b> Configurable start times, grace period, anti-duplicate cooldown slider, and Dark/Light theme.", bullet_style))
    story.append(Spacer(1, 10))

    # Section 5: How to Use & Present
    story.append(Paragraph("5. Step-by-Step Usage & Presentation Guide", h1_style))
    story.append(Paragraph(
        "<b>1. Launch Server:</b> Double-click <code>run_server.bat</code> in the project directory. The browser opens automatically to <code>http://localhost:8000</code>.<br/>"
        "<b>2. Enroll Colleague:</b> Go to 'Staff Roster' &rarr; Click '+ Enroll New Person' &rarr; Take a webcam photo or upload an image file &rarr; Click 'Save & Enroll'.<br/>"
        "<b>3. Mark Attendance:</b> Go to 'AI Scanner Kiosk' &rarr; Stand in front of camera &rarr; System detects face, plays sound chime, and marks attendance.<br/>"
        "<b>4. Download Report:</b> Go to 'Attendance Logs' &rarr; Click 'Export CSV' to download an Excel-ready attendance sheet.",
        body_style
    ))
    story.append(Spacer(1, 10))

    # Section 6: Teacher / Viva Questions & Answers
    story.append(Paragraph("6. Key Viva & Exam Questions (Ready Answers)", h1_style))
    
    qa_data = [
        [Paragraph("<b>Question</b>", body_bold), Paragraph("<b>Recommended Answer</b>", body_bold)],
        [
            Paragraph("<b>How does the AI recognize faces?</b>", body_style),
            Paragraph("It extracts 128 deep facial landmark measurements (embeddings) and calculates Euclidean distance to find the closest matching enrolled identity.", body_style)
        ],
        [
            Paragraph("<b>How are duplicate check-ins prevented?</b>", body_style),
            Paragraph("The backend enforces a configurable cooldown throttle cache (e.g. 5 minutes). Duplicate scans within this window are rejected from re-logging.", body_style)
        ],
        [
            Paragraph("<b>How is Late vs On-Time determined?</b>", body_style),
            Paragraph("The check-in timestamp is compared against the Official Start Time plus Grace Period configured in the system rules.", body_style)
        ],
        [
            Paragraph("<b>Why use WebSockets?</b>", body_style),
            Paragraph("WebSockets enable bidirectional real-time event broadcasting so multiple kiosks and admin screens update instantly without polling or page refresh.", body_style)
        ]
    ]

    t_qa = Table(qa_data, colWidths=[180, 350])
    t_qa.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_qa)

    # Build Document
    doc.build(story)
    print("PDF Successfully Generated at:", pdf_path)

if __name__ == "__main__":
    create_project_pdf()
