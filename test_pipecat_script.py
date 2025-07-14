#!/usr/bin/env python3
"""
Test script for Pipecat AI hallucination detection
"""
import os
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.vad.silero import SileroVADAnalyzer

async def main():
    # Initialize LLM service
    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o"
    )
    
    # Initialize TTS service
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22"
    )
    
    # Create transport
    transport = DailyTransport(
        room_url=os.getenv("DAILY_ROOM_URL"),
        token=os.getenv("DAILY_TOKEN"),
        bot_name="AI Assistant",
        params=DailyParams(
            audio_out_enabled=True,
            transcription_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer()
        )
    )
    
    # Create pipeline
    pipeline = Pipeline([
        transport.input(),
        llm,
        tts,
        transport.output()
    ])
    
    # Create and run task
    task = PipelineTask(pipeline)
    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 