"""
Merge transcript chunks into a single text.
Handles overlap deduplication at chunk boundaries.
"""

import logging
from pathlib import Path
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def dedupe_overlap(text_a: str, text_b: str, overlap_words: int = 30) -> str:
    """
    Simple overlap deduplication between the end of text_a and start of text_b.
    Looks for repeated words at the boundary and removes them.
    """
    if not text_a or not text_b:
        return (text_a or '') + '\n\n' + (text_b or '')

    words_a = text_a.split()
    words_b = text_b.split()

    if not words_a or not words_b:
        return text_a + '\n\n' + text_b

    # Check last N words of A against first N words of B
    check_len = min(overlap_words, len(words_a), len(words_b))

    best_overlap = 0
    tail_a = words_a[-check_len:]

    for i in range(check_len, 0, -1):
        head_b = words_b[:i]
        # Compare tail of A with head of B
        if tail_a[-i:] == head_b:
            best_overlap = i
            break

    if best_overlap > 3:  # Only dedupe if meaningful overlap found
        # Remove overlapping words from B
        merged = ' '.join(words_a) + ' ' + ' '.join(words_b[best_overlap:])
        logger.debug("Deduped %d overlapping words at boundary", best_overlap)
    else:
        merged = text_a.rstrip() + '\n\n' + text_b.lstrip()

    return merged


def merge_transcripts(texts: list[str]) -> str:
    """
    Merge multiple transcript texts in order.
    Applies overlap deduplication at boundaries.
    """
    if not texts:
        return ""
    if len(texts) == 1:
        return texts[0]

    result = texts[0]
    for i in range(1, len(texts)):
        result = dedupe_overlap(result, texts[i])

    return result.strip()


def merge_transcript_files(transcript_dir: Path, chunk_count: int) -> str:
    """
    Read chunk transcript files and merge them.
    Expects files named chunk_000.json, chunk_001.json, etc.
    """
    import json
    from app.core.transcribe_deepgram import extract_transcript_text

    texts = []
    for idx in range(chunk_count):
        json_path = transcript_dir / f"chunk_{idx:03d}.json"
        if json_path.exists():
            with open(json_path, 'r') as f:
                data = json.load(f)
            text = extract_transcript_text(data)
            texts.append(text)
        else:
            logger.warning("Missing transcript file: %s", json_path)

    return merge_transcripts(texts)
