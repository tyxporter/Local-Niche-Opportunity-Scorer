"""Phase 7 — branded .docx renders the six sections; wrapper never leaks in."""

from docx import Document

from lnos.brief import Brief, Section, SECTION_TITLES
from lnos.delivery import CETERA_REMINDER
from lnos import docx_export


def _brief() -> Brief:
    bodies = {
        1: "County unemployment rate: 3.4 % (as of 2026-04-01)\nNote: snapshot narrowed.",
        2: "Healthcare employers anchor the market; reachable via seminars.",
        3: "The niche intersects the dominant local employer base.",
        4: "Pre-retiree seminar series, delivered with the Carson seminar kit.",
        5: "1. Seminar series — fits the strongest channel\n2. Email — low lift\nStart with #1.",
        6: "Approved disclosure text, verbatim.\n\nThis is a local marketing-opportunity "
           "brief, not investment advice or a market forecast.",
    }
    sections = [Section(n, SECTION_TITLES[n - 1], bodies[n]) for n in range(1, 7)]
    return Brief("cwmg-omaha-cia", "CWMG Omaha LLC", "2026-06-11", sections)


def _text(path):
    return "\n".join(p.text for p in Document(str(path)).paragraphs)


def test_render_writes_correctly_named_file(tmp_path):
    path = docx_export.render_brief_docx(_brief(), out_dir=tmp_path)
    assert path.exists()
    assert path.name == "CWMG-Omaha-LLC-Local-Opportunity-Brief-2026-06-11.docx"


def test_all_six_sections_present_in_order(tmp_path):
    path = docx_export.render_brief_docx(_brief(), out_dir=tmp_path)
    text = _text(path)
    positions = [text.find(f"{n}. {SECTION_TITLES[n - 1]}") for n in range(1, 7)]
    assert all(p >= 0 for p in positions)
    assert positions == sorted(positions)  # in order


def test_deliverable_title_and_logo_placeholder(tmp_path):
    text = _text(docx_export.render_brief_docx(_brief(), out_dir=tmp_path))
    assert "Local Marketing Opportunity Brief" in text
    assert "logo — pending" in text  # flagged placeholder, not silent omission


def test_disclosure_and_standing_line_render(tmp_path):
    text = _text(docx_export.render_brief_docx(_brief(), out_dir=tmp_path))
    assert "Approved disclosure text, verbatim." in text
    assert "not investment advice" in text


def test_delivery_wrapper_content_never_in_docx(tmp_path):
    text = _text(docx_export.render_brief_docx(_brief(), out_dir=tmp_path))
    assert CETERA_REMINDER not in text
    assert "prioritization read" not in text.lower()


def test_docx_export_does_not_import_delivery():
    import inspect
    src = inspect.getsource(docx_export)
    assert "import delivery" not in src and "from .delivery" not in src
