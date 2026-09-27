"""Reusable FSR v2 chunker with multiple strategies and offset tracking."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

ChunkResult = tuple[str, int, int]


class SmartChunker:
    """Multi-strategy document chunker returning text with start/end offsets."""

    STRATEGIES = ["character", "recursive", "markdown", "section", "v1_hierarchical"]

    _RECURSIVE_SEPARATORS = [
        r"\n#{1,6}\s",
        r"\n\n",
        r"\n",
        r"(?<=[.!?])\s+",
        r"\s+",
    ]

    _MD_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    _MD_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    _MD_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
    _MD_HR = re.compile(r"^(-{3,}|_{3,}|\*{3,})$", re.MULTILINE)
    _SECTION_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    _NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\s+(.+)$")
    _SENTENCE_END_RE = re.compile(r"[.!?][\"'\)\]]?\s*$")
    _TOC_LIKE_RE = re.compile(r"table\s+of\s+contents|_{3,}|\.{3,}", re.IGNORECASE)
    _LEGAL_LIKE_RE = re.compile(
        r"confidential and proprietary|not to be copied, reproduced"
        r"|unauthorized export or re-export|general electric company",
        re.IGNORECASE,
    )
    _TOC_START_RE = re.compile(r"^\s*table\s+of\s+contents\b", re.IGNORECASE)
    _TOC_ENTRY_RE = re.compile(
        r"(_{3,}|\.{3,}|\b\d{1,4}\s*$|^\d{1,2}(?:\.\d{1,2}){0,3}\s+.+\d{1,4}\s*$)",
        re.IGNORECASE,
    )
    _NOISY_CHUNK_START_RE = re.compile(
        r"^(table\s+of\s+contents|\d+(?:\.\d+){0,3}\s*$|[A-Z0-9\-\|\s]{1,28}$)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        strategy: str = "recursive",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy if strategy in self.STRATEGIES else "recursive"
        # Track actual strategy used if fallback occurs (for data lineage)
        self._actual_strategy = self.strategy

    def chunk_text(self, text: str, pdf_path: str | None = None) -> list[ChunkResult]:
        # Reset per-call diagnostics so callers do not read stale values.
        self._last_mapping_miss_chunk_indices: list[int] = []
        # Track actual strategy used (may differ from self.strategy if fallback occurs)
        self._actual_strategy = self.strategy
        if not text or not text.strip():
            return []

        if self.strategy == "character":
            return self._chunk_character(text)
        if self.strategy == "markdown":
            return self._chunk_markdown(text)
        if self.strategy == "section":
            return self._chunk_by_sections(text)
        return self._chunk_recursive(text)

    # ------------------------------------------------------------------
    # Strategy block START: character
    # ------------------------------------------------------------------

    def _chunk_character(self, text: str) -> list[ChunkResult]:
        cleaned = self._collapse_whitespace(text)
        if len(cleaned) <= self.chunk_size:
            return [(cleaned, 0, len(text))]

        chunks: list[ChunkResult] = []
        start = 0
        text_len = len(cleaned)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            if end < text_len:
                boundary = self._find_sentence_boundary(cleaned, start, end)
                if boundary > start:
                    end = boundary

            chunk = cleaned[start:end].strip()
            if chunk:
                chunks.append((chunk, start, end))

            if end >= text_len:
                break

            start = end - self.chunk_overlap

        return chunks

    # ------------------------------------------------------------------
    # Strategy block END: character
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Strategy block START: recursive
    # ------------------------------------------------------------------

    def _chunk_recursive(self, text: str) -> list[ChunkResult]:
        segments = self._recursive_split(text, sep_index=0)
        return self._merge_segments(segments)

    def _recursive_split(
        self, text: str, sep_index: int, depth: int = 0
    ) -> list[tuple[str, int]]:
        if not text.strip():
            return []

        if len(text) <= self.chunk_size:
            return [(text, 0)]

        if sep_index >= len(self._RECURSIVE_SEPARATORS) or depth > 20:
            return self._hard_split(text)

        parts = self._split_keeping_offsets(text, self._RECURSIVE_SEPARATORS[sep_index])
        if len(parts) <= 1:
            return self._recursive_split(text, sep_index + 1, depth + 1)

        if any(len(part[0]) >= len(text) for part in parts):
            return self._recursive_split(text, sep_index + 1, depth + 1)

        result: list[tuple[str, int]] = []
        for part_text, part_offset in parts:
            if not part_text.strip():
                continue
            if len(part_text) <= self.chunk_size:
                result.append((part_text, part_offset))
            else:
                sub_parts = self._recursive_split(part_text, sep_index + 1, depth + 1)
                for sub_text, sub_offset in sub_parts:
                    result.append((sub_text, part_offset + sub_offset))

        return result

    def _split_keeping_offsets(
        self, text: str, pattern: str
    ) -> list[tuple[str, int]]:
        parts: list[tuple[str, int]] = []
        last_end = 0

        for match in re.finditer(pattern, text):
            if match.start() == 0 and not parts:
                continue

            segment = text[last_end:match.start()]
            if segment:
                parts.append((segment, last_end))

            separator = match.group()
            if separator.strip():
                last_end = match.start()
            else:
                last_end = match.end()

        if last_end < len(text):
            parts.append((text[last_end:], last_end))

        return parts

    def _hard_split(self, text: str) -> list[tuple[str, int]]:
        result: list[tuple[str, int]] = []
        pos = 0
        while pos < len(text):
            end = min(pos + self.chunk_size, len(text))
            result.append((text[pos:end], pos))
            pos = end
        return result

    def _merge_segments(self, segments: list[tuple[str, int]]) -> list[ChunkResult]:
        if not segments:
            return []

        chunks: list[ChunkResult] = []
        current_text = ""
        current_start = 0
        current_end = 0

        for seg_text, seg_offset in segments:
            seg_stripped = seg_text.strip()
            if not seg_stripped:
                continue

            candidate = (current_text + "\n\n" + seg_stripped).strip() if current_text else seg_stripped
            seg_end = seg_offset + len(seg_text)

            if len(candidate) <= self.chunk_size:
                current_text = candidate
                if not current_text or current_text == seg_stripped:
                    current_start = seg_offset
                current_end = seg_end
            else:
                if current_text:
                    chunks.append((current_text, current_start, current_end))

                if self.chunk_overlap > 0 and current_text:
                    overlap_text = current_text[-self.chunk_overlap:]
                    current_text = (overlap_text + "\n\n" + seg_stripped).strip()
                    current_start = current_end - self.chunk_overlap
                else:
                    current_text = seg_stripped
                    current_start = seg_offset
                current_end = seg_end

                if len(current_text) > self.chunk_size:
                    sub_chunks = self._chunk_character(current_text)
                    for chunk_text, rel_start, rel_end in sub_chunks:
                        chunks.append((chunk_text, current_start + rel_start, current_start + rel_end))
                    current_text = ""
                    current_start = seg_end
                    current_end = seg_end

        if current_text.strip():
            chunks.append((current_text, current_start, current_end))

        return chunks

    # ------------------------------------------------------------------
    # Strategy block END: recursive
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Strategy block START: markdown
    # ------------------------------------------------------------------

    def _chunk_markdown(self, text: str) -> list[ChunkResult]:
        sections = self._split_markdown_sections(text)
        return self._merge_segments(sections)

    def _split_markdown_sections(self, text: str) -> list[tuple[str, int]]:
        protected: list[tuple[int, int]] = []
        for match in self._MD_CODE_BLOCK.finditer(text):
            protected.append((match.start(), match.end()))

        protected.extend(self._find_table_regions(text))
        protected.sort()

        merged_protected: list[tuple[int, int]] = []
        for start, end in protected:
            if merged_protected and start <= merged_protected[-1][1]:
                merged_protected[-1] = (merged_protected[-1][0], max(end, merged_protected[-1][1]))
            else:
                merged_protected.append((start, end))

        split_points = []
        for match in self._MD_HEADING.finditer(text):
            if not self._in_protected(match.start(), merged_protected):
                split_points.append(match.start())
        for match in self._MD_HR.finditer(text):
            if not self._in_protected(match.start(), merged_protected):
                split_points.append(match.end())

        split_points = sorted(set(split_points))
        if not split_points:
            return self._recursive_split(text, sep_index=1)

        sections: list[tuple[str, int]] = []
        prev = 0
        for split_point in split_points:
            if split_point > prev:
                segment = text[prev:split_point]
                if segment.strip():
                    sections.append((segment, prev))
            prev = split_point

        if prev < len(text):
            segment = text[prev:]
            if segment.strip():
                sections.append((segment, prev))

        result: list[tuple[str, int]] = []
        for section_text, section_offset in sections:
            if len(section_text) <= self.chunk_size:
                result.append((section_text, section_offset))
            else:
                sub_sections = self._recursive_split(section_text, sep_index=1)
                for sub_text, sub_offset in sub_sections:
                    result.append((sub_text, section_offset + sub_offset))

        return result

    def _find_table_regions(self, text: str) -> list[tuple[int, int]]:
        regions: list[tuple[int, int]] = []
        current_start = None
        current_end = None

        for match in self._MD_TABLE_ROW.finditer(text):
            if current_start is None:
                current_start = match.start()
                current_end = match.end()
            elif match.start() - current_end <= 1:
                current_end = match.end()
            else:
                if current_end - current_start > 0:
                    regions.append((current_start, current_end))
                current_start = match.start()
                current_end = match.end()

        if current_start is not None:
            regions.append((current_start, current_end))

        return regions

    @staticmethod
    def _in_protected(pos: int, protected: list[tuple[int, int]]) -> bool:
        for start, end in protected:
            if start <= pos < end:
                return True
        return False

    # ------------------------------------------------------------------
    # Strategy block END: markdown
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Strategy block START: section
    # ------------------------------------------------------------------

    def _chunk_by_sections(self, text: str) -> list[ChunkResult]:
        sections = self._extract_sections(text)
        if not sections:
            return self._chunk_recursive(text)

        all_chunks: list[ChunkResult] = []
        prev_section: dict | None = None
        for section in sections:
            section_text_raw = section["text"]
            section_text, trim_delta = self._strip_leading_synthetic_heading(section_text_raw)
            section_offset = section["offset"] + trim_delta
            if not section_text.strip():
                continue

            section_chunks: list[ChunkResult] = []
            if len(section_text) <= self.chunk_size:
                section_chunks.append((section_text, section_offset, section_offset + len(section_text)))
            else:
                sub_segments = self._recursive_split(section_text, sep_index=1)
                sub_chunks = self._merge_segments(sub_segments)
                for chunk_text, rel_start, rel_end in sub_chunks:
                    section_chunks.append((chunk_text, section_offset + rel_start, section_offset + rel_end))

            if section_chunks and all_chunks and self.chunk_overlap > 0:
                prev_text, _, _ = all_chunks[-1]
                first_text, first_start, first_end = section_chunks[0]
                if self._should_overlap_sections(prev_text, first_text, prev_section, section):
                    overlap = prev_text[-min(self.chunk_overlap, len(prev_text)):].strip()
                    if overlap and not first_text.startswith(overlap):
                        boundary_join = (overlap + "\n\n" + first_text).strip()
                        # Keep start anchored to this section so metadata lookup
                        # stays in the correct section path.
                        section_chunks[0] = (boundary_join, first_start, first_end)

            all_chunks.extend(section_chunks)
            prev_section = section

        return all_chunks

    def _strip_leading_synthetic_heading(self, section_text: str) -> tuple[str, int]:
        """Remove injected markdown heading from the start of a section chunk.

        Keep section metadata anchored to heading lines while storing cleaner
        chunk text for embedding/retrieval.
        """
        first_line, sep, rest = section_text.partition("\n")
        if self._SECTION_HEADING.match(first_line.strip()) and rest.strip():
            removed = len(first_line) + len(sep)
            return rest, removed
        return section_text, 0

    def _should_overlap_sections(
        self,
        prev_text: str,
        next_text: str,
        prev_section: dict | None,
        next_section: dict | None,
    ) -> bool:
        prev = prev_text.rstrip()
        nxt = next_text.lstrip()
        if not prev or not nxt:
            return False
        if self._is_top_level_transition(prev_section, next_section):
            return False
        if self._is_noisy_section_start(nxt):
            return False
        if self._is_non_prose_boundary(prev, nxt):
            return False
        if self._SENTENCE_END_RE.search(prev):
            return False
        return bool(re.match(r"^[a-z0-9\(\[\"']", nxt))

    def _is_top_level_transition(self, prev_section: dict | None, next_section: dict | None) -> bool:
        if not prev_section or not next_section:
            return False
        prev_path = prev_section.get("path") or []
        next_path = next_section.get("path") or []
        if not prev_path or not next_path:
            return False
        prev_top = str(prev_path[0]).strip().lower()
        next_top = str(next_path[0]).strip().lower()
        return bool(prev_top and next_top and prev_top != next_top)

    def _is_noisy_section_start(self, next_head: str) -> bool:
        head = (next_head or "")[:220]
        if self._TOC_ENTRY_RE.search(head) or self._TOC_LIKE_RE.search(head):
            return True
        if self._LEGAL_LIKE_RE.search(head):
            return True
        return bool(self._NOISY_CHUNK_START_RE.search(head))

    def _is_non_prose_boundary(self, prev: str, nxt: str) -> bool:
        """Skip overlap when adjacent chunks are likely TOC/boilerplate blocks."""
        prev_tail = prev[-250:]
        next_head = nxt[:250]

        if self._TOC_LIKE_RE.search(prev_tail) or self._TOC_LIKE_RE.search(next_head):
            return True
        if self._LEGAL_LIKE_RE.search(prev_tail) or self._LEGAL_LIKE_RE.search(next_head):
            return True

        # Dense numeric tails/heads are typically index/table noise, not prose.
        prev_num = len(re.findall(r"\b\d+\b", prev_tail))
        next_num = len(re.findall(r"\b\d+\b", next_head))
        prev_words = len(re.findall(r"\b[a-zA-Z]{3,}\b", prev_tail))
        next_words = len(re.findall(r"\b[a-zA-Z]{3,}\b", next_head))
        if (prev_num >= 8 and prev_words <= 6) or (next_num >= 8 and next_words <= 6):
            return True
        return False

    def _extract_sections(self, text: str) -> list[dict]:
        sections = self._extract_sections_structural(text)
        if sections:
            self._last_section_map = sections
            return sections

        sections = self._extract_sections_markdown(text)
        self._last_section_map = sections
        return sections

    def _extract_sections_structural(self, text: str) -> list[dict]:
        """TOC-aware structural extraction before regex-heading fallback.

        This mirrors Alex/DS-style intent: use document structure first, then
        rely on heading-marker regex only when structure cannot be inferred.
        """
        lines = text.splitlines(keepends=True)
        if not lines:
            return []

        headings: list[tuple[int, int, str]] = []
        offset = 0
        in_toc = False
        non_toc_streak = 0

        for raw in lines:
            line = raw.strip()
            line_start = offset
            offset += len(raw)

            if not line:
                continue

            if self._TOC_START_RE.search(line):
                in_toc = True
                non_toc_streak = 0
                continue

            if in_toc:
                if self._TOC_ENTRY_RE.search(line) or self._TOC_LIKE_RE.search(line):
                    non_toc_streak = 0
                    continue
                non_toc_streak += 1
                if non_toc_streak < 3:
                    continue
                in_toc = False

            # Prefer explicit markdown heading markers if present.
            md = re.match(r"^(#{1,6})\s+(.+)$", line)
            if md:
                title = md.group(2).strip()
                if title and not self._TOC_ENTRY_RE.search(title):
                    headings.append((line_start, len(md.group(1)), title))
                continue

            # Structural numbered headings from body lines.
            m = self._NUMBERED_HEADING.match(line)
            if not m:
                continue
            if self._TOC_ENTRY_RE.search(line) or self._TOC_LIKE_RE.search(line):
                continue

            sec_num = m.group(1)
            title = m.group(2).strip()
            if not title or len(title) > 140:
                continue
            if title.endswith(('.', ':', ';')):
                continue

            level = min(sec_num.count('.') + 1, 6)
            headings.append((line_start, level, f"{sec_num} {title}"))

        if not headings:
            return []

        # Deduplicate same-start matches, favor lower numeric level (higher priority).
        uniq: dict[int, tuple[int, int, str]] = {}
        for h in headings:
            existing = uniq.get(h[0])
            if existing is None or h[1] < existing[1]:
                uniq[h[0]] = h
        ordered = sorted(uniq.values(), key=lambda x: x[0])

        sections = []
        heading_stack: list[tuple[int, str]] = []
        for i, (start, level, title) in enumerate(ordered):
            end = ordered[i + 1][0] if i + 1 < len(ordered) else len(text)
            section_text = text[start:end]

            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            path = [t for _, t in heading_stack]

            sections.append({
                "title": title,
                "level": level,
                "offset": start,
                "text": section_text,
                "path": path,
            })

        first_start = sections[0]["offset"] if sections else 0
        if first_start > 0:
            preamble = text[:first_start]
            if preamble.strip():
                sections.insert(0, {
                    "title": "(preamble)",
                    "level": 0,
                    "offset": 0,
                    "text": preamble,
                    "path": [],
                })

        return sections

    def _extract_sections_markdown(self, text: str) -> list[dict]:
        headings = list(self._SECTION_HEADING.finditer(text))
        if not headings:
            return []

        sections = []
        heading_stack: list[tuple[int, str]] = []

        for index, match in enumerate(headings):
            level = len(match.group(1))
            title = match.group(2).strip()
            start = match.start()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            section_text = text[start:end]

            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            path = [t for _, t in heading_stack]

            sections.append({
                "title": title,
                "level": level,
                "offset": start,
                "text": section_text,
                "path": path,
            })

        if headings[0].start() > 0:
            preamble = text[:headings[0].start()]
            if preamble.strip():
                sections.insert(0, {
                    "title": "(preamble)",
                    "level": 0,
                    "offset": 0,
                    "text": preamble,
                    "path": [],
                })

        return sections

    def get_section_metadata(self, start_pos: int, end_pos: int) -> dict:
        if not hasattr(self, "_last_section_map") or not self._last_section_map:
            return {}

        for section in reversed(self._last_section_map):
            section_end = section["offset"] + len(section["text"])
            if section["offset"] <= start_pos < section_end:
                path = section["path"]  # list of ancestor titles + this title
                return {
                    "section_1": path[0] if len(path) > 0 else None,
                    "section_2": path[1] if len(path) > 1 else None,
                    "section_3": path[2] if len(path) > 2 else None,
                    "section_4": path[3] if len(path) > 3 else None,
                    "section_5": path[4] if len(path) > 4 else None,
                }
        return {}

    # ------------------------------------------------------------------
    # Strategy block END: section
    # ------------------------------------------------------------------

    @staticmethod
    def _collapse_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _find_sentence_boundary(text: str, start: int, end: int) -> int:
        endings = [". ", "! ", "? ", ".\n", "!\n", "?\n"]
        search_from = max(start, end - int((end - start) * 0.2))
        best = -1
        for ending in endings:
            pos = text.rfind(ending, search_from, end)
            if pos > best:
                best = pos + len(ending)
        return best if best > start else end

    @staticmethod
    def _collapse_with_index_map(text: str) -> tuple[str, list[int]]:
        """Collapse whitespace and keep mapping from collapsed indices to original indices."""
        collapsed_chars: list[str] = []
        index_map: list[int] = []
        prev_was_space = False

        for idx, ch in enumerate(text):
            if ch.isspace():
                if collapsed_chars and not prev_was_space:
                    collapsed_chars.append(" ")
                    index_map.append(idx)
                prev_was_space = True
            else:
                collapsed_chars.append(ch)
                index_map.append(idx)
                prev_was_space = False

        collapsed = "".join(collapsed_chars).strip()
        if not collapsed:
            return "", []

        # Align map with stripped collapsed text.
        left_trim = 0
        right_trim = len(collapsed_chars)

        while left_trim < right_trim and collapsed_chars[left_trim] == " ":
            left_trim += 1
        while right_trim > left_trim and collapsed_chars[right_trim - 1] == " ":
            right_trim -= 1

        return collapsed, index_map[left_trim:right_trim]


def get_chunker(
    chunk_size: int = 4000,
    chunk_overlap: int = 200,
    strategy: str = "recursive",
) -> SmartChunker:
    return SmartChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        strategy=strategy,
    )