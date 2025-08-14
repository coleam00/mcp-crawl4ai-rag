"""
LLM client for the Crawl4AI MCP server.

This module provides a unified interface for interacting with different LLM providers,
including OpenAI, Google Gemini, and Open Router. It uses a factory pattern to
create a client for the specified provider, which can then be used to create
chat completions and embeddings.
"""

import os
from typing import List, Dict, Any, Optional
import openai
import google.generativeai as genai
import requests
import time

class LLMClient:
    """Base class for LLM clients."""
    def __init__(self, api_key: str, model: str, embedding_model: str):
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Create a chat completion.

        Args:
            messages: A list of messages in the chat history.
            **kwargs: Additional arguments for the API call.

        Returns:
            The response from the LLM.
        """
        raise NotImplementedError

    def create_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        Create embeddings for a list of texts.

        Args:
            texts: A list of texts to create embeddings for.
            **kwargs: Additional arguments for the API call.

        Returns:
            A list of embeddings.
        """
        raise NotImplementedError

class OpenAIClient(LLMClient):
    """LLM client for OpenAI."""
    def __init__(self, api_key: str, model: str, embedding_model: str):
        super().__init__(api_key, model, embedding_model)
        self.client = openai.OpenAI(api_key=api_key)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content.strip()

    def create_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
            **kwargs
        )
        return [item.embedding for item in response.data]

class GeminiClient(LLMClient):
    """LLM client for Google Gemini."""
    def __init__(self, api_key: str, model: str, embedding_model: str):
        super().__init__(api_key, model, embedding_model)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Gemini API has a different format for chat history.
        # It expects a list of alternating user and model messages.
        # We need to convert the OpenAI format to the Gemini format.
        gemini_messages = []
        for message in messages:
            role = "user" if message["role"] == "user" else "model"
            gemini_messages.append({"role": role, "parts": [message["content"]]})

        # The Gemini API doesn't like it when the same role appears twice in a row.
        # We need to filter out consecutive messages from the same role.
        filtered_messages = []
        if gemini_messages:
            filtered_messages.append(gemini_messages[0])
            for i in range(1, len(gemini_messages)):
                if gemini_messages[i]['role'] != gemini_messages[i-1]['role']:
                    filtered_messages.append(gemini_messages[i])

        chat = self.client.start_chat(history=filtered_messages[:-1])
        response = chat.send_message(filtered_messages[-1]["parts"])

        return response.text.strip()

    def create_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        response = genai.embed_content(
            model=self.embedding_model,
            content=texts,
            task_type="retrieval_document"
        )
        return response['embedding']


class OpenRouterClient(LLMClient):
    """LLM client for Open Router."""
    def __init__(self, api_key: str, model: str, embedding_model: str):
        super().__init__(api_key, model, embedding_model)
        self.api_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "http://localhost:8051"),
            "X-Title": os.getenv("OPENROUTER_TITLE", "Crawl4AI MCP"),
        }

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = requests.post(
            f"{self.api_url}/chat/completions",
            headers=self.headers,
            json={
                "model": self.model,
                "messages": messages,
                **kwargs
            }
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()

    def create_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        response = requests.post(
            f"{self.api_url}/embeddings",
            headers=self.headers,
            json={
                "model": self.embedding_model,
                "input": texts,
                **kwargs
            }
        )
        response.raise_for_status()
        data = response.json()['data']
        return [item['embedding'] for item in data]


def get_llm_client() -> Optional[LLMClient]:
    """
    Factory function to get the appropriate LLM client based on environment variables.

    Returns:
        An instance of the appropriate LLM client, or None if no provider is configured.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("MODEL_CHOICE")
    embedding_model = os.getenv("EMBEDDING_MODEL")

    print(f"Initializing LLM client for provider: {provider}")

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set for the OpenAI provider.")
        if not model:
            model = "gpt-3.5-turbo"
        if not embedding_model:
            embedding_model = "text-embedding-3-small"
        return OpenAIClient(api_key=api_key, model=model, embedding_model=embedding_model)

    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set for the Gemini provider.")
        if not model:
            model = "gemini-pro"
        if not embedding_model:
            embedding_model = "models/embedding-001"
        return GeminiClient(api_key=api_key, model=model, embedding_model=embedding_model)

    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY must be set for the OpenRouter provider.")
        if not model:
            raise ValueError("MODEL_CHOICE must be set for the OpenRouter provider (e.g., 'google/gemini-pro').")
        if not embedding_model:
            # Default to a common OpenAI embedding model available on OpenRouter
            embedding_model = "text-embedding-ada-002"
        return OpenRouterClient(api_key=api_key, model=model, embedding_model=embedding_model)

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    return None
