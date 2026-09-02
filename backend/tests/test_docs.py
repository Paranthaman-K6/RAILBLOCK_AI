import pathlib

def test_docs_exist_and_headings():
    root = pathlib.Path(__file__).parent.parent.parent
    # AGENTS.md
    agents = root / "AGENTS.md"
    assert agents.exists(), "AGENTS.md missing"
    text = agents.read_text(encoding="utf-8")
    assert "Prototype disclaimer" in text
    assert "Immutable Rule" in text
    # implementation-spec
    impl = root / "docs" / "implementation-spec.md"
    assert impl.exists(), "implementation-spec.md missing"
    text = impl.read_text(encoding="utf-8")
    assert "Canonical Entities" in text
    assert "Routes" in text
    # problem-understanding
    prob = root / "docs" / "problem-understanding.md"
    assert prob.exists()
    text = prob.read_text(encoding="utf-8")
    assert "Rolling" in text and "block" in text.lower()
    assert "Current vs Required" in text
    # manual-acceptance
    man = root / "docs" / "manual-acceptance-execution.md"
    assert man.exists()
    text = man.read_text(encoding="utf-8")
    assert "30-Step Demo" in text
