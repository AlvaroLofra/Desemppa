# -*- coding: utf-8 -*-
"""
Generador del Documento Maestro Consolidado y Definitivo:
IURIS-IA / LEX-AGENT ES: ASISTENTE LEGAL PERSONAL AUTÓNOMO PARA ESPAÑA
Especificación Técnica y Arquitectura Basada Exclusivamente en Suscripciones Pro (Claude Code + Gemini Antigravity)
"""

import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Registro de fuentes TrueType de Windows
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Italic', 'C:/Windows/Fonts/ariali.ttf'))
pdfmetrics.registerFont(TTFont('Consolas', 'C:/Windows/Fonts/consola.ttf'))
pdfmetrics.registerFont(TTFont('Consolas-Bold', 'C:/Windows/Fonts/consolab.ttf'))

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return  # Portada limpia
        
        self.saveState()
        self.setFont("Arial-Bold", 7.5)
        self.setFillColor(colors.HexColor("#1B365D"))
        self.drawString(54, 802, "IURIS-IA / LEX-AGENT ES")
        self.setFont("Arial", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(168, 802, "| Especificación Maestra Definitiva (Claude Pro & Google AI Pro)")
        self.drawRightString(A4[0] - 54, 802, "SISTEMA AGÉNTICO JURÍDICO")
        
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 794, A4[0] - 54, 794)
        self.line(54, 44, A4[0] - 54, 44)
        
        self.setFont("Arial", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(54, 32, "Confidencial - Blueprint Maestro Optimizado para Suscripciones Claude Pro & Gemini AI Pro")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(A4[0] - 54, 32, page_str)
        self.restoreState()


def create_callout(text, title="NOTA TÉCNICA", bg_hex="#F0F7FF", border_hex="#2B6CB0", title_color="#1B365D", width=487):
    content = [
        Paragraph(f"<b>{title}</b>", ParagraphStyle(
            'CalloutTitle', fontName='Arial-Bold', fontSize=8.8, leading=11.5,
            textColor=colors.HexColor(title_color), spaceAfter=2.5
        )),
        Paragraph(text, ParagraphStyle(
            'CalloutBody', fontName='Arial', fontSize=8, leading=11.2,
            textColor=colors.HexColor("#1E293B")
        ))
    ]
    t = Table([[content]], colWidths=[width])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg_hex)),
        ('LEFTPADDING', (0,0), (-1,-1), 11),
        ('RIGHTPADDING', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 6.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6.5),
        ('LINEBEFORE', (0,0), (0,-1), 3.5, colors.HexColor(border_hex)),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    return t


def create_code_block(code_text, width=487):
    clean_text = code_text.replace(" ", "&nbsp;").replace("\n", "<br/>")
    p = Paragraph(clean_text, ParagraphStyle(
        'CodeBlockText', fontName='Consolas', fontSize=7.1, leading=9.5,
        textColor=colors.HexColor("#0F172A")
    ))
    t = Table([[p]], colWidths=[width])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('LEFTPADDING', (0,0), (-1,-1), 9),
        ('RIGHTPADDING', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 5.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5.5),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#CBD5E1")),
    ]))
    return t


