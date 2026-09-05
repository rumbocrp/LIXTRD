"""Auditoría Automatizada de Estándar Anti-AI Slop y UI/UX Pro Max."""

import re
from pathlib import Path
from sistema_luces.ui.templates import render_industrial_console_html

def test_zero_emojis_in_html_output():
    """Verifica que no exista ningún emoji en el HTML generado (Sin 1)."""
    html = render_industrial_console_html()
    # Rango Unicode de emojis comunes
    emoji_pattern = re.compile(
        r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U00002600-\U000026FF\U00002700-\U000027BF]"
    )
    matches = emoji_pattern.findall(html)
    assert len(matches) == 0, f"Violación Anti-AI Slop: Emojis detectados en HTML: {matches}"

def test_no_glassmorphism_or_neon_halos_in_css():
    """Verifica la eliminación de halos difusos y blurs apilados (Sin 2 & Sin 3)."""
    css_path = Path(__file__).parent.parent / "src" / "sistema_luces" / "ui" / "static" / "styles.css"
    css_content = css_path.read_text(encoding="utf-8")
    
    assert "backdrop-filter" not in css_content, "Violación Anti-AI Slop: backdrop-filter / glassmorphism detectado"
    assert "blur(" not in css_content, "Violación Anti-AI Slop: blur() decorativo detectado"
    assert "box-shadow: 0 0" not in css_content, "Violación Anti-AI Slop: halo difuso box-shadow neon detectado"

def test_tabular_numerals_presence():
    """Verifica que las clases tipográficas tabulares existan en el CSS (Sin 4)."""
    css_path = Path(__file__).parent.parent / "src" / "sistema_luces" / "ui" / "static" / "styles.css"
    css_content = css_path.read_text(encoding="utf-8")
    assert "font-variant-numeric: tabular-nums" in css_content

def test_hardware_optical_bezel_markup():
    """Verifica la estructura física del bisel óptico mecanizado y micropunto especular."""
    html = render_industrial_console_html()
    assert "optical-bezel" in html
    assert "diode-green" in html
    assert "diode-yellow" in html
    assert "diode-red" in html
    assert "specular-dot" in html
