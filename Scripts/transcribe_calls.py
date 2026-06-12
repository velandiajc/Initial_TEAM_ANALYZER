from pathlib import Path

from app.services.pci_redaction_service import PCIRedactionService

AUDIO_FOLDER = Path("Data/CALLS/WEEK_18")
OUTPUT_FOLDER = Path("Data/CALLS/TRANSCRIPTS")


def write_redacted_transcript(output_file, transcript):
    output_file = Path(output_file)
    pci_service = PCIRedactionService()
    output_file = output_file.with_name(
        pci_service.redact_filename_component(output_file.stem)
        + output_file.suffix
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    safe_transcript = pci_service.redact(transcript)
    output_file.write_text(safe_transcript, encoding="utf-8")
    return output_file


def main():
    from faster_whisper import WhisperModel

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8"
    )

    for audio_file in AUDIO_FOLDER.glob("*.mp4"):
        print(f"Processing: {audio_file.name}")
        segments, _ = model.transcribe(
            str(audio_file),
            beam_size=5
        )
        transcript = "\n".join(segment.text for segment in segments)
        output_file = OUTPUT_FOLDER / f"{audio_file.stem}.md"
        write_redacted_transcript(output_file, transcript)
        print(f"Saved: {output_file}")


if __name__ == "__main__":
    main()
