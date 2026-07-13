import pytest
from copilot.core.config import build_system_prompt

def test_build_system_prompt():
    context = "Candidate name: Alice. 5 years of Python experience."
    
    prompt = build_system_prompt(context)
    
    assert "Candidate name: Alice" in prompt
    assert "[ESPAÑOL]:" in prompt
    assert "[INGLÉS]:" in prompt
    assert "[CÓDIGO]" in prompt
    assert "[CATEGORÍA:" in prompt
    assert "Algoritmos" in prompt
    assert "System Design" in prompt

