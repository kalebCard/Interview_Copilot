import pytest
from copilot.core.config import build_system_prompt

def test_build_system_prompt():
    context = "Candidate name: Alice. 5 years of Python experience."
    category = "Focus on Python technical details."
    
    prompt = build_system_prompt(context, category)
    
    assert "Candidate name: Alice" in prompt
    assert "Focus on Python technical details." in prompt
    assert "[ESPAÑOL]:" in prompt
    assert "[INGLÉS]:" in prompt
    assert "[CÓDIGO]" in prompt
