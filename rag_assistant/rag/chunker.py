import re
from typing import List, Dict

def split_text_into_chunks(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150
) -> List[str]:
    """
    Splits a single text block into overlapping chunks respecting natural boundaries:
    paragraphs (\\n\\n) -> sentences (. / ! / ?) -> lines (\\n) -> spaces -> hard slice.
    
    Parameters:
        text: Raw cleaned text to chunk.
        chunk_size: Maximum character length per chunk (e.g. 800 chars ~ 150-200 words).
        chunk_overlap: Character overlap between consecutive chunks (e.g. 150 chars).
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        if end >= text_length:
            # Reached end of text
            final_chunk = text[start:].strip()
            if final_chunk:
                chunks.append(final_chunk)
            break

        # Look for the best split point before `end`
        chunk_candidate = text[start:end]

        # 1. Try splitting at paragraph break (\n\n) within the latter half of the window
        split_pos = -1
        para_idx = chunk_candidate.rfind('\n\n')
        if para_idx > chunk_size // 3:
            split_pos = start + para_idx + 2
        else:
            # 2. Try sentence ending (.!?) followed by space or newline
            sentence_matches = list(re.finditer(r'([.!?])\s', chunk_candidate))
            if sentence_matches:
                last_match = sentence_matches[-1]
                if last_match.end() > chunk_size // 3:
                    split_pos = start + last_match.end()
            
            if split_pos == -1:
                # 3. Try splitting at line break (\n)
                line_idx = chunk_candidate.rfind('\n')
                if line_idx > chunk_size // 3:
                    split_pos = start + line_idx + 1
                else:
                    # 4. Try splitting at last whitespace
                    space_idx = chunk_candidate.rfind(' ')
                    if space_idx > chunk_size // 3:
                        split_pos = start + space_idx + 1
                    else:
                        # 5. Hard split fallback
                        split_pos = end

        chunk_text = text[start:split_pos].strip()
        if chunk_text:
            chunks.append(chunk_text)

        # Move forward, stepping back by overlap amount
        start = max(start + 1, split_pos - chunk_overlap)

    return chunks


def chunk_document_pages(
    pages_data: List[Dict[str, any]],
    chunk_size: int = 800,
    chunk_overlap: int = 150
) -> List[Dict[str, any]]:
    """
    Chunks extracted pages while preserving page numbers and sequence order.
    
    Returns:
        List of chunk dicts:
        [
            {
                'chunk_index': 0,
                'content': '...',
                'page_number': 1,
                'char_start': 0,
                'char_end': 795
            },
            ...
        ]
    """
    all_chunks = []
    chunk_counter = 0

    for page in pages_data:
        page_num = page.get('page_number', 1)
        page_text = page.get('text', '')

        page_chunks = split_text_into_chunks(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        for chunk_text in page_chunks:
            all_chunks.append({
                'chunk_index': chunk_counter,
                'content': chunk_text,
                'page_number': page_num,
                'char_start': None,
                'char_end': None,
            })
            chunk_counter += 1

    return all_chunks
