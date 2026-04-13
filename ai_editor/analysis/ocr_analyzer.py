from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

try:
    import cv2
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore

try:
    import numpy as np
except Exception:  # pragma: no cover - dependency availability varies by environment
    np = None  # type: ignore

from .analysis_schema import OCRSpan, VideoMetadata
from .visual_signature import VisualSignatureAnalyzer

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - dependency availability varies by environment
    PaddleOCR = None

try:
    import easyocr
except Exception:  # pragma: no cover - dependency availability varies by environment
    easyocr = None


@dataclass
class OCRAnalysisOutput:
    keyframes: List[dict]
    ocr_spans: List[OCRSpan]


class OCRAnalyzer:
    """Frame-sampled OCR analysis that preserves legacy keyframe output."""

    def __init__(self) -> None:
        self._paddle_ocr = None
        self._easy_reader = None
        self.visual_signature_analyzer = VisualSignatureAnalyzer()

    def _clean_text(self, value: str) -> str:
        txt = str(value or "")
        txt = re.sub(r"\((?:top|bottom|middle|center)\)", "", txt, flags=re.IGNORECASE)
        txt = txt.replace("|", " ")
        txt = txt.replace("'", "")
        txt = " ".join(txt.split())
        return txt.strip()

    def _get_paddle(self):
        if self._paddle_ocr is not None:
            return self._paddle_ocr
        if PaddleOCR is None:
            return None
        try:
            self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en")
        except Exception as exc:
            print(f"PaddleOCR initialization failed, continuing without it: {exc}")
            self._paddle_ocr = None
        return self._paddle_ocr

    def _get_easy_reader(self):
        if self._easy_reader is not None:
            return self._easy_reader
        if easyocr is None:
            return None
        self._easy_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return self._easy_reader

    def analyze(self, video_path: str, metadata: VideoMetadata, num_frames: int = 12) -> OCRAnalysisOutput:
        if cv2 is None or np is None:
            return OCRAnalysisOutput(keyframes=[], ocr_spans=[])
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened() or metadata.total_frames <= 0 or metadata.fps <= 0:
            if cap.isOpened():
                cap.release()
            return OCRAnalysisOutput(keyframes=[], ocr_spans=[])

        paddle = self._get_paddle()
        easy_reader = self._get_easy_reader()
        keyframes: List[dict] = []
        ocr_spans: List[OCRSpan] = []
        intervals = max(1, metadata.total_frames // max(1, num_frames))

        try:
            for frame_number in range(0, metadata.total_frames, intervals):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))
                timestamp = frame_number / metadata.fps

                paddle_text: List[str] = []
                if paddle is not None:
                    try:
                        paddle_res = paddle.ocr(frame, cls=True)
                        if paddle_res and paddle_res[0]:
                            for line in paddle_res[0]:
                                raw_text = self._clean_text(line[1][0] if line and len(line) > 1 else "")
                                if raw_text:
                                    paddle_text.append(raw_text)
                                    ocr_spans.append(
                                        OCRSpan(
                                            timestamp=timestamp,
                                            frame_number=frame_number,
                                            text=raw_text,
                                            source="paddleocr",
                                            confidence=float(line[1][1]) if line and len(line) > 1 else None,
                                        )
                                    )
                    except Exception as exc:
                        print(f"PaddleOCR per-frame OCR failed, skipping for this frame: {exc}")

                easy_details: List[str] = []
                if easy_reader is not None:
                    easy_res = easy_reader.readtext(frame)
                    for bbox, text, conf in easy_res:
                        if conf <= 0.3:
                            continue
                        h, _w = frame.shape[:2]
                        avg_y = sum(point[1] for point in bbox) / 4
                        if avg_y < h / 3:
                            position = "Top"
                        elif avg_y < 2 * h / 3:
                            position = "Middle"
                        else:
                            position = "Bottom"
                        cleaned = self._clean_text(text)
                        if cleaned:
                            easy_details.append(cleaned)
                            ocr_spans.append(
                                OCRSpan(
                                    timestamp=timestamp,
                                    frame_number=frame_number,
                                    text=cleaned,
                                    source="easyocr",
                                    confidence=float(conf),
                                    position=position,
                                    bbox=[[float(x), float(y)] for x, y in bbox],
                                )
                            )

                detected_text = "; ".join(paddle_text) if paddle_text else "No text"
                if not paddle_text and easy_details:
                    detected_text = "; ".join(easy_details)

                keyframes.append(
                    {
                        "timestamp": timestamp,
                        "frame_number": frame_number,
                        "brightness": brightness,
                        "contrast": float(np.std(gray)),
                        "detected_text": detected_text,
                        "easyocr_details": easy_details,
                        "visual_signature": self.visual_signature_analyzer.describe_frame(frame),
                    }
                )
        finally:
            cap.release()

        return OCRAnalysisOutput(keyframes=keyframes, ocr_spans=ocr_spans)