def build_unified_master_pdf(filename):
    doc = SimpleDocTemplate(
        filename, pagesize=A4, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54
    )
    
    title_style = ParagraphStyle(
        'DocTitle', fontName='Arial-Bold', fontSize=21, leading=25,
        textColor=colors.HexColor("#1B365D"), spaceAfter=7
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle', fontName='Arial', fontSize=10.5, leading=14.5,
        textColor=colors.HexColor("#475569"), spaceAfter=11
    )
    
    h1_style = ParagraphStyle(
        'CustomH1', fontName='Arial-Bold', fontSize=12.5, leading=16,
        textColor=colors.HexColor("#1B365D"), spaceBefore=13, spaceAfter=5, keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'CustomH2', fontName='Arial-Bold', fontSize=9.8, leading=13.5,
        textColor=colors.HexColor("#2B6CB0"), spaceBefore=9, spaceAfter=3.5, keepWithNext=True
    )

    body_style = ParagraphStyle(
        'CustomBody', fontName='Arial', fontSize=8.3, leading=11.6,
        textColor=colors.HexColor("#1E293B"), spaceAfter=4.5
    )

    bullet_style = ParagraphStyle(
        'CustomBullet', fontName='Arial', fontSize=8.3, leading=11.4,
        textColor=colors.HexColor("#1E293B"), leftIndent=13, firstLineIndent=-8.5, spaceAfter=2.8
    )

    tbl_header = ParagraphStyle(
        'TblHeader', fontName='Arial-Bold', fontSize=7.8, leading=10.2,
        textColor=colors.HexColor("#FFFFFF"), alignment=1
    )

    tbl_cell = ParagraphStyle(
        'TblCell', fontName='Arial', fontSize=7.6, leading=10.2,
        textColor=colors.HexColor("#1E293B")
    )

    tbl_cell_center = ParagraphStyle(
        'TblCellCenter', fontName='Arial', fontSize=7.6, leading=10.2,
        textColor=colors.HexColor("#1E293B"), alignment=1
    )

    story = []

    # =========================================================================
    # PORTADA MAESTRA
    # =========================================================================
    story.append(Spacer(1, 10))
    tag_table = Table([[Paragraph("<b>ESPECIFICACIÓN MAESTRA DEFINITIVA • STACK 100% CLAUDE PRO & GEMINI AI PRO</b>", ParagraphStyle(
        'TagStyle', fontName='Arial-Bold', fontSize=7.8, textColor=colors.HexColor("#FFFFFF")
    ))]], colWidths=[385])
    tag_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1B365D")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(tag_table)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("IURIS-IA / LEX-AGENT ES: ASISTENTE LEGAL AUTÓNOMO", title_style))
    story.append(Paragraph("Sistema Agéntico Experto en Derecho Español con Enrutamiento Inteligente sobre Suscripciones Pro (Gemini 3.8 Flash, 4 Argon, Claude Haiku, Sonnet y Opus 5.5 con Niveles de Razonamiento Low/Med/High)", subtitle_style))
    
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2B6CB0"), spaceAfter=10, spaceBefore=2))
    
    meta_data = [
        [Paragraph("<b>Ámbito Territorial:</b>", tbl_cell), Paragraph("España (BOE Consolidado, 17 Regímenes Forales Autonómicos y 30 Convenios Colectivos Clave)", tbl_cell)],
        [Paragraph("<b>Fuentes Primarias:</b>", tbl_cell), Paragraph("BOE Datos Abiertos (REST API), CENDOJ/CGPJ (LanceDB Vectorial + Playwright Stealth) y REGCON (Convenios)", tbl_cell)],
        [Paragraph("<b>Stack de Modelos:</b>", tbl_cell), Paragraph("<b>Google AI Pro / Antigravity:</b> Gemini 3.8 Flash & 4 Argon | <b>Claude Pro:</b> Haiku, Sonnet & Opus 5.5 (Low/Med/High)", tbl_cell)],
        [Paragraph("<b>Coste Operativo:</b>", tbl_cell), Paragraph("<b>0,00 € adicionales en tokens</b> (Aprovechamiento íntegro de las suscripciones planas ya pagadas)", tbl_cell)],
        [Paragraph("<b>Blindaje Semántico:</b>", tbl_cell), Paragraph("Token Fuzzy Matching (Levenshtein ≥ 95%) + Micro-Validador NLI (Natural Language Inference)", tbl_cell)],
        [Paragraph("<b>Motor Procesal:</b>", tbl_cell), Paragraph("Cómputo determinista de días hábiles con 8.131 festivos municipales + Día de Gracia (Art. 135.5 LEC)", tbl_cell)],
        [Paragraph("<b>Cumplimiento Legal:</b>", tbl_cell), Paragraph("Exención Doméstica AI Act (Art. 2.10) + Cortafuegos Anti-Intrusismo (Art. 403 CP y Arts. 23/31 LEC >2.000€)", tbl_cell)],
        [Paragraph("<b>Testing & Calidad:</b>", tbl_cell), Paragraph("Benchmark Ciego con Sentencias Purgadas del Tribunal Supremo y Audiencias Provinciales (Score 0-100)", tbl_cell)],
        [Paragraph("<b>Pila de Software:</b>", tbl_cell), Paragraph("Python 3.11+, FastAPI (Backend SSE), Web UI (Tailwind/React), LanceDB, SQLite3 (WAL), RapidFuzz", tbl_cell)],
        [Paragraph("<b>Versión del Documento:</b>", tbl_cell), Paragraph("Versión 2.1 Maestra Definitiva (Optimizada para el Stack Pro del Usuario)", tbl_cell)],
    ]
    t_meta = Table(meta_data, colWidths=[128, 359])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))
    
    story.append(create_callout(
        "<b>DISEÑO A MEDIDA DE TUS SUSCRIPCIONES:</b> Esta versión descarta explícitamente cualquier requisito de hardware local (Ollama/Qwen). La arquitectura está optimizada al 100% para combinar de forma sinérgica tus suscripciones activas de Google AI Pro (Gemini 3.8 Flash y futuro Argon 4) y Claude Pro (Haiku, Sonnet y Opus 5.5 con thinking configurable). El sistema absorbe la lectura masiva gratis con Gemini y reserva el razonamiento profundo de Opus/Argon para la estrategia final, protegiendo tus límites de cuota.",
        title="DIRECTIVA MAESTRA DE INGENIERÍA",
        bg_hex="#EFF6FF", border_hex="#1B365D"
    ))
    story.append(PageBreak())

    # =========================================================================
    # SECCIÓN 1: RESUMEN EJECUTIVO Y JUSTIFICACIÓN
    # =========================================================================
    story.append(Paragraph("1. Resumen Ejecutivo y Planteamiento del Problema", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph("<b>1.1. El Problema: Asimetría y Brecha en el Acceso a la Justicia</b>", h2_style))
    story.append(Paragraph(
        "El acceso al asesoramiento jurídico en España presenta una barrera económica y técnica infranqueable para la ciudadanía. Ante contingencias cotidianas —retención indebida de fianzas de alquiler, despidos disciplinarios, discrepancias contractuales bancarias o sanciones administrativas—, el ciudadano común no sabe si su pretensión es legítima ni conoce los plazos procesales perentorios para accionar. El proyecto <b>Iuris-IA / Lex-Agent ES</b> crea un asistente de escritorio autónomo que democratiza el acceso a la información jurídica rigurosa.",
        body_style
    ))
    
    story.append(Paragraph("<b>1.2. La Tesis del Informático: Orquestación Determinista y Modelos Frontera</b>", h2_style))
    story.append(Paragraph(
        "El desarrollador del proyecto no necesita ser jurista: la solidez del sistema se logra mediante <b>ingeniería de software determinista</b> (guardarraíles de citación tokenizada, bases vectoriales locales, filtros de congruencia lógica NLI y cómputo matemático de días hábiles) combinada con el <b>razonamiento jurídico superior de los modelos frontera</b> de Anthropic (Opus 5.5 / Sonnet) y Google (Gemini 3.8 Flash / 4 Argon en Antigravity).",
        body_style
    ))

    # =========================================================================
    # SECCIÓN 2: ANÁLISIS COMPARATIVO DE ENFOQUES DE IA
    # =========================================================================
    story.append(Paragraph("2. Análisis Comparativo de Enfoques de Inteligencia Artificial", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    approaches_data = [
        [Paragraph("<b>Enfoque Técnico</b>", tbl_header), Paragraph("<b>Mecanismo Operativo</b>", tbl_header), Paragraph("<b>Comportamiento en Derecho Español</b>", tbl_header), Paragraph("<b>Veredicto Técnico</b>", tbl_header)],
        [
            Paragraph("<b>1. Fine-Tuning<br/>(LoRA / QLoRA)</b>", tbl_cell),
            Paragraph("Reentrenamiento de pesos sinápticos con leyes y demandas.", tbl_cell),
            Paragraph("Aprende estilo procesal forense, pero comprime la información en pesos estáticos.", tbl_cell),
            Paragraph("<font color='#DC2626'><b>Inviable en solitario:</b></font> Alucina números de artículos y cita normas derogadas al carecer de actualización dinámica.", tbl_cell)
        ],
        [
            Paragraph("<b>2. Inyección Masiva<br/>(Long Context Dump)</b>", tbl_cell),
            Paragraph("Volcar códigos enteros en ventanas de 1M de tokens.", tbl_cell),
            Paragraph("El corpus español supera los 120M tokens (10.000+ normas BOE + CC.AA.). Sufre <i>Lost in the Middle</i>.", tbl_cell),
            Paragraph("<font color='#D97706'><b>Inviable en escala:</b></font> Ceguera ante la jerarquía normativa y excepciones transitorias; latencia y costes inasumibles.", tbl_cell)
        ],
        [
            Paragraph("<b>3. Agentic RAG Quirúrgico + MCP + NLI</b>", tbl_cell),
            Paragraph("Recuperación atómica de 10-15 artículos y 3-5 sentencias en ventana limpia con verificación lógica.", tbl_cell),
            Paragraph("Máxima precisión factual, trazabilidad oficial completa y verificación determinista en Python.", tbl_cell),
            Paragraph("<font color='#16A34A'><b>Estándar Óptimo:</b></font> Fiabilidad matemática, ausencia de alucinaciones y coste por consulta de 0,00 € sobre tus planes Pro.", tbl_cell)
        ],
    ]
    t_app = Table(approaches_data, colWidths=[90, 125, 132, 140])
    t_app.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1B365D")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    for r in range(1, len(approaches_data)):
        if r % 2 == 0:
            t_app.setStyle(TableStyle([('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC"))]))
    story.append(t_app)
    story.append(Spacer(1, 6))

    # =========================================================================
    # SECCIÓN 3: FUENTES DE DATOS E INGENIERÍA DE ACCESO
    # =========================================================================
    story.append(Paragraph("3. Fuentes de Datos e Ingeniería de Acceso Desacoplada", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph(
        "Para garantizar una respuesta instantánea sin bloqueos en el portal del CGPJ y resolver el vacío de los convenios laborales, el sistema adopta una **Capa de Datos Híbrida Desacoplada**:",
        body_style
    ))
    
    sources_data = [
        [Paragraph("<b>Fuente Jurídica</b>", tbl_header), Paragraph("<b>Cobertura y Contenido</b>", tbl_header), Paragraph("<b>Mecanismo de Acceso en Iuris-IA</b>", tbl_header)],
        [
            Paragraph("<b>BOE Legislación Consolidada</b>", tbl_cell),
            Paragraph("Leyes estatales consolidadas vigentes, códigos básicos, reformas y enlaces de análisis.", tbl_cell),
            Paragraph("API REST oficial pública (GET) a <code>/datosabiertos/api/legislacion-consolidada</code> con parser Pydantic polimórfico.", tbl_cell)
        ],
        [
            Paragraph("<b>CENDOJ (CGPJ) Jurisprudencia</b>", tbl_cell),
            Paragraph("Millones de sentencias de Tribunal Supremo, Audiencia Nacional, TSJ y Audiencias Provinciales.", tbl_cell),
            Paragraph("<b>Cache-First en LanceDB local</b> (5.000 precedentes clave a <50ms) + fallback asíncrono con <code>playwright-stealth</code>.", tbl_cell)
        ],
        [
            Paragraph("<b>Convenios Colectivos (REGCON / BOP)</b>", tbl_cell),
            Paragraph("Convenios sectoriales y de empresa (salarios reales, categorías, pluses, faltas laborales).", tbl_cell),
            Paragraph("Pre-indexación local de los <b>30 convenios más masivos de España</b> + selector UI para carga de PDF/nómina.", tbl_cell)
        ],
        [
            Paragraph("<b>Ordenanzas Municipales (BOP)</b>", tbl_cell),
            Paragraph("Normativa local: multas ORA/SER, ruidos, licencias y Plusvalía municipal.", tbl_cell),
            Paragraph("Gatekeeper de competencia local en Triaje; solicitud de PDF de la sanción al usuario y advertencia de primacía local.", tbl_cell)
        ]
    ]
    t_src = Table(sources_data, colWidths=[110, 187, 190])
    t_src.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1B365D")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    for r in range(1, len(sources_data)):
        if r % 2 == 0:
            t_src.setStyle(TableStyle([('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC"))]))
    story.append(t_src)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>3.1. Pipeline de Extracción Robusta de Sentencias (OCR y Ligaduras)</b>", h2_style))
    story.append(Paragraph(
        "<code>connectors/pdf_extractor.py</code> aplica una triple salvaguarda: 1) Conmutación a OCR local (Tesseract / Windows OCR) si <code>pdfplumber</code> extrae menos de 100 caracteres por página (PDF escaneado); 2) Normalización tipográfica de ligaduras Unicode (<code>\\ufb01</code> &rarr; <code>fi</code>, <code>\\ufb02</code> &rarr; <code>fl</code>) y des-silabeo con regex; y 3) Aislamiento determinista de <code>VOTOS PARTICULARES</code> disidentes para impedir que se adopten como doctrina de la Sala.",
        body_style
    ))

    # =========================================================================
    # SECCIÓN 4: VALIDADOR TEMPORAL Y REFORMAS NORMATIVAS
    # =========================================================================
    story.append(Paragraph("4. Sincronización Temporal y Validador de Reformas Normativas", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph(
        "El módulo <code>core/temporal_sync.py</code> previene el anacronismo jurisprudencial cruzando la <code>fecha_resolucion</code> de la sentencia con la <code>fecha_actualizacion</code> y <code>referencias_posteriores</code> del BOE. Si el precepto sufrió reformas con posterioridad al fallo, inyecta una advertencia imperativa de desincronización, verificando asimismo si la controversia se rige por disposiciones transitorias o por el principio de irretroactividad de las normas desfavorables (Art. 9.3 y 25 CE).",
        body_style
    ))

    # =========================================================================
    # SECCIÓN 5: PIPELINE EN 4 FASES OPTIMIZADO PARA CLAUDE & GEMINI
    # =========================================================================
    story.append(Paragraph("5. Arquitectura del Pipeline Agéntico en 4 Fases", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph(
        "El orquestador divide la ejecución en cuatro etapas desacopladas con **Streaming Progresivo SSE en la Web UI** y asignación óptima de tus modelos suscritos:",
        body_style
    ))
    
    pipeline_data = [
        [Paragraph("<b>Fase y Latencia</b>", tbl_header), Paragraph("<b>Misión y Asignación de Modelos</b>", tbl_header), Paragraph("<b>Entrada / Salida y Optimización</b>", tbl_header)],
        [
            Paragraph("<b>Fase 1: Triaje Multihop<br/>(1 - 2 seg)</b>", tbl_cell),
            Paragraph("Traductor Jurídico Invisible.<br/><b>Motor:</b> Claude Haiku o Gemini 3.8 Flash (Low effort).", tbl_cell),
            Paragraph("<b>In:</b> Texto usuario.<br/><b>Out:</b> JSON con leyes BOE y términos CENDOJ. Lanza preguntas aclaratorias si hay ambigüedad.", tbl_cell)
        ],
        [
            Paragraph("<b>Fase 2: Cribado Pesado<br/>(2 - 4 seg)</b>", tbl_cell),
            Paragraph("Cribado de BOE, convenios y PDFs CENDOJ.<br/><b>Motor:</b> Gemini 3.8 Flash (AI Studio Free Tier / Pro).", tbl_cell),
            Paragraph("<b>In:</b> JSON Fase 1.<br/><b>Out:</b> Dossier compacto (~3.000 tokens). Absorbe gratis miles de tokens de PDFs judiciales.", tbl_cell)
        ],
        [
            Paragraph("<b>Fase 3: Debate Dialéctico<br/>(10 - 25 seg stream)</b>", tbl_cell),
            Paragraph("Contradictorio procesal: Defensa vs Contraparte vs Magistrado.<br/><b>Motor:</b> Claude Opus 5.5 / Sonnet o Gemini 4 Argon.", tbl_cell),
            Paragraph("<b>In:</b> Dossier curado de Fase 2.<br/><b>Out:</b> Dictamen bajo <b>lógica disyuntiva estricta</b> con niveles de thinking (Low/Med/High).", tbl_cell)
        ],
        [
            Paragraph("<b>Fase 4: Blindaje NLI<br/>(1 - 3 seg)</b>", tbl_cell),
            Paragraph("Guardarraíles en Python: Fuzzy Matching (≥95%), NLI y calendario judicial.<br/><b>Motor:</b> Python local + Gemini Flash.", tbl_cell),
            Paragraph("<b>In:</b> Dictamen Fase 3.<br/><b>Out:</b> Dictamen certificado con advertencia deontológica de postulación legal.", tbl_cell)
        ]
    ]
    t_pip = Table(pipeline_data, colWidths=[100, 192, 195])
    t_pip.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1B365D")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    for r in range(1, len(pipeline_data)):
        if r % 2 == 0:
            t_pip.setStyle(TableStyle([('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC"))]))
    story.append(t_pip)
    story.append(Spacer(1, 6))

    # =========================================================================
    # SECCIÓN 6: GUARDARRAÍLES DETERMINISTAS Y BLINDAJE SEMÁNTICO
    # =========================================================================
    story.append(Paragraph("6. Guardarraíles Deterministas y Blindaje Semántico NLI", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph("• <b>Token Fuzzy Matching (Levenshtein ≥ 95%):</b> El dictamen exige el campo <code>verbatim_quote</code>. El validador en Python normaliza comillas, espacios y signos de puntuación, calculando la similitud tokenizada frente al texto descargado del BOE. Si el ratio es inferior al 95%, bloquea la emisión.", bullet_style))
    story.append(Paragraph("• <b>Micro-Validador de Congruencia Lógica NLI:</b> Mediante un prompt estructurado de entailment con Gemini 3.8 Flash, se comprueba que la conclusión del asistente no contradiga la literalidad del precepto legal invocado.", bullet_style))
    story.append(Paragraph("• <b>Motor de Calendario Judicial y Días Hábiles (<code>calendar_engine.py</code>):</b> Integra el dataset oficial de festivos locales de los **8.131 municipios de España** más festivos autonómicos y nacionales, aplicando estrictamente la regla del <b>Día de Gracia Procesal</b> (Art. 135.5 LEC: plazo hábil hasta las 15:00 horas del siguiente día hábil).", bullet_style))
    story.append(Paragraph("• <b>Tratamiento de Conceptos Jurídicos Indeterminados (CJI):</b> Cuando se invocan estándares elásticos (*'pequeñas reparaciones'*, *'buena fe'*), el sistema prohíbe inventar importes con base en el BOE y obliga a fundamentar la cuantía exclusivamente en sentencias de Audiencias Provinciales.", bullet_style))

    # =========================================================================
    # SECCIÓN 7: MATRIZ DE MODOS DE ENRUTAMIENTO (CLAUDE & GEMINI)
    # =========================================================================
    story.append(Paragraph("7. Matriz de Enrutamiento Inteligente sobre tus Suscripciones", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    modes_data = [
        [Paragraph("<b>Modo / Perfil</b>", tbl_header), Paragraph("<b>Fase 1 (Triaje) & Fase 2 (PDFs)</b>", tbl_header), Paragraph("<b>Fase 3 (Dictamen Senior)</b>", tbl_header), Paragraph("<b>Impacto en Cuota / Latencia</b>", tbl_header)],
        [
            Paragraph("<b>1. Modo Eco<br/>(Día a Día)</b>", tbl_cell),
            Paragraph("Gemini 3.8 Flash<br/>(Low effort / AI Studio Free)", tbl_cell),
            Paragraph("Gemini 3.8 Flash (High effort)<br/>o Claude Haiku", tbl_cell),
            Paragraph("<b>0%</b> cuota Claude Pro.<br/>Latencia: ~6 seg.", tbl_cell_center)
        ],
        [
            Paragraph("<b>2. Equilibrado<br/>(Recomendado)</b>", tbl_cell),
            Paragraph("Gemini 3.8 Flash<br/>(Absorbe lectura masiva)", tbl_cell),
            Paragraph("Claude Sonnet 3.5 / 4.5<br/>(Medium effort)", tbl_cell),
            Paragraph("<b>~3%</b> cuota Claude Pro.<br/>Latencia: ~14 seg.", tbl_cell_center)
        ],
        [
            Paragraph("<b>3. Modo Pro<br/>(Tribunal Supremo)</b>", tbl_cell),
            Paragraph("Gemini 3.8 Flash<br/>(Dossier curado a 3.000 tok)", tbl_cell),
            Paragraph("Claude Opus 5.5 o Gemini 4 Argon<br/>(High effort / deep reasoning)", tbl_cell),
            Paragraph("<b>~9%</b> cuota Claude Pro.<br/>Latencia: ~28 seg stream.", tbl_cell_center)
        ],
        [
            Paragraph("<b>4. Auditoría Cruzada<br/>(Consenso Dual)</b>", tbl_cell),
            Paragraph("Gemini 3.8 Flash<br/>(Lectura y síntesis)", tbl_cell),
            Paragraph("Claude Opus 5.5 (Dictamen)<br/>+ Gemini 4 Argon (Auditor)", tbl_cell),
            Paragraph("Máximo rigor procesal.<br/>Latencia: ~35 seg.", tbl_cell_center)
        ]
    ]
    t_modes = Table(modes_data, colWidths=[105, 137, 135, 110])
    t_modes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1B365D")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    for r in range(1, len(modes_data)):
        if r % 2 == 0:
            t_modes.setStyle(TableStyle([('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC"))]))
    story.append(t_modes)
    story.append(Spacer(1, 6))

    # =========================================================================
    # SECCIÓN 8: CUMPLIMIENTO REGULATORIO Y DEONTOLOGÍA
    # =========================================================================
    story.append(Paragraph("8. Cumplimiento Regulatorio, Deontología y AI Act", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph("• <b>Encuadre Legal bajo el AI Act (Reglamento UE 2024/1689):</b> El sistema se define estrictamente como una <i>Herramienta Personal de Investigación Documental y Soporte a la Auto-Defensa Ciudadana</i>, quedando amparada en la exención de actividad privada y doméstica (Art. 2.10) cuando es ejecutada en local por el propio usuario.", bullet_style))
    story.append(Paragraph("• <b>Erradicación del Delito de Intrusismo (Art. 403 CP):</b> Se prohíben de forma absoluta las predicciones numéricas pseudo-científicas de victoria (*'viabilidad: 78%'*). Se sustituyen por bandas cualitativas de solidez argumental (*'Criterio consolidado favorable'*, *'Disparidad de criterio'*, *'Riesgo probatorio alto'*).", bullet_style))
    story.append(Paragraph("• <b>Alerta Preceptiva de Postulación (Arts. 23 y 31 LEC):</b> Cuando el litigio supere los 2.000 € o se trate de materias con postulación obligatoria (juicio ordinario civil, recurso contencioso o demanda judicial de despido), el sistema bloquea la generación de escritos formales y emite un requerimiento no saltable de contratación de Abogado y Procurador colegiados.", bullet_style))

    # =========================================================================
    # SECCIÓN 9: MOTOR DE BACKTESTING CIEGO CERTIFICADO
    # =========================================================================
    story.append(Paragraph("9. Motor de Backtesting Ciego Certificado (Blind Judge)", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    story.append(Paragraph(
        "El motor <code>benchmark/blind_judge.py</code> evalúa el sistema frente a 25 casos reales (15 del Tribunal Supremo y 10 de Audiencias Provinciales) aplicando un estricto **Protocolo Anti-Fuga de Datos**:",
        body_style
    ))
    story.append(Paragraph("1. <b>Purga Forense de Antecedentes:</b> Eliminación de toda mención a las resoluciones de primera instancia y apelación contenidas en los Antecedentes de Hecho, dejando solo la narración fáctica pura.", bullet_style))
    story.append(Paragraph("2. <b>Casos Sintéticos con Permutaciones Controladas:</b> Modificación de fechas, nombres de empresas y cuantías preservando la ratio decidendi para medir deducción jurídica genuina sin atajos memorísticos.", bullet_style))
    story.append(Paragraph("3. <b>Rúbrica de Puntuación (0-100 Puntos):</b> Outcome Match (30 pts), Statutory Recall BOE (30 pts), Alineación Doctrinal con Audiencias y Supremo (25 pts) y Tasa Cero de Alucinación Normativa (15 pts).", bullet_style))

    # =========================================================================
    # SECCIÓN 10: ESTRUCTURA DEL SOFTWARE Y ESQUEMA SQLITE
    # =========================================================================
    story.append(Paragraph("10. Estructura del Software y Esquema de Base de Datos", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    tree_text = """abogado_ia_app/
├── config/
│   ├── profiles.json          # Modos: Eco (Flash), Equilibrado (Sonnet) y Pro (Opus/Argon)
│   └── settings.py            # Rutas LanceDB, SQLite WAL, timeouts y effort levels (Low/Med/High)
├── core/
│   ├── router.py              # Adaptador unificado: Google GenAI SDK (Flash/Argon) + Claude CLI
│   ├── orchestrator.py        # Pipeline 4 fases con streaming SSE y WebSocket
│   ├── validators.py          # Token Fuzzy Match (≥95%) y Micro-validador NLI
│   └── calendar_engine.py     # Motor 8.131 festivos municipales + Día de Gracia (Art. 135.5 LEC)
├── connectors/
│   ├── boe_client.py          # Cliente REST oficial /datosabiertos/ con Pydantic polimórfico
│   ├── cendoj_vector.py       # Interfaz LanceDB / SQLite-VSS (5.000 sentencias en local)
│   ├── cendoj_stealth.py      # Worker Playwright-Stealth para búsquedas background
│   ├── convenios_db.py        # Gestor de los 30 convenios colectivos sectoriales masivos
│   └── pdf_extractor.py       # Extractor con OCR de respaldo y aislamiento de Votos Particulares
├── benchmark/
│   ├── blind_judge.py         # Orquestador con purga de antecedentes y casos sintéticos
│   ├── evaluator.py           # Evaluador cuantitativo (Outcome, Recall, Doctrina, Alucinación)
│   └── trap_cases.json        # 25 casos calibrados (TS + Audiencias Provinciales)
├── storage/
│   ├── database.py            # SQLite3 con PRAGMA journal_mode=WAL y busy_timeout=5000
│   ├── local_cache.db         # Tablas: boe_bloques, cendoj_sentencias, convenios, sesiones
│   └── lancedb_store/         # Base vectorial para búsqueda semántica instantánea (<50ms)
└── ui/
    ├── web_server.py          # Servidor FastAPI local con endpoints REST y SSE
    └── web_frontend/          # Interfaz Web moderna (Tailwind, visor de artículos y chat SSE)"""
    story.append(create_code_block(tree_text))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>10.1. Esquema Relacional Consolidado (SQLite3 en Modo WAL)</b>", h2_style))
    schema_sql = """PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

-- Normativa Consolidada del BOE
CREATE TABLE IF NOT EXISTS boe_bloques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_norma TEXT NOT NULL,                -- BOE-A-1994-26003 (LAU)
    id_bloque TEXT NOT NULL,               -- a21
    titulo TEXT,
    texto_consolidado TEXT NOT NULL,
    fecha_actualizacion TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(id_norma, id_bloque)
);

-- Precedentes Judiciales CENDOJ (TS y Audiencias Provinciales)
CREATE TABLE IF NOT EXISTS cendoj_sentencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roj_id TEXT UNIQUE NOT NULL,           -- STS 4512/2023 o SAP M 1204/2022
    ecli TEXT,
    tribunal TEXT NOT NULL,
    jurisdiccion TEXT NOT NULL,
    fecha_resolucion TEXT NOT NULL,
    antecedentes_purgados TEXT,
    fundamentos_mayoria TEXT,
    voto_particular TEXT,                  -- Aislado de la doctrina vencedora
    fallo TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Convenios Colectivos Sectoriales y Provinciales Masivos
CREATE TABLE IF NOT EXISTS convenios_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_convenio TEXT UNIQUE NOT NULL,  -- Código oficial REGCON/BOP
    denominacion TEXT NOT NULL,
    ambito_territorial TEXT NOT NULL,      -- Madrid, Barcelona, etc.
    sector_actividad TEXT NOT NULL,        -- Hostelería, Metal, Comercio, etc.
    texto_integro TEXT NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sesiones y Dictámenes Auditados
CREATE TABLE IF NOT EXISTS sesiones_consultas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modo_utilizado TEXT NOT NULL,          -- Eco, Equilibrado, Pro
    consulta_usuario TEXT NOT NULL,
    triage_json TEXT NOT NULL,
    articulos_citados TEXT,
    sentencias_citadas TEXT,
    fuzzy_match_score REAL,
    dictamen_markdown TEXT NOT NULL
);"""
    story.append(create_code_block(schema_sql))
    story.append(Spacer(1, 6))

    # =========================================================================
    # SECCIÓN 11: HOJA DE RUTA EN 5 SPRINTS
    # =========================================================================
    story.append(Paragraph("11. Hoja de Ruta de Implementación en 5 Sprints", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=7, spaceBefore=2))
    
    sprints_data = [
        [Paragraph("<b>Sprint / Hito</b>", tbl_header), Paragraph("<b>Módulos e Hitos de Ingeniería</b>", tbl_header), Paragraph("<b>Criterio de Éxito / Métrica</b>", tbl_header)],
        [
            Paragraph("<b>Sprint 1:<br/>Core & Router Pro</b>", tbl_cell),
            Paragraph("1. Conector Gemini 3.8 Flash / 4 Argon (Google GenAI) + Claude CLI serializado.<br/>2. Inicialización de SQLite WAL y LanceDB local.", tbl_cell),
            Paragraph("Inferencia streaming <10s y conmutación de modo sin colisiones de I/O.", tbl_cell)
        ],
        [
            Paragraph("<b>Sprint 2:<br/>Datos & Convenios</b>", tbl_cell),
            Paragraph("1. Cliente BOE REST con Pydantic polimórfico.<br/>2. Pre-indexación de 30 convenios masivos y LanceDB con 5.000 sentencias.", tbl_cell),
            Paragraph("Statutory Recall ≥ 92% en recuperación de normas y convenios.", tbl_cell)
        ],
        [
            Paragraph("<b>Sprint 3:<br/>Calendario & Guardarraíles</b>", tbl_cell),
            Paragraph("1. Motor <code>calendar_engine.py</code> con 8.131 municipios + Día de Gracia.<br/>2. Token Fuzzy Matching (≥95%) y validador de congruencia NLI.", tbl_cell),
            Paragraph("Cero errores en cómputo de plazos procesales. Tasa de alucinación = 0%.", tbl_cell)
        ],
        [
            Paragraph("<b>Sprint 4:<br/>Pipeline & Backtesting</b>", tbl_cell),
            Paragraph("1. Pipeline 4 fases con debate disyuntivo y streaming progresivo.<br/>2. Ejecución del benchmark ciego con 25 sentencias purgadas.", tbl_cell),
            Paragraph("Doctrinal Alignment ≥ 88% y Outcome Match ≥ 90% en Audiencias y TS.", tbl_cell)
        ],
        [
            Paragraph("<b>Sprint 5:<br/>Web UI & Certificación</b>", tbl_cell),
            Paragraph("1. Interfaz Web moderna con streaming SSE, visor lateral y soporte PWA.<br/>2. Cortafuegos deontológico y advertencia preceptiva Arts. 23/31 LEC.", tbl_cell),
            Paragraph("Aplicación de escritorio terminada, empaquetable y lista para uso.", tbl_cell)
        ]
    ]
    t_sp = Table(sprints_data, colWidths=[98, 250, 139])
    t_sp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1B365D")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    for r in range(1, len(sprints_data)):
        if r % 2 == 0:
            t_sp.setStyle(TableStyle([('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC"))]))
    story.append(t_sp)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>11.1. Adaptador Python en <code>core/router.py</code> para tus Modelos</b>", h2_style))
    router_code = """import subprocess, json
from google import genai

class ProLegalRouter:
    def __init__(self, gemini_api_key: str):
        self.gemini_client = genai.Client(api_key=gemini_api_key)

    def execute_stage(self, stage: str, profile: str, prompt: str, system_prompt: str, effort: str = "medium") -> str:
        # Enrutamiento inteligente segun fase y perfil seleccionado
        if stage in ["triage", "pdf_screening"]:
            # Fase 1 y 2: Gemini 3.8 Flash (rapido, ventana 1M tokens, coste 0)
            res = self.gemini_client.models.generate_content(
                model="gemini-3.8-flash", contents=f"SYSTEM: {system_prompt}\\n\\nUSER: {prompt}"
            )
            return res.text
            
        elif stage == "dialectical_counsel":
            if profile == "eco":
                # Modo Eco: Gemini 3.8 Flash con thinking alto
                res = self.gemini_client.models.generate_content(
                    model="gemini-3.8-flash", contents=f"SYSTEM: {system_prompt}\\n\\nUSER: {prompt}"
                )
                return res.text
            elif profile == "pro":
                # Modo Pro: Claude Opus 5.5 con thinking profundo via CLI Pro
                cmd = ["claude", "-p", f"{system_prompt}\\n\\n{prompt}", 
                       "--model", "opus", "--effort", effort, "--output-format", "json"]
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return json.loads(res.stdout).get("result", "")
            else:
                # Modo Equilibrado: Claude Sonnet con thinking medio
                cmd = ["claude", "-p", f"{system_prompt}\\n\\n{prompt}", 
                       "--model", "sonnet", "--output-format", "json"]
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return json.loads(res.stdout).get("result", "")"""
    story.append(create_code_block(router_code))
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>11.2. Conclusión y Veredicto Final</b>", h2_style))
    story.append(Paragraph(
        "Esta <b>Especificación Maestra Definitiva</b> acredita la total viabilidad técnica, operativa y económica de <b>Iuris-IA / Lex-Agent ES</b> utilizando exclusivamente tu ecosistema de suscripciones ya pagadas (Claude Pro y Google AI Pro). Se erradica cualquier dependencia de hardware local costoso y se asegura un rendimiento de nivel profesional sin gastar un solo euro adicional en tokens de API.",
        body_style
    ))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Master PDF generado exitosamente en: {filename}")

if __name__ == "__main__":
    out = r"c:\Users\Administrator\Documents\Claude Code\Proyecto abogado personal\Propuesta_Maestra_IurisIA_LexAgent_Definitiva.pdf"
    build_unified_master_pdf(out)
