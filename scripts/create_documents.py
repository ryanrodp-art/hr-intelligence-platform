"""Generate four Acme Corp HR policy PDFs using PyMuPDF."""

import fitz
import os

# ── Page geometry ──────────────────────────────────────────────────────────
W, H = 595, 842          # A4 in points
ML, MR, MT, MB = 60, 60, 70, 70
CW = W - ML - MR         # content width = 475

# ── Colours ────────────────────────────────────────────────────────────────
NAVY   = (0.08, 0.18, 0.42)
WHITE  = (1, 1, 1)
BLACK  = (0, 0, 0)
GRAY   = (0.45, 0.45, 0.45)
LGRAY  = (0.93, 0.93, 0.96)

# ── Fonts ──────────────────────────────────────────────────────────────────
REGULAR = "helv"
BOLD    = "hebo"

# Approximate character width at fontsize 10 (Helvetica):
# 475 content points / ~5.8 pts per char ≈ 81 chars per line
CHARS_PER_LINE = 81
CHARS_INDENTED = 72   # with 20 pt bullet indent


def _wrap(text: str, chars: int) -> list[str]:
    """Split text into lines of at most `chars` characters."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > chars:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).lstrip()
    if line:
        lines.append(line)
    return lines


class PDFDoc:
    def __init__(self):
        self.doc = fitz.open()
        self.pg: fitz.Page | None = None
        self.y = MT
        self._new_page()

    def _new_page(self):
        self.pg = self.doc.new_page(width=W, height=H)
        self.y = MT

    def _need(self, pts: float):
        """Start a new page if fewer than `pts` points remain."""
        if self.y + pts > H - MB:
            self._new_page()

    # ── Structural elements ────────────────────────────────────────────────

    def add_header(self, title: str, version: str, effective: str):
        """Coloured banner covering the top of the first page."""
        self.pg.draw_rect(fitz.Rect(0, 0, W, 105), color=NAVY, fill=NAVY)
        self.pg.insert_text(fitz.Point(ML, 48), title,
                            fontsize=17, fontname=BOLD, color=WHITE)
        subtitle = f"Version {version}   |   Effective: {effective}   |   Acme Corp"
        self.pg.insert_text(fitz.Point(ML, 72), subtitle,
                            fontsize=9.5, fontname=REGULAR, color=(0.82, 0.82, 0.88))
        # Extra gap after header so extractor emits \n\n before section 1
        self.y = 140

    def add_section(self, number: str, title: str):
        """Numbered section heading with a coloured rule.

        Uses a 22 pt leading gap (up from 8) so PyMuPDF's text-block detector
        sees enough whitespace to emit \\n\\n before each section heading.
        """
        self._need(50)
        self.y += 22          # ← increased from 8; creates block boundary in extraction
        self.pg.draw_line(fitz.Point(ML, self.y),
                          fitz.Point(W - MR, self.y),
                          color=NAVY, width=0.8)
        self.y += 10
        self.pg.insert_text(fitz.Point(ML, self.y),
                            f"{number}.  {title}",
                            fontsize=12, fontname=BOLD, color=NAVY)
        self.y += 18

    def add_text(self, text: str, indent: float = 0):
        """Body paragraph — auto-wrapped."""
        chars = int(CHARS_PER_LINE * (1 - indent / CW))
        for line in _wrap(text, chars):
            self._need(14)
            self.pg.insert_text(fitz.Point(ML + indent, self.y),
                                line, fontsize=10, fontname=REGULAR, color=BLACK)
            self.y += 14
        self.y += 4

    def add_bullet(self, text: str, indent: float = 18):
        """Single bulleted line — auto-wrapped."""
        self._need(14)
        self.pg.insert_text(fitz.Point(ML + indent - 10, self.y),
                            "•", fontsize=10, fontname=REGULAR, color=NAVY)
        chars = int(CHARS_INDENTED * (1 - (indent - 18) / CW))
        lines = _wrap(text, chars)
        for line in lines:
            self._need(14)
            self.pg.insert_text(fitz.Point(ML + indent, self.y),
                                line, fontsize=10, fontname=REGULAR, color=BLACK)
            self.y += 14

    def add_label(self, label: str, value: str):
        """Bold label followed by regular value on the same line."""
        self._need(14)
        lw = len(label) * 5.8
        self.pg.insert_text(fitz.Point(ML, self.y),
                            label, fontsize=10, fontname=BOLD, color=BLACK)
        self.pg.insert_text(fitz.Point(ML + lw, self.y),
                            value, fontsize=10, fontname=REGULAR, color=BLACK)
        self.y += 14

    def add_contact(self, text: str):
        """Highlighted contact box at the end of a document."""
        self._need(42)
        self.y += 6
        box = fitz.Rect(ML, self.y, W - MR, self.y + 30)
        self.pg.draw_rect(box, color=LGRAY, fill=LGRAY)
        self.pg.insert_text(fitz.Point(ML + 10, self.y + 18),
                            text, fontsize=10, fontname=BOLD, color=NAVY)
        self.y += 40

    def gap(self, pts: float = 8):
        self.y += pts

    def new_page(self):
        """Force a page break — used to keep major sections on their own page."""
        self._new_page()

    def _add_page_numbers(self):
        n = self.doc.page_count
        for i, pg in enumerate(self.doc):
            pg.insert_text(fitz.Point(W / 2 - 30, H - 28),
                           f"Page {i + 1} of {n}",
                           fontsize=8.5, fontname=REGULAR, color=GRAY)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._add_page_numbers()
        self.doc.save(path)
        self.doc.close()
        size = os.path.getsize(path)
        print(f"  ✓ {path}  ({size:,} bytes, {self.doc.page_count if not self.doc.is_closed else '?'} pages)")


def _size_str(path):
    size = os.path.getsize(path)
    pages = fitz.open(path).page_count
    return f"{size:,} bytes, {pages} page{'s' if pages > 1 else ''}"


# ══════════════════════════════════════════════════════════════════════════════
# Document 1 — Leave Policy
# ══════════════════════════════════════════════════════════════════════════════
def create_leave_policy():
    path = "documents/policies/leave_policy.pdf"
    d = PDFDoc()
    d.add_header("Acme Corp — Employee Leave Policy", "2.1", "January 1, 2024")

    d.add_section("1", "Overview")
    d.add_text("This policy sets out the leave entitlements and procedures for all Acme Corp employees. "
               "It applies to all full-time and part-time staff employed on a permanent or fixed-term basis. "
               "The purpose of this policy is to ensure employees can take appropriate time away from work "
               "while maintaining operational continuity.")

    d.add_section("2", "Annual Leave")
    d.add_bullet("Full-time employees: 25 days per calendar year")
    d.add_bullet("Part-time employees: pro-rated based on contracted hours")
    d.add_bullet("Accrual rate: 2.08 days per month from hire date")
    d.gap(6)
    d.add_bullet("Maximum carryover: 5 days to the following calendar year")
    d.add_bullet("Minimum notice required: 2 weeks for planned leave")
    d.add_bullet("Leave in excess of carryover limit is forfeited at year end")

    d.add_section("3", "Sick Leave")
    d.add_bullet("Entitlement: 10 days per calendar year")
    d.add_bullet("Sick leave does not accrue and does not carry over to the following year")
    d.gap(6)
    d.add_bullet("Doctor's certificate required for absences exceeding 3 consecutive days")
    d.add_bullet("Sick leave cannot be used for planned absences or elective procedures")
    d.add_bullet("Repeated short-term absence may trigger a review under the attendance policy")

    d.add_section("4", "Parental Leave")
    d.add_bullet("Primary caregiver: 16 weeks fully paid")
    d.add_bullet("Secondary caregiver: 4 weeks fully paid")
    d.gap(6)
    d.add_bullet("Eligibility: 6 months continuous service prior to leave commencement")
    d.add_bullet("Leave must be taken within 12 months of birth or adoption")
    d.add_bullet("Employees must give 8 weeks' written notice to HR where possible")

    d.add_section("5", "Emergency Leave")
    d.add_bullet("Up to 3 days per incident, paid")
    d.add_bullet("Covers bereavement, family medical emergency, and natural disaster")
    d.add_bullet("Manager approval required within 24 hours of commencement")
    d.add_bullet("HR may request supporting documentation")

    d.add_section("6", "Unpaid Leave")
    d.add_bullet("Available after exhausting all paid leave entitlements")
    d.add_bullet("Requires HR Director approval before commencement")
    d.add_bullet("Maximum 3 months in any 12-month rolling period")
    d.add_bullet("Employee benefits continue during unpaid leave unless otherwise agreed")

    d.add_section("7", "Leave Application Process")
    d.add_bullet("Submit leave request via the HR portal at least 2 weeks in advance")
    d.add_bullet("Manager must approve or decline within 5 business days")
    d.add_bullet("HR sends confirmation email within 2 business days of manager approval")
    d.gap(6)
    d.add_bullet("Emergency leave: notify manager by phone or message immediately")
    d.add_bullet("Disputes regarding leave decisions should be escalated to the HR Business Partner")

    d.add_section("8", "Contact")
    d.add_contact("HR Department   hr@acmecorp.com   |   ext. 4100")

    d.save(path)
    print(f"     {_size_str(path)}")


# ══════════════════════════════════════════════════════════════════════════════
# Document 2 — Code of Conduct
# ══════════════════════════════════════════════════════════════════════════════
def create_code_of_conduct():
    path = "documents/policies/code_of_conduct.pdf"
    d = PDFDoc()
    d.add_header("Acme Corp — Code of Conduct", "3.0", "January 1, 2024")

    d.add_section("1", "Overview")
    d.add_text("Acme Corp is committed to maintaining a respectful, inclusive, and ethical workplace. "
               "This Code of Conduct outlines the standards of behaviour expected of every employee, "
               "contractor, and visitor. Our core values — integrity, respect, collaboration, and "
               "accountability — underpin everything we do.")

    d.add_section("2", "Professional Behaviour")
    d.add_bullet("Treat all colleagues, clients, and partners with respect and dignity at all times")
    d.add_bullet("Maintain strict confidentiality of company, client, and employee information")
    d.gap(6)
    d.add_bullet("Avoid conflicts of interest; any potential conflict must be declared to your line manager in writing")
    d.add_bullet("Represent Acme Corp professionally in all external communications and interactions")
    d.add_bullet("Use company resources responsibly and only for legitimate business purposes")

    d.add_section("3", "Anti-Harassment Policy")
    d.add_text("Acme Corp operates a zero-tolerance policy for harassment of any kind.")
    d.add_bullet("Harassment includes sexual, racial, religious, disability-based, and age-based conduct")
    d.add_bullet("This policy applies to employees, contractors, clients, and visitors on company premises")
    d.gap(6)
    d.add_bullet("Harassment via digital channels (email, Slack, social media) is equally prohibited")
    d.add_bullet("Any employee found to have harassed another person will face disciplinary action up to and including dismissal")

    d.add_section("4", "Reporting and Grievance Process")
    d.add_bullet("Step 1: Raise the concern with your direct manager informally")
    d.add_bullet("Step 2: If unresolved within 5 business days, escalate to your HR Business Partner")
    d.add_bullet("Step 3: Submit a formal grievance form to the HR Director")
    d.add_bullet("Step 4: An independent investigation will be completed within 15 business days")
    d.gap(6)
    d.add_bullet("All reports are treated with strict confidentiality")
    d.add_bullet("No retaliation policy: employees who raise concerns in good faith are fully protected")

    d.add_section("5", "Disciplinary Procedure")
    d.add_bullet("Stage 1: Verbal warning — recorded in employee file")
    d.add_bullet("Stage 2: Written warning — valid for 12 months")
    d.add_bullet("Stage 3: Final written warning — valid for 12 months")
    d.add_bullet("Stage 4: Dismissal — employee has the right of appeal within 10 business days")
    d.gap(6)
    d.add_text("Gross misconduct may result in immediate dismissal without prior warnings.")

    d.add_section("6", "Social Media Policy")
    d.add_bullet("Do not share confidential company information on any public platform")
    d.add_bullet("Do not make statements that could damage Acme Corp's reputation or brand")
    d.add_bullet("Employees are personally liable for their own social media content")
    d.add_bullet("When in doubt, consult the Communications team before posting")

    d.add_section("7", "Contact")
    d.add_contact("HR Business Partner   hrbp@acmecorp.com   |   ext. 4200")

    d.save(path)
    print(f"     {_size_str(path)}")


# ══════════════════════════════════════════════════════════════════════════════
# Document 3 — Benefits Guide
# ══════════════════════════════════════════════════════════════════════════════
def create_benefits_guide():
    path = "documents/policies/benefits_guide.pdf"
    d = PDFDoc()
    d.add_header("Acme Corp — Employee Benefits Guide", "1.4", "January 1, 2024")

    d.add_section("1", "Overview")
    d.add_text("Acme Corp's total compensation philosophy is to provide a comprehensive and competitive "
               "package that supports the health, financial security, and professional growth of every "
               "employee. This guide summarises the benefits available to all eligible employees.")

    d.add_section("2", "Health Insurance")
    d.add_bullet("Provider: BlueCross BlueShield Premier Plan")
    d.add_bullet("Employee coverage: 100% company-paid")
    d.add_bullet("Dependant coverage: 80% company-paid, 20% employee contribution")
    d.add_bullet("Dental and vision care included in the Premier Plan")
    d.gap(6)
    d.add_bullet("Coverage is effective from the first day of employment")
    d.add_bullet("Contact the Benefits Team to add or update dependants within 30 days of a qualifying life event")

    d.add_section("3", "Retirement Plan")
    d.add_bullet("Provider: Fidelity 401(k) Plan")
    d.add_bullet("Employee contribution: up to 6% of base salary (pre-tax)")
    d.add_bullet("Company match: 100% of first 3% contributed, 50% of next 3% contributed")
    d.gap(6)
    d.add_bullet("Vesting: employee contributions are immediately vested; company match vests over 3 years")
    d.add_bullet("Eligible to enrol after 90 days of employment")
    d.add_bullet("Enrolment via the Fidelity NetBenefits portal")

    d.add_section("4", "Wellness Benefits")
    d.add_bullet("Gym membership subsidy: $50 per month, reimbursed quarterly")
    d.add_bullet("Mental health support: 6 free confidential sessions per year via the EAP")
    d.add_bullet("Annual wellness allowance: $500 for eligible expenses (fitness equipment, apps, nutrition)")
    d.add_bullet("Submit wellness reimbursement claims via the HR portal with receipts")

    d.add_section("5", "Life and Disability Insurance")
    d.add_bullet("Life insurance: 2x annual base salary, 100% company-paid")
    d.add_bullet("Short-term disability: 60% of base salary for up to 26 weeks")
    d.add_bullet("Long-term disability: 60% of base salary after 26 weeks, until recovery or retirement")
    d.add_bullet("Employee Assistance Program (EAP): 24/7 confidential support line for personal and financial issues")

    d.add_section("6", "Stock Options")
    d.add_bullet("Eligibility: Senior Manager level and above")
    d.add_bullet("Annual stock option grant reviewed each December")
    d.add_bullet("Vesting schedule: 4 years with a 1-year cliff (25% vests after year 1, monthly thereafter)")
    d.add_bullet("Speak with your manager and HR Business Partner for details specific to your role")

    d.add_section("7", "Professional Development")
    d.add_bullet("Annual learning budget: $2,000 per employee")
    d.add_bullet("Eligible expenses: courses, conferences, certifications, books, and workshops")
    d.add_bullet("Requires manager approval before purchase")
    d.add_bullet("Submit reimbursement via the HR portal within 30 days of expense")

    d.add_section("8", "Contact")
    d.add_contact("Benefits Team   benefits@acmecorp.com   |   ext. 4300")

    d.save(path)
    print(f"     {_size_str(path)}")


# ══════════════════════════════════════════════════════════════════════════════
# Document 4 — Employee Handbook
# ══════════════════════════════════════════════════════════════════════════════
def create_employee_handbook():
    path = "documents/handbooks/employee_handbook.pdf"
    d = PDFDoc()
    d.add_header("Acme Corp — Employee Handbook", "4.2", "January 1, 2024")

    d.add_section("1", "Welcome to Acme Corp")
    d.add_text("Welcome to Acme Corp. Our mission is to build innovative products that make a meaningful "
               "difference for our customers. We believe that a diverse, engaged, and well-supported "
               "workforce is the foundation of everything we achieve. This handbook is your guide to "
               "working life at Acme Corp.")

    d.add_section("2", "Onboarding")
    d.add_bullet("Week 1: Company orientation, system setup, IT provisioning, meet your team")
    d.add_bullet("Weeks 2–4: Role-specific training programme delivered by your line manager")
    d.gap(6)
    d.add_bullet("30-day check-in: one-to-one with your HR Business Partner")
    d.add_bullet("90-day probation review: formal performance review with your line manager")
    d.add_bullet("Buddy programme: you will be assigned an onboarding buddy for your first month")

    d.add_section("3", "Probation Period")
    d.add_bullet("Duration: 90 days for all new employees")
    d.add_bullet("60-day review: informal check-in with your line manager")
    d.add_bullet("90-day review: formal assessment — pass, extend, or not confirm employment")
    d.gap(6)
    d.add_bullet("Extension: probation may be extended by up to 30 days with HR Director approval")
    d.add_bullet("Notice during probation: either party may terminate with 1 week's written notice")

    d.add_section("4", "Working Hours")
    d.add_bullet("Standard hours: 9:00 am – 5:00 pm, Monday to Friday (37.5 hours per week)")
    d.add_bullet("Core hours: 10:00 am – 3:00 pm — all employees expected to be available")
    d.gap(6)
    d.add_bullet("Flexible working: available with manager agreement, subject to business needs")
    d.add_bullet("Overtime: must be pre-approved by your manager; compensated at 1.5x your hourly rate")
    d.add_bullet("Time off in lieu (TOIL): may be offered instead of overtime pay by mutual agreement")

    # Page 2 — Remote work, performance, termination, IT, contacts
    d.new_page()

    d.add_section("5", "Remote Work Policy")
    d.add_bullet("Hybrid model: minimum 3 days in the office per week")
    d.add_bullet("Remote work: maximum 2 days per week")
    d.add_bullet("Home office equipment allowance: $500 for new employees (one-time)")
    d.gap(6)
    d.add_bullet("Employees must be available and responsive during core hours when working remotely")
    d.add_bullet("Remote work privileges may be reviewed if performance or collaboration is impacted")

    d.add_section("6", "Performance Management")
    d.add_bullet("Mid-year review: conducted each June — objectives review and development discussion")
    d.add_bullet("Annual review: conducted each December — full performance assessment and salary review")
    d.add_bullet("Performance Improvement Plan (PIP): 60-day structured improvement plan if required")
    d.gap(6)
    d.add_bullet("Promotions and level changes reviewed annually in December")
    d.add_bullet("Continuous feedback encouraged via regular one-to-ones with your manager")

    d.add_section("7", "Termination")
    d.add_bullet("Notice period: 4 weeks written notice by either party (or as per employment contract)")
    d.add_bullet("Payment in lieu of notice: may be offered at the company's discretion")
    d.add_bullet("Final paycheck: processed within 5 business days of last working day")
    d.gap(6)
    d.add_bullet("Exit interview: conducted by HR within the final week of employment")
    d.add_bullet("Return of equipment: all company property must be returned within 5 business days")

    d.add_section("8", "IT and Equipment")
    d.add_bullet("Laptop provided on your first day — configured by the IT team")
    d.add_bullet("All company equipment must be returned within 5 business days of leaving")
    d.add_bullet("Do not install unauthorised software on company devices")
    d.add_bullet("IT Helpdesk: it@acmecorp.com | ext. 5000")

    d.add_section("9", "Key Contacts")
    d.add_bullet("HR Department: hr@acmecorp.com | ext. 4100")
    d.add_bullet("HR Director: Sarah Mitchell | sarah.mitchell@acmecorp.com")
    d.add_bullet("IT Helpdesk: it@acmecorp.com | ext. 5000")
    d.add_bullet("Payroll: payroll@acmecorp.com | ext. 4400")
    d.add_bullet("Benefits Team: benefits@acmecorp.com | ext. 4300")

    d.add_contact("HR Department   hr@acmecorp.com   |   ext. 4100")

    d.save(path)
    print(f"     {_size_str(path)}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Creating Acme Corp HR documents...\n")

    create_leave_policy()
    create_code_of_conduct()
    create_benefits_guide()
    create_employee_handbook()

    print("\nDone — 4 PDFs created.")
