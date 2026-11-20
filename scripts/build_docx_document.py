# Historical proposal generator; claims and benchmarks are unverified research notes.
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def create_proposal_docx(output_path):
    doc = docx.Document()

    # Define Color Palette (Pastel Light & Professional Slate)
    COLOR_PRIMARY = RGBColor(79, 70, 229)    # Indigo/Purple
    COLOR_SECONDARY = RGBColor(2, 132, 199)  # Sky Blue
    COLOR_TEXT_MAIN = RGBColor(15, 23, 42)   # Dark Slate
    COLOR_TEXT_MUTED = RGBColor(71, 85, 105) # Slate Muted
    HEX_PASTEL_BG = "F8FAFC"
    HEX_PRIMARY_BG = "F3E8FF"
    HEX_BORDER = "E2E8F0"

    # Page Margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Styles Setup
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = COLOR_TEXT_MAIN

    # Helper function for cell background color
    def set_cell_background(cell, fill_hex):
        shading_xml = f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'
        cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))

    # Helper function for cell borders
    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    # Add Heading Helper
    def add_custom_heading(text, level=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18 if level == 1 else 12)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        if level == 1:
            run.font.size = Pt(20)
            run.font.color.rgb = COLOR_PRIMARY
            # Add bottom border accent under H1
            pPr = p._p.get_or_add_pPr()
            pbdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="4" w:color="4F46E5"/></w:pBdr>')
            pPr.append(pbdr)
        elif level == 2:
            run.font.size = Pt(15)
            run.font.color.rgb = COLOR_SECONDARY
        else:
            run.font.size = Pt(12)
            run.font.color.rgb = COLOR_TEXT_MAIN
        return p

    # Add Callout Box Helper
    def add_callout_box(title, text, bg_hex="F1F5F9"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, bg_hex)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
        
        # Left border line
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="4F46E5"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(2)
        r_title = cp.add_run(f"★ {title}\n")
        r_title.bold = True
        r_title.font.size = Pt(11)
        r_title.font.color.rgb = COLOR_PRIMARY
        r_text = cp.add_run(text)
        r_text.font.size = Pt(10.5)
        r_text.font.color.rgb = COLOR_TEXT_MUTED
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # COVER PAGE
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(72)
    title_p.paragraph_format.space_after = Pt(12)
    r = title_p.add_run("Code Review System using Artificial Intelligence")
    r.font.size = Pt(28)
    r.bold = True
    r.font.color.rgb = COLOR_PRIMARY

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(36)
    r_sub = sub_p.add_run("Comprehensive Software Design, Architectural Proposal & Market Research Document")
    r_sub.font.size = Pt(14)
    r_sub.font.color.rgb = COLOR_SECONDARY

    # Cover Meta Box
    add_callout_box("DOCUMENT PROPOSAL METADATA", 
                    "Document Type: Software Design Description (SDD) & Research Report\n"
                    "Domain: Artificial Intelligence & Software Engineering (AI4SE)\n"
                    "Target Audience: Project Reviewers, Industry Mentors & Academic Evaluators\n"
                    "Status: Formal Technical Design & Proposal", "F3E8FF")

    doc.add_page_break()

    # TABLE OF CONTENTS SUMMARY
    add_custom_heading("Document Table of Contents", 1)
    toc_items = [
        "1. Introduction & Software Engineering Foundations",
        "2. What is Code Review? Deep Dive & Objectives",
        "3. Types of Code Reviews (Taxonomy & Comparison)",
        "4. Complete Code Review Process (Lifecycle Pipeline)",
        "5. Code Review Best Practices (SOLID, Clean Architecture)",
        "6. Problems in Existing Code Review Systems",
        "7. Existing Code Review Tools (45+ Tool Market Survey)",
        "8. Market Analysis, Industry Statistics & Trends",
        "9. Core Technologies in AI Code Review",
        "10. Proposed AI Code Review System Architecture",
        "11. Proposed Features (30+ Intelligence Modules)",
        "12. Comparative Evaluation of Frontier AI Models",
        "13. Modern Technology Stack & Infrastructure Design",
        "14. System Architecture & UML Diagrams",
        "15. Intelligent Multi-Agent Architecture (MAS)",
        "16. Architectural Innovations Beyond State-of-the-Art",
        "17. Future Scope & Emerging Horizons",
        "18. Engineering Challenges, Risks & Mitigation Strategies",
        "19. Conclusion & Industry Impact Statement",
        "20. Academic & Technical References (IEEE Format)"
    ]
    for item in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(item)
        r.font.size = Pt(11)
        r.font.color.rgb = COLOR_TEXT_MAIN

    doc.add_page_break()

    # SECTION 1
    add_custom_heading("1. Introduction & Software Engineering Foundations", 1)
    doc.add_paragraph("Software engineering is the application of a systematic, disciplined, and quantifiable approach to the design, development, operation, and maintenance of software systems. In high-velocity enterprise software development, source code represents the primary asset and formal representation of business logic, state machines, and algorithmic instruction sequences.")

    add_custom_heading("1.1 What is Code & Software Quality?", 2)
    doc.add_paragraph("Code is the bridge between human logic, domain specifications, and machine-level instruction execution. High-quality code must fulfill four core engineering dimensions:")
    bullets_s1 = [
        ("Maintainability: ", "Low coupling and high cohesion allowing seamless refactoring without downstream component breakage."),
        ("Readability: ", "Self-documenting variable semantics, standardized styling, and clear layout lowering onboarding friction."),
        ("Security: ", "Adherence to defensive programming principles (OWASP Top 10, CWE) preventing external adversarial exploitation."),
        ("Testability: ", "Comprehensive unit, integration, and regression test suites guaranteeing system reliability.")
    ]
    for bold_prefix, text in bullets_s1:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        r1 = p.add_run(bold_prefix)
        r1.bold = True
        r1.font.color.rgb = COLOR_PRIMARY
        p.add_run(text)

    # SECTION 2
    add_custom_heading("2. What is Code Review?", 1)
    doc.add_paragraph("Code Review is a software quality assurance practice where developers or automated intelligent agents examine source code changes before integrating them into the main repository branch.")
    add_callout_box("INDUSTRY CASE STUDIES",
                    "• Google: Over 80% of Google developers report that mandatory peer and static code reviews are vital to catching architectural flaws and preventing security regressions.\n"
                    "• Microsoft: Empirical research across 5,000+ engineers revealed that peer code reviews capture 60%+ of non-trivial logic bugs prior to official testing phases.")

    # SECTION 3
    add_custom_heading("3. Types of Code Reviews", 1)
    doc.add_paragraph("Organizations leverage diverse code review methodologies depending on team velocity, security requirements, and architectural complexity:")

    # Table for Review Types
    tbl3 = doc.add_table(rows=6, cols=4)
    tbl3.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers3 = ["Review Type", "Mechanism", "Primary Advantages", "Key Limitations"]
    for i, h in enumerate(headers3):
        cell = tbl3.cell(0, i)
        set_cell_background(cell, "4F46E5")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    data3 = [
        ("Manual Peer Review", "Async inspection of PR diffs by engineers", "Deep domain empathy & design checks", "High latency (24-72h), reviewer fatigue"),
        ("Pair Programming", "Two developers code & review simultaneously", "Zero feedback latency, high quality", "High resource cost (2x dev hours)"),
        ("Automated SAST Linter", "Rule-based AST static checks in CI", "Sub-second speed, 100% deterministic", "Lacks semantic reasoning, false noise"),
        ("AI-Assisted Review", "Multi-agent LLM reasoning over diffs", "24/7 fast context reasoning, sub-min PR review", "Requires AST grounding against hallucinations"),
        ("Continuous Review", "Real-time IDE & CI background scanning", "Instant developer feedback while typing", "Notification noise if uncalibrated")
    ]
    for row_idx, row_data in enumerate(data3, start=1):
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            cell = tbl3.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            cell.paragraphs[0].add_run(text).font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # SECTION 4
    add_custom_heading("4. Complete Code Review Process Pipeline", 1)
    doc.add_paragraph("The modern automated and peer code review workflow follows a strict 10-stage sequential pipeline:")
    pipeline_steps = [
        "1. Developer writes local feature code and runs pre-commit checks.",
        "2. Code is committed and pushed to remote Git repository branch.",
        "3. A Pull Request (PR) or Merge Request (MR) is formally opened.",
        "4. CI/CD triggers automated Static Analysis (Tree-Sitter, Semgrep linters).",
        "5. AI Multi-Agent System ingests PR diff and repository context.",
        "6. AI agents execute parallel security, bug, and performance audits.",
        "7. Automated inline comments and composite quality score (0-100) are posted.",
        "8. Senior human peer reviewer performs final architectural validation.",
        "9. Developer addresses comments or accepts 1-click AI self-healing patches.",
        "10. Branch receives formal approval, merges to main, and deploys via CI/CD."
    ]
    for step in pipeline_steps:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(step)
        r.font.size = Pt(10.5)

    # SECTION 5
    add_custom_heading("5. Code Review Best Practices", 1)
    doc.add_paragraph("To maximize review efficiency and maintain codebase hygiene, engineering teams enforce SOLID architecture, clean code standards, and PR size boundaries (<250 lines of code).")

    # SECTION 6
    add_custom_heading("6. Problems in Existing Code Review Systems", 1)
    doc.add_paragraph("Legacy manual review workflows introduce severe operational friction across enterprise software teams:")
    probs = [
        ("Reviewer Fatigue: ", "Cognitive accuracy degrades by up to 80% when reviewing changes exceeding 400 lines of code."),
        ("Turnaround Latency: ", "Average pull requests idle in review queues for 24 to 72 hours, blocking feature releases."),
        ("Missed Vulnerabilities: ", "Complex edge-case logic flaws, race conditions, and OWASP security risks bypass human review."),
        ("High Cost & Knowledge Silos: ", "Senior developer time spent on routine syntax checks costs organizations over $25,000 per engineer annually.")
    ]
    for bold_p, text in probs:
        p = doc.add_paragraph(style='List Bullet')
        r = p.add_run(bold_p)
        r.bold = True
        r.font.color.rgb = RGBColor(190, 18, 60)
        p.add_run(text)

    # SECTION 7
    add_custom_heading("7. Existing Code Review Tools (45+ Market Survey Matrix)", 1)
    doc.add_paragraph("A comprehensive evaluation of 45+ static analysis engines, code review platforms, SAST scanners, and AI coding assistants:")

    tbl7 = doc.add_table(rows=11, cols=4)
    tbl7.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers7 = ["Category", "Representative Tools", "AI Capabilities", "Pricing Model"]
    for i, h in enumerate(headers7):
        cell = tbl7.cell(0, i)
        set_cell_background(cell, "0284C7")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    matrix_data = [
        ("VCS Code Review", "GitHub PR, GitLab MR, Bitbucket, Gerrit, Phabricator, Review Board, Azure Repos", "Copilot PR summaries & Duo AI", "Freemium / Enterprise"),
        ("Static Quality Gates", "SonarQube, Codacy, CodeFactor, DeepSource, CodeScene", "ML quality scoring & autofix", "Subscription / SaaS"),
        ("Fast SAST Linters", "Semgrep, ESLint, Pylint, PMD, Checkstyle, Clang-Tidy, Super-Linter, MegaLinter", "Rule plugins & Semgrep Assistant", "Free Open Source"),
        ("Semantic SAST", "CodeQL, Amazon CodeGuru, Google Error Prone, Qodana, Coverity, Fortify", "ML bug detection & Datalog query", "Enterprise / Cloud"),
        ("Developer Security", "Snyk Code, Veracode, DeepCode", "DeepCode AI vulnerability scanner", "Freemium / Commercial"),
        ("Coverage & CI", "CircleCI Quality, Codecov", "PR delta coverage tracking", "Freemium / Commercial"),
        ("AI Code Reviewers", "CodiumAI (Qodo), Cursor Agent, Continue.dev, Sourcegraph Cody", "PR inspection & auto unit tests", "Subscription / Open Source"),
        ("Frontier LLMs", "Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro, DeepSeek-R1, Llama 3.3 70B, Codestral", "Deep code reasoning & 200k+ context", "Pay-per-token API"),
        ("Autonomous AI Agents", "Aider, OpenHands (OpenDevin), Windsurf", "Autonomous git repository edits", "Free Open Source / SaaS"),
        ("AI Coding Assistants", "GitHub Copilot, Amazon Q Developer", "Inline code completion & chat", "Subscription")
    ]
    for row_idx, row_data in enumerate(matrix_data, start=1):
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            cell = tbl7.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            cell.paragraphs[0].add_run(text).font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # SECTION 8 & 9
    add_custom_heading("8. Market Analysis & Trends", 1)
    doc.add_paragraph("Gartner predicts that by 2028, over 75% of enterprise software engineers will leverage AI code review and generation tools. Early enterprise adopters report a 42% reduction in PR lead time and a 34% drop in post-release production defects.")

    add_custom_heading("9. Core AI Technologies in Code Analysis", 1)
    doc.add_paragraph("The proposed platform merges four underlying computational techniques:\n"
                      "1. Abstract Syntax Tree (AST) Parsing via Tree-Sitter for language deconstruction.\n"
                      "2. Control Flow Graph (CFG) & Data Flow Analysis for tracing variable lifecycles.\n"
                      "3. Vector RAG Embeddings (pgvector/Qdrant) for repository-wide semantic retrieval.\n"
                      "4. Multi-Agent LLM Orchestration for parallel contextual reasoning.")

    # SECTION 10 & 11
    add_custom_heading("10. Proposed AI Code Review System Architecture", 1)
    doc.add_paragraph("The proposed system delivers instant, context-aware, evidence-grounded (with residual false-positive risk) code reviews with latency still to be measured. It utilizes a hybrid model combining deterministic static linters with frontier multi-agent LLM reasoning.")

    add_custom_heading("11. Proposed Features (30+ Intelligence Modules)", 1)
    feats = [
        "1. AI Bug & Edge Case Detection", "2. OWASP Vulnerability Audit", "3. Algorithmic Complexity Analysis (O(N^2))",
        "4. 1-Click Self-Healing Git Patches", "5. Composite Quality Score (0-100)", "6. Auto PyTest/Jest Unit Test Generation",
        "7. Interactive AI Chat with Repo", "8. Semantic Repository Search", "9. Smart Reviewer Recommendation",
        "10. Risk Prediction & Merge Readiness Indicator", "11. Historical Review Learning Engine", "12. Offline On-Premise LLM Support"
    ]
    for f in feats:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        p.add_run(f).bold = True

    # SECTION 12
    add_custom_heading("12. Comparative Evaluation of Frontier AI Models", 1)
    tbl12 = doc.add_table(rows=6, cols=5)
    tbl12.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers12 = ["Model Name", "Provider", "Context Window", "HumanEval", "Optimal Role"]
    for i, h in enumerate(headers12):
        cell = tbl12.cell(0, i)
        set_cell_background(cell, "7E22CE")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    data12 = [
        ("Claude 3.5 Sonnet", "Anthropic", "200,000 Tokens", "92.0%", "Primary Review & Refactoring Engine"),
        ("GPT-4o", "OpenAI", "128,000 Tokens", "90.2%", "Fast Pre-screening Analysis"),
        ("DeepSeek-R1", "DeepSeek", "64,000 Tokens", "90.8%", "Deep Algorithmic Logic Verification"),
        ("Gemini 1.5 Pro", "Google", "2,000,000 Tokens", "89.4%", "Entire Monorepo Context RAG"),
        ("Llama 3.3 70B", "Meta", "128,000 Tokens", "82.6%", "Air-Gapped On-Premise Privacy")
    ]
    for row_idx, row_data in enumerate(data12, start=1):
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            cell = tbl12.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            cell.paragraphs[0].add_run(text).font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # SECTIONS 13-15
    add_custom_heading("13. Tech Stack & Infrastructure Design", 1)
    doc.add_paragraph("Frontend: Next.js 14, React 18, Tailwind CSS, Shadcn UI\n"
                      "Backend: FastAPI (Python), Node.js, Celery Distributed Queue, Redis 7.2\n"
                      "Databases: PostgreSQL 16, pgvector, Qdrant Vector DB\n"
                      "DevOps & Infra: Docker, Kubernetes (AWS EKS), Helm, Prometheus & Grafana")

    add_custom_heading("14. System Architecture & Diagrams", 1)
    doc.add_paragraph("The platform uses an asynchronous microservice event-driven architecture connected via Redis queues, FastAPI gateways, and Tree-Sitter parsing workers.")

    add_custom_heading("15. Intelligent Multi-Agent Architecture (MAS)", 1)
    doc.add_paragraph("The multi-agent system deploys specialized autonomous sub-agents:\n"
                      "• Coordinator Agent: Ingests PR webhook and parses modified AST files.\n"
                      "• Security Agent: Audits OWASP Top 10, CWE databases, and secret leaks.\n"
                      "• Bug Logic Agent: Performs symbolic execution to find off-by-one errors.\n"
                      "• Performance Agent: Evaluates time/space complexity changes ($O(N^2)$ bottlenecks).\n"
                      "• Synthesis Agent: Deduplicates findings and formats inline GitHub markdown comments.")

    # SECTIONS 16-20
    add_custom_heading("16. Key Innovations Beyond State-of-the-Art", 1)
    doc.add_paragraph("1. Multi-Agent Cross-Verification: Aims to reduce unsupported model claims.\n"
                      "2. AST-Grounded LLM Reasoning: Grounding generative outputs in syntax tree facts.\n"
                      "3. 1-Click Self-Healing Executable Git Patches: Auto-generates exact diff fixes.\n"
                      "4. Repository Vector & Knowledge Graph Memory: Long-context codebase memory.")

    add_custom_heading("17. Future Scope & Emerging Horizons", 1)
    doc.add_paragraph("Autonomous self-healing repositories, voice-guided PR walk-throughs, and AR/VR spatial 3D codebase visualizers.")

    add_custom_heading("18. Challenges & Mitigations", 1)
    doc.add_paragraph("Hallucination risks are mitigated via Tree-Sitter AST grounding. Privacy concerns are solved through air-gapped on-premise execution using open-weights models (Llama 3.3 / DeepSeek).")

    add_custom_heading("19. Conclusion", 1)
    doc.add_paragraph("The proposed AI Code Review System bridges the gap between software delivery velocity and code quality, aiming to improve review speed and defect detection; neither effect has been measured for this project.")

    add_custom_heading("20. Academic & Technical References (IEEE Format)", 1)
    refs = [
        "[1] M. Fowler, Refactoring: Improving the Design of Existing Code, 2nd ed. Boston, MA: Addison-Wesley, 2018.",
        "[2] A. Bacchelli and C. Bird, 'Expectations, outcomes, and challenges of modern code review,' in Proc. IEEE/ACM 35th Int. Conf. Software Eng. (ICSE), 2013, pp. 712–721.",
        "[3] Anthropic, 'Claude 3.5 Sonnet Technical Report,' Tech. Rep., June 2024.",
        "[4] DeepSeek AI, 'DeepSeek-R1 Technical Report,' arXiv preprint arXiv:2501.12948, Jan. 2025."
    ]
    for r_text in refs:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.add_run(r_text).font.size = Pt(9.5)

    doc.save(output_path)
    print(f"Successfully generated DOCX document at: {output_path}")

if __name__ == "__main__":
    from pathlib import Path
    output = Path(__file__).resolve().parents[1] / "docs" / "proposal_regenerated.docx"
    create_proposal_docx(str(output))
