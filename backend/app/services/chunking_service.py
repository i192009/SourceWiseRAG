import math
from typing import Any, Dict, List


class ChunkingService:
    def __init__(
        self,
        target_tokens: int = 650,
        min_tokens: int = 500,
        max_tokens: int = 800,
        overlap_tokens: int = 100,
    ):
        self.target_tokens = target_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

    def chunk_units(self, source_id: str, document_id: str, units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []

        for unit in units:
            unit_type = unit["unit_type"]

            if unit_type == "excel_sheet":
                chunks.extend(self._chunk_excel_sheet(source_id, document_id, unit))
            else:
                chunks.extend(self._chunk_text_unit(source_id, document_id, unit))

        return chunks

    def _chunk_text_unit(self, source_id: str, document_id: str, unit: Dict[str, Any]) -> List[Dict[str, Any]]:
        text = (unit.get("raw_text") or "").strip()
        if not text:
            return []

        heading_path = unit.get("heading_path") or []
        prefix = self._build_context_prefix(unit)

        segments = self._split_preserving_paragraphs(text)
        merged = self._merge_segments_with_overlap(segments)

        results = []
        for idx, chunk_text in enumerate(merged):
            final_text = f"{prefix}\n{chunk_text}".strip()
            results.append({
                "source_id": source_id,
                "document_id": document_id,
                "chunk_index": idx,
                "text": final_text,
                "token_count": self.estimate_tokens(final_text),
                "metadata": {
                    "source_id": source_id,
                    "document_id": document_id,
                    "page_no": unit.get("page_number"),
                    "sheet_name": unit.get("sheet_name"),
                    "section_type": unit.get("unit_type"),
                    "heading_path": heading_path,
                    "unit_index": unit.get("unit_index"),
                },
            })

        return results

    def _chunk_excel_sheet(self, source_id: str, document_id: str, unit: Dict[str, Any]) -> List[Dict[str, Any]]:
        sheet_name = unit.get("sheet_name") or "unknown_sheet"
        raw_text = (unit.get("raw_text") or "").strip()
        if not raw_text:
            return []

        rows = [r.strip() for r in raw_text.splitlines() if r.strip()]
        if not rows:
            return []

        chunks: List[Dict[str, Any]] = []
        current_rows: List[str] = []
        current_start_row = None
        chunk_index = 0

        for row_text in rows:
            row_num = self._extract_row_number(row_text)

            candidate_rows = current_rows + [row_text]
            candidate_text = self._format_excel_chunk(sheet_name, candidate_rows)
            candidate_tokens = self.estimate_tokens(candidate_text)

            if candidate_tokens <= self.max_tokens:
                if current_start_row is None:
                    current_start_row = row_num
                current_rows.append(row_text)
            else:
                if current_rows:
                    final_text = self._format_excel_chunk(sheet_name, current_rows)
                    chunks.append({
                        "source_id": source_id,
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "text": final_text,
                        "token_count": self.estimate_tokens(final_text),
                        "metadata": {
                            "source_id": source_id,
                            "document_id": document_id,
                            "page_no": None,
                            "sheet_name": sheet_name,
                            "section_type": "excel_sheet",
                            "heading_path": [],
                            "row_start": current_start_row,
                            "row_end": self._extract_row_number(current_rows[-1]),
                            "unit_index": unit.get("unit_index"),
                        },
                    })
                    chunk_index += 1

                overlap_rows = self._take_excel_overlap_rows(current_rows)
                current_rows = overlap_rows + [row_text]
                current_start_row = self._extract_row_number(current_rows[0]) if current_rows else row_num

        if current_rows:
            final_text = self._format_excel_chunk(sheet_name, current_rows)
            chunks.append({
                "source_id": source_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": final_text,
                "token_count": self.estimate_tokens(final_text),
                "metadata": {
                    "source_id": source_id,
                    "document_id": document_id,
                    "page_no": None,
                    "sheet_name": sheet_name,
                    "section_type": "excel_sheet",
                    "heading_path": [],
                    "row_start": current_start_row,
                    "row_end": self._extract_row_number(current_rows[-1]),
                    "unit_index": unit.get("unit_index"),
                },
            })

        return chunks

    def _split_preserving_paragraphs(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        segments: List[str] = []

        for para in paragraphs:
            if self.estimate_tokens(para) <= self.max_tokens:
                segments.append(para)
            else:
                segments.extend(self._split_long_paragraph(para))

        return segments

    def _split_long_paragraph(self, para: str) -> List[str]:
        sentence_like = para.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n")
        pieces = [p.strip() for p in sentence_like.split("\n") if p.strip()]

        if not pieces:
            return [para]

        results: List[str] = []
        current = ""

        for piece in pieces:
            candidate = f"{current} {piece}".strip() if current else piece
            if self.estimate_tokens(candidate) <= self.max_tokens:
                current = candidate
            else:
                if current:
                    results.append(current)
                current = piece

        if current:
            results.append(current)

        final_results: List[str] = []
        for item in results:
            if self.estimate_tokens(item) <= self.max_tokens:
                final_results.append(item)
            else:
                final_results.extend(self._hard_window_split(item))

        return final_results

    def _hard_window_split(self, text: str) -> List[str]:
        chars_per_window = self.target_tokens * 4
        overlap_chars = self.overlap_tokens * 4

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chars_per_window, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = max(end - overlap_chars, start + 1)

        return chunks

    def _merge_segments_with_overlap(self, segments: List[str]) -> List[str]:
        chunks: List[str] = []
        current_parts: List[str] = []

        for segment in segments:
            candidate = "\n\n".join(current_parts + [segment]).strip()

            if self.estimate_tokens(candidate) <= self.max_tokens:
                current_parts.append(segment)
            else:
                if current_parts:
                    finalized = "\n\n".join(current_parts).strip()
                    chunks.append(finalized)

                    overlap_parts = self._take_text_overlap(current_parts)
                    current_parts = overlap_parts + [segment]
                else:
                    chunks.append(segment)
                    current_parts = []

        if current_parts:
            chunks.append("\n\n".join(current_parts).strip())

        return chunks

    def _take_text_overlap(self, parts: List[str]) -> List[str]:
        selected: List[str] = []
        total = 0

        for part in reversed(parts):
            t = self.estimate_tokens(part)
            if total + t > self.overlap_tokens and selected:
                break
            selected.insert(0, part)
            total += t

        return selected

    def _take_excel_overlap_rows(self, rows: List[str]) -> List[str]:
        selected: List[str] = []
        total = 0

        for row in reversed(rows):
            t = self.estimate_tokens(row)
            if total + t > self.overlap_tokens and selected:
                break
            selected.insert(0, row)
            total += t

        return selected

    def _build_context_prefix(self, unit: Dict[str, Any]) -> str:
        lines = []

        if unit.get("unit_type"):
            lines.append(f"Section Type: {unit['unit_type']}")

        if unit.get("page_number") is not None:
            lines.append(f"Page: {unit['page_number']}")

        if unit.get("sheet_name"):
            lines.append(f"Sheet: {unit['sheet_name']}")

        heading_path = unit.get("heading_path") or []
        if heading_path:
            lines.append("Heading Path: " + " > ".join(heading_path))

        return "\n".join(lines)

    def _format_excel_chunk(self, sheet_name: str, rows: List[str]) -> str:
        return f"Sheet: {sheet_name}\n" + "\n".join(rows)

    def _extract_row_number(self, row_text: str):
        if row_text.startswith("row_"):
            try:
                prefix = row_text.split(":", 1)[0]
                return int(prefix.replace("row_", "").strip())
            except Exception:
                return None
        return None
