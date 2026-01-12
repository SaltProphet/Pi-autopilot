"""Tests for llm_client module."""
import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from services.llm_client import LLMClient
from services.cost_governor import CostGovernor, CostLimitExceeded


@pytest.fixture
def mock_cost_governor():
    """Create a mock CostGovernor."""
    governor = Mock(spec=CostGovernor)
    governor.estimate_tokens.return_value = 100
    governor.check_limits_before_call.return_value = None
    governor.record_usage.return_value = None
    return governor


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = MagicMock()
    return mock_client


@pytest.mark.unit
class TestLLMClient:
    """Test suite for LLMClient class."""

    @patch('services.llm_client.OpenAI')
    def test_llm_client_initialization(self, mock_openai_class, mock_cost_governor):
        """Test LLMClient initialization."""
        client = LLMClient(mock_cost_governor)
        
        assert client.cost_governor == mock_cost_governor
        mock_openai_class.assert_called_once()

    @patch('services.llm_client.OpenAI')
    def test_call_structured_success(self, mock_openai_class, mock_cost_governor):
        """Test successful structured LLM call."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"result": "success"}'
        mock_response.usage.prompt_tokens = 150
        mock_response.usage.completion_tokens = 50
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client_instance
        
        # Create client and call
        client = LLMClient(mock_cost_governor)
        result = client.call_structured("System prompt", "User content", max_tokens=2000)
        
        # Verify result
        assert isinstance(result, dict)
        assert result["result"] == "success"
        
        # Verify cost governor was called
        mock_cost_governor.estimate_tokens.assert_called()
        mock_cost_governor.check_limits_before_call.assert_called_once()
        mock_cost_governor.record_usage.assert_called_once_with(150, 50)

    @patch('services.llm_client.OpenAI')
    def test_call_text_success(self, mock_openai_class, mock_cost_governor):
        """Test successful text LLM call."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Generated text content"
        mock_response.usage.prompt_tokens = 200
        mock_response.usage.completion_tokens = 100
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client_instance
        
        # Create client and call
        client = LLMClient(mock_cost_governor)
        result = client.call_text("System prompt", "User content", max_tokens=3000)
        
        # Verify result
        assert isinstance(result, str)
        assert result == "Generated text content"
        
        # Verify cost governor was called
        mock_cost_governor.check_limits_before_call.assert_called_once()
        mock_cost_governor.record_usage.assert_called_once_with(200, 100)

    @patch('services.llm_client.OpenAI')
    def test_cost_limit_exceeded(self, mock_openai_class, mock_cost_governor):
        """Test that CostLimitExceeded is raised when limits exceeded."""
        # Setup cost governor to raise exception
        mock_cost_governor.check_limits_before_call.side_effect = CostLimitExceeded("Limit exceeded")
        
        client = LLMClient(mock_cost_governor)
        
        # Should raise CostLimitExceeded
        with pytest.raises(CostLimitExceeded):
            client.call_structured("System prompt", "User content")

    @patch('services.llm_client.OpenAI')
    def test_call_structured_json_parsing(self, mock_openai_class, mock_cost_governor):
        """Test that structured call properly parses JSON response."""
        # Setup mock response with complex JSON
        complex_json = {
            "discard": False,
            "problem_summary": "Test problem",
            "urgency_score": 8,
            "evidence_quotes": ["Quote 1", "Quote 2"]
        }
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(complex_json)
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client_instance
        
        client = LLMClient(mock_cost_governor)
        result = client.call_structured("System", "User")
        
        # Verify complex JSON was parsed correctly
        assert result["discard"] is False
        assert result["problem_summary"] == "Test problem"
        assert result["urgency_score"] == 8
        assert len(result["evidence_quotes"]) == 2

    @patch('services.llm_client.OpenAI')
    def test_call_with_custom_max_tokens(self, mock_openai_class, mock_cost_governor):
        """Test that custom max_tokens is passed correctly."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"test": "data"}'
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 25
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client_instance
        
        client = LLMClient(mock_cost_governor)
        client.call_structured("System", "User", max_tokens=1500)
        
        # Verify create was called with correct max_tokens
        call_args = mock_client_instance.chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 1500

    @patch('services.llm_client.OpenAI')
    def test_call_records_actual_token_usage(self, mock_openai_class, mock_cost_governor):
        """Test that actual token usage from response is recorded."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Text"
        mock_response.usage.prompt_tokens = 300
        mock_response.usage.completion_tokens = 150
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client_instance
        
        client = LLMClient(mock_cost_governor)
        client.call_text("System", "User")
        
        # Verify actual tokens were recorded
        mock_cost_governor.record_usage.assert_called_once_with(300, 150)

    @patch('services.llm_client.OpenAI')
    def test_json_response_format_set(self, mock_openai_class, mock_cost_governor):
        """Test that structured call sets response_format to json_object."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"key": "value"}'
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 25
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client_instance
        
        client = LLMClient(mock_cost_governor)
        client.call_structured("System", "User")
        
        # Verify response_format was set
        call_args = mock_client_instance.chat.completions.create.call_args
        assert call_args[1]["response_format"] == {"type": "json_object"}
