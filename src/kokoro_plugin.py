import asyncio
import logging
from openai import OpenAI
from livekit.agents import APIConnectOptions, tts, utils

# Initialize OpenAI client for local Kokoro server
client = OpenAI(base_url="http://localhost:8880/v1", api_key="not-needed")

logger = logging.getLogger("kokoro_tts")


class KokoroTTS(tts.TTS):
    def __init__(self, voice="af_bella", sample_rate=22050):
        # Initialize without calling super().__init__ immediately
        # We'll call it in the first async method to ensure event loop is available
        self.voice = voice
        self.sample_rate = sample_rate
        self._initialized = False

    def synthesize(
        self, text: str, *, conn_options=APIConnectOptions(max_retry=3, timeout=5)
    ):
        return KokoroStream(tts=self, input_text=text)


class KokoroStream(tts.SynthesizeStream):
    def __init__(
        self,
        *,
        tts: KokoroTTS,
        input_text: str,
        conn_options=APIConnectOptions(max_retry=3, timeout=5),
    ):
        super().__init__(
            tts=tts, conn_options=APIConnectOptions(max_retry=3, timeout=5)
        )
        self._tts = tts
        self._input_text = input_text

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        """Stream Kokoro TTS output directly to LiveKit AudioEmitter"""
        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=self._tts.sample_rate,
            num_channels=1,
            stream=True,
            mime_type="audio/pcm",
        )

        try:
            with client.audio.speech.with_streaming_response.create(
                model="kokoro",
                voice=self._tts.voice,
                input=self._input_text,
                response_format="pcm",
            ) as response:
                for chunk in response.iter_bytes(chunk_size=1024):
                    output_emitter.push(chunk)

            output_emitter.flush()
            output_emitter.end_segment()

        except Exception as e:
            print(f"[KokoroTTS] Streaming failed: {e}")
            raise
