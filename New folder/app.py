import os
import tempfile
from io import BytesIO
from typing import Dict

import streamlit as st
from googletrans import LANGUAGES, Translator
from gtts import gTTS
import speech_recognition as sr

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
except ImportError:
    webrtc_streamer = None

###############################################################################
# Utility helpers
###############################################################################

def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio (WAV) to text using Google Web Speech API."""
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        tmp_wav.write(audio_bytes)
        tmp_wav.flush()
        with sr.AudioFile(tmp_wav.name) as source:
            audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        text = "[Could not understand audio]"
    except sr.RequestError as e:
        text = f"[Speech recognition failed: {e}]"
    finally:
        os.unlink(tmp_wav.name)
    return text

def translate_text(text: str) -> Dict[str, str]:
    """Translate text into multiple languages using Google Translate."""
    translator = Translator()
    translations = {}
    for code in LANGUAGES.keys():
        try:
            translations[code] = translator.translate(text, dest=code).text
        except Exception:
            translations[code] = "[Translation failed]"
    return translations

def tts_audio_bytes(text: str, lang_code: str) -> bytes | None:
    """Generate MP3 audio bytes for text in the given language."""
    try:
        tts = gTTS(text=text, lang=lang_code)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception:
        return None

###############################################################################
# Streamlit UI
###############################################################################

st.set_page_config(page_title="Universal Voice Translator", page_icon="🌐")
st.title("🌐 Universal Voice Translator")
st.markdown(
    "Speak or upload an audio clip, and the app will translate it to every language it knows — **and** read the translations back to you!"
)

# 1️⃣ Audio input
st.header("1. Provide your voice input")

input_method = st.radio(
    "Choose input method:",
    ("🎤 Record with microphone", "📁 Upload audio file"),
    horizontal=True,
)

audio_bytes: bytes | None = None

if input_method == "🎤 Record with microphone":
    if webrtc_streamer is None:
        st.warning("`streamlit-webrtc` is not installed. Please install it or switch to file upload.")
    else:
        class AudioRecorder(AudioProcessorBase):
            def __init__(self):
                self.recorded_frames = []

            def recv_audio(self, frame):
                self.recorded_frames.append(frame)
                return frame

        recorder_ctx = webrtc_streamer(
            key="recorder",
            mode=WebRtcMode.SENDRECV,
            audio_receiver_size=256,
            video_processor_factory=None,
            audio_processor_factory=AudioRecorder,
            media_stream_constraints={"video": False, "audio": True},
        )
        if recorder_ctx.audio_processor:
            if st.button("Stop & Use Recording"):
                audio_frames = recorder_ctx.audio_processor.recorded_frames
                if audio_frames:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        for frame in audio_frames:
                            tmp.write(frame.to_ndarray().tobytes())
                        tmp.flush()
                        audio_bytes = tmp.read()
                        st.success("Audio captured!")
                else:
                    st.error("No audio frames captured yet. Try speaking.")

else:  # File upload
    uploaded_file = st.file_uploader("Upload an audio file (WAV only)", type=["wav"])
    if uploaded_file is not None:
        audio_bytes = uploaded_file.read()
        st.audio(audio_bytes)

# Proceed if we have audio
if audio_bytes:
    st.header("2. Transcript")
    transcript = transcribe_audio(audio_bytes)
    st.write(transcript)

    if not transcript.startswith("["):
        st.header("3. Translations & Speech")
        translations = translate_text(transcript)

        for code, translated in translations.items():
            lang_name = LANGUAGES[code].title()
            with st.expander(f"{lang_name} ({code})"):
                st.write(translated)
                speech_bytes = tts_audio_bytes(translated, code)
                if speech_bytes:
                    st.audio(speech_bytes, format="audio/mp3")
                else:
                    st.info("gTTS does not support speech synthesis for this language code.")

else:
    st.info("Please provide an audio input to begin.")
