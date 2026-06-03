from pathlib import Path
from faster_whisper import WhisperModel

AUDIO_FOLDER = Path("Data/CALLS/WEEK_18")
OUTPUT_FOLDER = Path("Data/CALLS/TRANSCRIPTS")

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

for audio_file in AUDIO_FOLDER.glob("*.mp4"):

    print(f"Processing: {audio_file.name}")

    segments, info = model.transcribe(
        str(audio_file),
        beam_size=5
    )

    transcript = []

    for segment in segments:
        transcript.append(segment.text)

    output_file = (
        OUTPUT_FOLDER /
        f"{audio_file.stem}.md"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:
        f.write("\n".join(transcript))

    print(f"Saved: {output_file}")