import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src directory to Python path to import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import utils

# Define a class for mock OpenAI and Azure OpenAI responses
class MockOpenAIResponse:
    def __init__(self, data):
        self.data = data

class MockAzureOpenAIResponse:
    def __init__(self, data):
        self.data = data

class MockEmbeddingData:
    def __init__(self, embedding):
        self.embedding = embedding

class MockChatCompletionChoice:
    def __init__(self, content):
        self.message = MockChatMessage(content)

class MockChatMessage:
    def __init__(self, content):
        self.content = content

class MockChatCompletionResponse:
    def __init__(self, content):
        self.choices = [MockChatCompletionChoice(content)]


class TestUtilsAzureIntegration(unittest.TestCase):

    def setUp(self):
        # Store original environment variables
        self.original_env = os.environ.copy()

        # Clear Azure and OpenAI env vars before each test
        env_vars_to_clear = [
            "OPENAI_API_KEY",
            "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_CHAT_DEPLOYMENT", "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            "MODEL_CHOICE"
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

        # Reset the utils.azure_openai_client to None as it's initialized at import time
        utils.azure_openai_client = None
        utils.openai.api_key = None


    def tearDown(self):
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)

        # Re-initialize azure_openai_client based on original env
        utils.AZURE_OPENAI_API_KEY = self.original_env.get("AZURE_OPENAI_API_KEY")
        utils.AZURE_OPENAI_ENDPOINT = self.original_env.get("AZURE_OPENAI_ENDPOINT")
        utils.AZURE_OPENAI_CHAT_DEPLOYMENT = self.original_env.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
        utils.AZURE_OPENAI_EMBEDDING_DEPLOYMENT = self.original_env.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        utils.openai.api_key = self.original_env.get("OPENAI_API_KEY")

        if utils.AZURE_OPENAI_API_KEY and utils.AZURE_OPENAI_ENDPOINT:
            try:
                utils.azure_openai_client = utils.openai.AzureOpenAI(
                    api_key=utils.AZURE_OPENAI_API_KEY,
                    azure_endpoint=utils.AZURE_OPENAI_ENDPOINT,
                    api_version="2023-07-01-preview"
                )
            except Exception:
                utils.azure_openai_client = None
        else:
            utils.azure_openai_client = None


    def _set_env_vars(self, use_azure=False, use_openai=False, valid_azure_creds=True):
        if use_azure:
            os.environ["AZURE_OPENAI_API_KEY"] = "fake_azure_key" if valid_azure_creds else "invalid_key"
            os.environ["AZURE_OPENAI_ENDPOINT"] = "fake_azure_endpoint" if valid_azure_creds else "invalid_endpoint"
            os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"] = "azure_chat_model"
            os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"] = "azure_embedding_model"
            # Re-initialize client in utils
            if valid_azure_creds:
                utils.azure_openai_client = MagicMock(spec=utils.openai.AzureOpenAI)
            else:
                # Simulate failed client initialization by setting it to None or making it raise error
                utils.azure_openai_client = None
        else:
            if "AZURE_OPENAI_API_KEY" in os.environ: del os.environ["AZURE_OPENAI_API_KEY"]
            if "AZURE_OPENAI_ENDPOINT" in os.environ: del os.environ["AZURE_OPENAI_ENDPOINT"]
            if "AZURE_OPENAI_CHAT_DEPLOYMENT" in os.environ: del os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
            if "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" in os.environ: del os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
            utils.azure_openai_client = None

        if use_openai:
            os.environ["OPENAI_API_KEY"] = "fake_openai_key"
            os.environ["MODEL_CHOICE"] = "openai_chat_model"
            utils.openai.api_key = "fake_openai_key"
        else:
            if "OPENAI_API_KEY" in os.environ: del os.environ["OPENAI_API_KEY"]
            if "MODEL_CHOICE" in os.environ: del os.environ["MODEL_CHOICE"]
            utils.openai.api_key = None

        # Update utils module constants directly for AZURE deployments for this test run
        utils.AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
        utils.AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")


    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_openai_success(self, mock_openai_create):
        self._set_env_vars(use_openai=True)
        texts = ["text1", "text2"]
        expected_embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_openai_create.return_value = MockOpenAIResponse([
            MockEmbeddingData(expected_embeddings[0]),
            MockEmbeddingData(expected_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_embeddings)
        mock_openai_create.assert_called_once_with(model="text-embedding-3-small", input=texts)

    @patch("utils.openai.AzureOpenAI") # To mock the client object itself if needed
    @patch("utils.openai.embeddings.create") # Standard OpenAI
    def test_create_embeddings_batch_azure_success(self, mock_openai_create, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, valid_azure_creds=True)

        # Ensure the client is mocked correctly
        mock_azure_client_instance = MagicMock()
        if utils.azure_openai_client: # if _set_env_vars successfully created a mock client
             utils.azure_openai_client.embeddings.create = mock_azure_client_instance
        else: # if client is None, this test path might be problematic, ensure client is set
            # This case implies _set_env_vars didn't set up azure_openai_client mock correctly
            # Forcing it here for the sake of the test structure
            utils.azure_openai_client = MagicMock()
            utils.azure_openai_client.embeddings.create = mock_azure_client_instance

        texts = ["text1", "text2"]
        expected_embeddings = [[0.5, 0.6], [0.7, 0.8]]

        mock_azure_client_instance.return_value = MockAzureOpenAIResponse([
            MockEmbeddingData(expected_embeddings[0]),
            MockEmbeddingData(expected_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_embeddings)
        mock_azure_client_instance.assert_called_once_with(model="azure_embedding_model", input=texts)
        mock_openai_create.assert_not_called()


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.embeddings.create") # Standard OpenAI
    def test_create_embeddings_batch_azure_fail_openai_success(self, mock_openai_create, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)

        mock_azure_client_instance = MagicMock()
        if utils.azure_openai_client:
             utils.azure_openai_client.embeddings.create = mock_azure_client_instance
        else:
            utils.azure_openai_client = MagicMock() # Ensure it's a mock
            utils.azure_openai_client.embeddings.create = mock_azure_client_instance

        mock_azure_client_instance.side_effect = Exception("Azure API Error")

        texts = ["text1", "text2"]
        expected_openai_embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_openai_create.return_value = MockOpenAIResponse([
            MockEmbeddingData(expected_openai_embeddings[0]),
            MockEmbeddingData(expected_openai_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_openai_embeddings)
        mock_azure_client_instance.assert_called_with(model="azure_embedding_model", input=texts) # Should be called (and fail)
        mock_openai_create.assert_called_once_with(model="text-embedding-3-small", input=texts)


    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_all_fail(self, mock_openai_create):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True) # Try Azure, then OpenAI

        mock_azure_client_instance = MagicMock()
        if utils.azure_openai_client:
             utils.azure_openai_client.embeddings.create = mock_azure_client_instance
        else:
            utils.azure_openai_client = MagicMock()
            utils.azure_openai_client.embeddings.create = mock_azure_client_instance

        mock_azure_client_instance.side_effect = Exception("Azure API Error")
        mock_openai_create.side_effect = Exception("OpenAI API Error") # Both direct and individual calls will fail

        texts = ["text1", "text2"]
        # Expect zero embeddings of dimension 1536 (hardcoded in utils.py)
        expected_embeddings = [[0.0] * 1536, [0.0] * 1536]

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_embeddings)


    # Tests for create_embedding (mostly relies on create_embeddings_batch mocks)
    @patch("utils.create_embeddings_batch")
    def test_create_embedding_calls_batch(self, mock_create_embeddings_batch):
        self._set_env_vars(use_openai=True) # Config doesn't matter as much as we mock the batch call
        text = "single text"
        expected_embedding = [0.1, 0.2, 0.3]
        mock_create_embeddings_batch.return_value = [expected_embedding]

        result = utils.create_embedding(text)
        self.assertEqual(result, expected_embedding)
        mock_create_embeddings_batch.assert_called_once_with([text])

    @patch("utils.create_embeddings_batch")
    def test_create_embedding_batch_fails(self, mock_create_embeddings_batch):
        self._set_env_vars(use_openai=True)
        text = "single text"
        mock_create_embeddings_batch.return_value = [] # Simulate failure or empty result

        result = utils.create_embedding(text)
        self.assertEqual(result, [0.0] * 1536) # Expect zero embedding

    # --- Tests for Chat Completion Functions ---

    # generate_contextual_embedding
    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_openai_success(self, mock_openai_chat):
        self._set_env_vars(use_openai=True)
        mock_openai_chat.return_value = MockChatCompletionResponse("OpenAI context")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"OpenAI context\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool)
        mock_openai_chat.assert_called_once()
        self.assertEqual(mock_openai_chat.call_args[1]['model'], "openai_chat_model")


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create") # Standard OpenAI chat
    def test_generate_contextual_embedding_azure_success(self, mock_openai_chat, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, valid_azure_creds=True)

        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client:
            utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: # Should be mocked by _set_env_vars
            utils.azure_openai_client = MagicMock()
            utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance

        mock_azure_chat_instance.return_value = MockChatCompletionResponse("Azure context")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"Azure context\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool)
        mock_azure_chat_instance.assert_called_once()
        self.assertEqual(mock_azure_chat_instance.call_args[1]['model'], "azure_chat_model")
        mock_openai_chat.assert_not_called()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create") # Standard OpenAI chat
    def test_generate_contextual_embedding_azure_fail_openai_success(self, mock_openai_chat, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)

        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client:
            utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else:
            utils.azure_openai_client = MagicMock()
            utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.side_effect = Exception("Azure API Error")

        mock_openai_chat.return_value = MockChatCompletionResponse("OpenAI context fallback")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"OpenAI context fallback\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool) # Still true as OpenAI succeeded
        mock_azure_chat_instance.assert_called_once()
        mock_openai_chat.assert_called_once()

    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_all_fail(self, mock_openai_chat):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)

        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client:
            utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else:
            utils.azure_openai_client = MagicMock()
            utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.side_effect = Exception("Azure API Error")
        mock_openai_chat.side_effect = Exception("OpenAI API Error")

        chunk = "test chunk"
        full_doc = "full document content"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, chunk) # Should return original chunk
        self.assertFalse(result_bool) # Should be false as it failed

    # generate_code_example_summary (similar structure to contextual_embedding)
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_openai_success(self, mock_openai_chat):
        self._set_env_vars(use_openai=True)
        mock_openai_chat.return_value = MockChatCompletionResponse("OpenAI summary")

        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "OpenAI summary")
        mock_openai_chat.assert_called_once()
        self.assertEqual(mock_openai_chat.call_args[1]['model'], "openai_chat_model")

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_azure_success(self, mock_openai_chat, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, valid_azure_creds=True)
        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client: utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: utils.azure_openai_client = MagicMock(); utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.return_value = MockChatCompletionResponse("Azure summary")

        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "Azure summary")
        mock_azure_chat_instance.assert_called_once()
        mock_openai_chat.assert_not_called()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_azure_fail_openai_success(self, mock_openai_chat, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)
        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client: utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: utils.azure_openai_client = MagicMock(); utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.side_effect = Exception("Azure Error")
        mock_openai_chat.return_value = MockChatCompletionResponse("OpenAI fallback summary")

        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "OpenAI fallback summary")
        mock_azure_chat_instance.assert_called_once()
        mock_openai_chat.assert_called_once()

    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_all_fail(self, mock_openai_chat):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)
        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client: utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: utils.azure_openai_client = MagicMock(); utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.side_effect = Exception("Azure Error")
        mock_openai_chat.side_effect = Exception("OpenAI Error")

        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "Code example for demonstration purposes.") # Default summary

    # extract_source_summary (similar structure)
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_openai_success(self, mock_openai_chat):
        self._set_env_vars(use_openai=True)
        mock_openai_chat.return_value = MockChatCompletionResponse("OpenAI source summary")

        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "OpenAI source summary")
        mock_openai_chat.assert_called_once()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_azure_success(self, mock_openai_chat, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, valid_azure_creds=True)
        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client: utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: utils.azure_openai_client = MagicMock(); utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.return_value = MockChatCompletionResponse("Azure source summary")

        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "Azure source summary")
        mock_azure_chat_instance.assert_called_once()
        mock_openai_chat.assert_not_called()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_azure_fail_openai_success(self, mock_openai_chat, MockAzureOpenAIClient):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)
        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client: utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: utils.azure_openai_client = MagicMock(); utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.side_effect = Exception("Azure Error")
        mock_openai_chat.return_value = MockChatCompletionResponse("OpenAI fallback source summary")

        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "OpenAI fallback source summary")
        mock_azure_chat_instance.assert_called_once()
        mock_openai_chat.assert_called_once()

    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_all_fail(self, mock_openai_chat):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True)
        mock_azure_chat_instance = MagicMock()
        if utils.azure_openai_client: utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        else: utils.azure_openai_client = MagicMock(); utils.azure_openai_client.chat.completions.create = mock_azure_chat_instance
        mock_azure_chat_instance.side_effect = Exception("Azure Error")
        mock_openai_chat.side_effect = Exception("OpenAI Error")

        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "Content from source_id") # Default summary

if __name__ == '__main__':
    unittest.main()
