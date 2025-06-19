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
            "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION",
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
        utils.AZURE_OPENAI_API_VERSION = self.original_env.get("AZURE_OPENAI_API_VERSION")
        utils.AZURE_OPENAI_CHAT_DEPLOYMENT = self.original_env.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
        utils.AZURE_OPENAI_EMBEDDING_DEPLOYMENT = self.original_env.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        utils.openai.api_key = self.original_env.get("OPENAI_API_KEY")

        # Reload the utils module to re-trigger client initialization with original env vars
        # This is a bit heavy-handed, but ensures the client reflects the tearDown state.
        # A more targeted approach would be to have a re-init function in utils.
        import importlib
        importlib.reload(utils)

        # The direct assignment of azure_openai_client in _set_env_vars and setUp/tearDown
        # means we don't strictly need to rely on the import-time initialization from utils
        # for the test's setup, but tearDown should restore it as best as possible.
        # The reload helps ensure that if utils were imported elsewhere, it also sees changes.

        # Fallback to manual re-initialization if reload is problematic or not desired:
        # if utils.AZURE_OPENAI_API_KEY and utils.AZURE_OPENAI_ENDPOINT and utils.AZURE_OPENAI_API_VERSION:
        #     try:
        #         utils.azure_openai_client = utils.openai.AzureOpenAI(
        #             api_key=utils.AZURE_OPENAI_API_KEY,
        #             azure_endpoint=utils.AZURE_OPENAI_ENDPOINT,
        #             api_version=utils.AZURE_OPENAI_API_VERSION
        #         )
        #     except Exception:
        #         utils.azure_openai_client = None
        # # else: # This was the line with the unexpected indent if not commented correctly
        # #     utils.azure_openai_client = None


    def _set_env_vars(self, use_azure=False, use_openai=False, valid_azure_creds=True, with_api_version=True):
        if use_azure:
            os.environ["AZURE_OPENAI_API_KEY"] = "fake_azure_key" if valid_azure_creds else "invalid_key"
            os.environ["AZURE_OPENAI_ENDPOINT"] = "fake_azure_endpoint" if valid_azure_creds else "invalid_endpoint"
            if with_api_version:
                os.environ["AZURE_OPENAI_API_VERSION"] = "fake_api_version" if valid_azure_creds else "invalid_version"
            elif "AZURE_OPENAI_API_VERSION" in os.environ: # ensure it's not there if with_api_version is false
                del os.environ["AZURE_OPENAI_API_VERSION"]

            os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"] = "azure_chat_model"
            os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"] = "azure_embedding_model"

            # Simulate re-initialization of the client as it happens in utils.py
            # The actual utils.azure_openai_client will be patched in tests that need to verify its calls.
            # This setup here is more about ensuring the *conditions* for its initialization are met.
            if valid_azure_creds and with_api_version and \
               os.environ.get("AZURE_OPENAI_API_KEY") == "fake_azure_key" and \
               os.environ.get("AZURE_OPENAI_ENDPOINT") == "fake_azure_endpoint" and \
               os.environ.get("AZURE_OPENAI_API_VERSION") == "fake_api_version":
                # This is where we'd expect utils.py to successfully create a client.
                # For testing method calls on the client, the client itself will be a MagicMock.
                # We don't assign to utils.azure_openai_client here directly anymore,
                # that will be handled by patching openai.AzureOpenAI in specific tests.
                pass
            else:
                # Conditions for client creation in utils.py are not met.
                # utils.azure_openai_client would be None.
                pass
        else:
            if "AZURE_OPENAI_API_KEY" in os.environ: del os.environ["AZURE_OPENAI_API_KEY"]
            if "AZURE_OPENAI_ENDPOINT" in os.environ: del os.environ["AZURE_OPENAI_ENDPOINT"]
            if "AZURE_OPENAI_API_VERSION" in os.environ: del os.environ["AZURE_OPENAI_API_VERSION"]
            if "AZURE_OPENAI_CHAT_DEPLOYMENT" in os.environ: del os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]
            if "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" in os.environ: del os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
            # utils.azure_openai_client would be None

        if use_openai:
            os.environ["OPENAI_API_KEY"] = "fake_openai_key"
            os.environ["MODEL_CHOICE"] = "openai_chat_model"
        else:
            if "OPENAI_API_KEY" in os.environ: del os.environ["OPENAI_API_KEY"]
            if "MODEL_CHOICE" in os.environ: del os.environ["MODEL_CHOICE"]

        # Crucially, reload utils so it picks up the new env vars for client init
        import importlib
        importlib.reload(utils)

        # Update utils module constants directly for AZURE deployments for this test run
        # This is needed because reload might not update these if they are top-level constants
        # and not re-evaluated based on os.getenv within a function.
        # However, in the actual utils.py, these are indeed top-level constants.
        # So, they need to be set here after reload if utils.py doesn't re-evaluate them.
        # Let's assume utils.py re-evaluates them or they are used directly from os.getenv in functions.
        # For safety, let's ensure the reloaded utils module's constants are what we expect for deployments.
        utils.AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
        utils.AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")


    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_openai_success(self, mock_openai_embeddings_create):
        self._set_env_vars(use_openai=True, use_azure=False) # Ensure Azure is off
        texts = ["text1", "text2"]
        expected_embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_openai_embeddings_create.return_value = MockOpenAIResponse([
            MockEmbeddingData(expected_embeddings[0]),
            MockEmbeddingData(expected_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_embeddings)
        mock_openai_embeddings_create.assert_called_once_with(model="text-embedding-3-small", input=texts)

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_azure_success(self, mock_openai_embeddings_create, mock_azure_openai_constructor):
        # Setup Azure env vars
        self._set_env_vars(use_azure=True, valid_azure_creds=True, with_api_version=True)

        # Mock the client instance that the constructor will return
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance

        # Reload utils for the mocked constructor to take effect if client is used from module level
        # However, the functions in utils.py check utils.azure_openai_client directly.
        # So, we need to ensure utils.azure_openai_client is this mocked instance.
        import importlib
        importlib.reload(utils) # This will re-initialize utils.azure_openai_client

        # Verify constructor call after reload
        mock_azure_openai_constructor.assert_called_with(
            api_key="fake_azure_key",
            azure_endpoint="fake_azure_endpoint",
            api_version="fake_api_version"
        )
        # Ensure the client used by the function is the one from the constructor
        self.assertIsNotNone(utils.azure_openai_client)
        self.assertEqual(utils.azure_openai_client, mock_azure_client_instance)

        texts = ["text1", "text2"]
        expected_embeddings = [[0.5, 0.6], [0.7, 0.8]]

        # Setup the mock call on the instance's method
        mock_azure_client_instance.embeddings.create.return_value = MockAzureOpenAIResponse([
            MockEmbeddingData(expected_embeddings[0]),
            MockEmbeddingData(expected_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_embeddings)
        mock_azure_client_instance.embeddings.create.assert_called_once_with(
            model=utils.AZURE_OPENAI_EMBEDDING_DEPLOYMENT, # Check it uses the deployment name
            input=texts
        )
        mock_openai_embeddings_create.assert_not_called()


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_azure_missing_api_version(self, mock_openai_embeddings_create, mock_azure_openai_constructor):
        # Set up Azure but without API version
        self._set_env_vars(use_azure=True, valid_azure_creds=True, with_api_version=False, use_openai=True)

        import importlib
        importlib.reload(utils) # Reload to attempt client init

        # Azure client constructor should NOT have been called because api_version is missing
        mock_azure_openai_constructor.assert_not_called()
        self.assertIsNone(utils.azure_openai_client) # Client should be None

        texts = ["text1", "text2"]
        expected_openai_embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_openai_embeddings_create.return_value = MockOpenAIResponse([
            MockEmbeddingData(expected_openai_embeddings[0]),
            MockEmbeddingData(expected_openai_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_openai_embeddings)
        mock_openai_embeddings_create.assert_called_once_with(model="text-embedding-3-small", input=texts)


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_azure_fail_openai_success(self, mock_openai_embeddings_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)

        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance

        import importlib
        importlib.reload(utils) # Re-initialize client

        mock_azure_openai_constructor.assert_called_with(
            api_key="fake_azure_key",
            azure_endpoint="fake_azure_endpoint",
            api_version="fake_api_version"
        )
        self.assertEqual(utils.azure_openai_client, mock_azure_client_instance)

        mock_azure_client_instance.embeddings.create.side_effect = Exception("Azure API Error")

        texts = ["text1", "text2"]
        expected_openai_embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_openai_embeddings_create.return_value = MockOpenAIResponse([
            MockEmbeddingData(expected_openai_embeddings[0]),
            MockEmbeddingData(expected_openai_embeddings[1])
        ])

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_openai_embeddings)
        mock_azure_client_instance.embeddings.create.assert_called_with(
            model=utils.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            input=texts
        )
        mock_openai_embeddings_create.assert_called_once_with(model="text-embedding-3-small", input=texts)


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.embeddings.create")
    def test_create_embeddings_batch_all_fail(self, mock_openai_embeddings_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)

        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib
        importlib.reload(utils)

        mock_azure_client_instance.embeddings.create.side_effect = Exception("Azure API Error")
        # Both direct and individual calls for OpenAI will fail
        mock_openai_embeddings_create.side_effect = Exception("OpenAI API Error")

        texts = ["text1", "text2"]
        expected_embeddings = [[0.0] * 1536, [0.0] * 1536]

        result = utils.create_embeddings_batch(texts)
        self.assertEqual(result, expected_embeddings)
        # Check that Azure was tried
        mock_azure_client_instance.embeddings.create.assert_called_once()
        # Check that OpenAI was tried (at least once for batch, then individually)
        # It will be called for the batch, then for each item individually.
        self.assertTrue(mock_openai_embeddings_create.call_count >= 1 + len(texts))


    # Tests for create_embedding (mostly relies on create_embeddings_batch mocks)
    # No changes needed here if create_embeddings_batch is correctly mocked/tested

    # --- Tests for Chat Completion Functions ---
    # generate_contextual_embedding
    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_openai_success(self, mock_openai_chat_create):
        self._set_env_vars(use_openai=True, use_azure=False)
        import importlib
        importlib.reload(utils)

        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI context")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"OpenAI context\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool)
        mock_openai_chat_create.assert_called_once()
        self.assertEqual(mock_openai_chat_create.call_args[1]['model'], "openai_chat_model")


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_azure_success(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, valid_azure_creds=True, with_api_version=True)

        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib
        importlib.reload(utils)

        mock_azure_openai_constructor.assert_called_with(api_key='fake_azure_key', azure_endpoint='fake_azure_endpoint', api_version='fake_api_version')
        self.assertEqual(utils.azure_openai_client, mock_azure_client_instance)

        mock_azure_client_instance.chat.completions.create.return_value = MockChatCompletionResponse("Azure context")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"Azure context\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool)
        mock_azure_client_instance.chat.completions.create.assert_called_once()
        self.assertEqual(mock_azure_client_instance.chat.completions.create.call_args[1]['model'], utils.AZURE_OPENAI_CHAT_DEPLOYMENT)
        mock_openai_chat_create.assert_not_called()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_azure_missing_api_version(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=False)
        import importlib
        importlib.reload(utils)

        mock_azure_openai_constructor.assert_not_called()
        self.assertIsNone(utils.azure_openai_client)

        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI context fallback")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"OpenAI context fallback\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool)
        mock_openai_chat_create.assert_called_once()


    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_azure_fail_openai_success(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)

        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib
        importlib.reload(utils)

        mock_azure_client_instance.chat.completions.create.side_effect = Exception("Azure API Error")
        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI context fallback")

        chunk = "test chunk"
        full_doc = "full document content"
        expected_text = f"OpenAI context fallback\n---\n{chunk}"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, expected_text)
        self.assertTrue(result_bool)
        mock_azure_client_instance.chat.completions.create.assert_called_once()
        mock_openai_chat_create.assert_called_once()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_contextual_embedding_all_fail(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)

        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib
        importlib.reload(utils)

        mock_azure_client_instance.chat.completions.create.side_effect = Exception("Azure API Error")
        mock_openai_chat_create.side_effect = Exception("OpenAI API Error")

        chunk = "test chunk"
        full_doc = "full document content"

        result_text, result_bool = utils.generate_contextual_embedding(full_doc, chunk)
        self.assertEqual(result_text, chunk)
        self.assertFalse(result_bool)

    # generate_code_example_summary (similar structure)
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_openai_success(self, mock_openai_chat_create):
        self._set_env_vars(use_openai=True, use_azure=False)
        import importlib; importlib.reload(utils)
        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI summary")

        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "OpenAI summary")
        mock_openai_chat_create.assert_called_once()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_azure_success(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, valid_azure_creds=True, with_api_version=True)
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib; importlib.reload(utils)
        self.assertEqual(utils.azure_openai_client, mock_azure_client_instance)

        mock_azure_client_instance.chat.completions.create.return_value = MockChatCompletionResponse("Azure summary")
        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "Azure summary")
        mock_azure_client_instance.chat.completions.create.assert_called_once()
        mock_openai_chat_create.assert_not_called()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_azure_fail_openai_success(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib; importlib.reload(utils)

        mock_azure_client_instance.chat.completions.create.side_effect = Exception("Azure Error")
        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI fallback summary")
        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "OpenAI fallback summary")
        mock_azure_client_instance.chat.completions.create.assert_called_once()
        mock_openai_chat_create.assert_called_once()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_generate_code_example_summary_all_fail(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib; importlib.reload(utils)

        mock_azure_client_instance.chat.completions.create.side_effect = Exception("Azure Error")
        mock_openai_chat_create.side_effect = Exception("OpenAI Error")
        result = utils.generate_code_example_summary("code", "before", "after")
        self.assertEqual(result, "Code example for demonstration purposes.")

    # extract_source_summary (similar structure)
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_openai_success(self, mock_openai_chat_create):
        self._set_env_vars(use_openai=True, use_azure=False)
        import importlib; importlib.reload(utils)
        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI source summary")

        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "OpenAI source summary")
        mock_openai_chat_create.assert_called_once()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_azure_success(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, valid_azure_creds=True, with_api_version=True)
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib; importlib.reload(utils)
        self.assertEqual(utils.azure_openai_client, mock_azure_client_instance)

        mock_azure_client_instance.chat.completions.create.return_value = MockChatCompletionResponse("Azure source summary")
        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "Azure source summary")
        mock_azure_client_instance.chat.completions.create.assert_called_once()
        mock_openai_chat_create.assert_not_called()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_azure_fail_openai_success(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib; importlib.reload(utils)

        mock_azure_client_instance.chat.completions.create.side_effect = Exception("Azure Error")
        mock_openai_chat_create.return_value = MockChatCompletionResponse("OpenAI fallback source summary")
        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "OpenAI fallback source summary")
        mock_azure_client_instance.chat.completions.create.assert_called_once()
        mock_openai_chat_create.assert_called_once()

    @patch("utils.openai.AzureOpenAI")
    @patch("utils.openai.chat.completions.create")
    def test_extract_source_summary_all_fail(self, mock_openai_chat_create, mock_azure_openai_constructor):
        self._set_env_vars(use_azure=True, use_openai=True, valid_azure_creds=True, with_api_version=True)
        mock_azure_client_instance = MagicMock()
        mock_azure_openai_constructor.return_value = mock_azure_client_instance
        import importlib; importlib.reload(utils)

        mock_azure_client_instance.chat.completions.create.side_effect = Exception("Azure Error")
        mock_openai_chat_create.side_effect = Exception("OpenAI Error")
        result = utils.extract_source_summary("source_id", "content")
        self.assertEqual(result, "Content from source_id") # Default summary

if __name__ == '__main__':
    unittest.main()
