"""
test_pipeline_steps.py — unit tests for the individual steps of the 4-step pipeline.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import _negate_operator, _normalise_property, translate_claim

class TestPipelineSteps:
    def test_negate_operator(self):
        assert _negate_operator("<") == ">="
        assert _negate_operator("<=") == ">"
        assert _negate_operator("==") == "!="
        assert _negate_operator("!=") == "=="
        assert _negate_operator(">") == "<="
        assert _negate_operator(">=") == "<"

    def test_normalise_property(self):
        assert _normalise_property("result < x") == "result < x"
        assert _normalise_property("```result < x```") == "result < x"
        assert _normalise_property("  result < x  \n") == "result < x"

    @patch("pipeline.translate._ask_ollama")
    @patch("pipeline.translate._load_prompt")
    def test_translate_claim_pipeline(self, mock_load_prompt, mock_ask_ollama):
        # Mocking Step 1 response
        # Mocking Step 2 response
        mock_ask_ollama.side_effect = [
            "result < x",  # Step 1
            '{"lhs": "result", "op": "<", "rhs": "x"}' # Step 2
        ]
        
        # We don't care about the prompts for this unit test
        mock_load_prompt.return_value = "dummy prompt"
        
        with patch.dict(os.environ, {"DOCCHECK_BACKEND": "ollama"}):
            result = translate_claim("uint64_t f(uint64_t x){}", "output smaller than input")
            
        assert result == "if (result >= x) { exit(1); }"
        assert mock_ask_ollama.call_count == 2

    @patch("pipeline.translate._ask_ollama")
    @patch("pipeline.translate._load_prompt")
    def test_translate_claim_with_normalization(self, mock_load_prompt, mock_ask_ollama):
        # Test that Step 4 correctly normalizes pointer derefs and function calls
        mock_ask_ollama.side_effect = [
            "result == absolute(x)",  # Step 1
            '{"lhs": "result", "op": "==", "rhs": "absolute(x)"}' # Step 2
        ]
        
        mock_load_prompt.return_value = "dummy prompt"
        
        with patch.dict(os.environ, {"DOCCHECK_BACKEND": "ollama"}):
            # Pass func_name and param_names to ensure normalization happens in Step 4
            result = translate_claim("uint64_t absolute(uint64_t x){}", "output equals absolute input", 
                                     func_name="absolute", param_names=["x"])
            
        assert result == "if (result != result) { exit(1); }" # absolute(x) normalized to result
