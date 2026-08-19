from typing import Dict, Any, List


class OCRService:
    def __init__(self):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en")

    def extract_text_with_confidence(self, image_path: str) -> Dict[str, Any]:
        result = self.ocr.ocr(image_path, cls=True)

        lines: List[Dict[str, Any]] = []
        confidences: List[float] = []

        for block in result:
            for item in block:
                box = item[0]
                text = item[1][0]
                confidence = float(item[1][1])

                lines.append({
                    "text": text,
                    "confidence": confidence,
                    "box": box,
                })
                confidences.append(confidence)

        joined_text = "\n".join(line["text"] for line in lines).strip()
        avg_confidence = sum(confidences) / len(confidences) if confidences else None

        return {
            "text": joined_text,
            "average_confidence": avg_confidence,
            "lines": lines,
        }
