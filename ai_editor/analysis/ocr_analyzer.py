from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore

from .analysis_schema import OCRSpan, VideoMetadata
from .style_extractor import extract_text_style
from .transition_detector import detect_text_transitions
from .visual_signature import VisualSignatureAnalyzer

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover
    PaddleOCR = None

try:
    import easyocr
except Exception:  # pragma: no cover
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

    def _normalize_ocr_text(self, value: str) -> str:
        return self._clean_text(value).lower()

    def _merge_ocr_spans_by_source(self, spans: List[OCRSpan]) -> List[OCRSpan]:
        merged: List[OCRSpan] = []
        grouped: Dict[str, List[OCRSpan]] = {}
        for span in spans:
            grouped.setdefault(span.source or "unknown", []).append(span)

        for source, source_spans in grouped.items():
            source_spans.sort(key=lambda item: item.timestamp)
            current_span: Optional[OCRSpan] = None
            current_text: str = ""
            for span in source_spans:
                normalized = self._normalize_ocr_text(span.text)
                if current_span is None:
                    current_span = OCRSpan(
                        timestamp=span.timestamp,
                        frame_number=span.frame_number,
                        span_end=span.timestamp,
                        text=span.text,
                        source=span.source,
                        confidence=span.confidence,
                        position=span.position,
                        bbox=span.bbox,
                        extracted_style=span.extracted_style,
                        transition_in=span.transition_in,
                        transition_out=span.transition_out,
                    )
                    current_text = normalized
                    continue
                if normalized == current_text:
                    current_span.span_end = span.timestamp
                    # Keep the last known transition_out so it reflects where the text disappears
                    if span.transition_out:
                        current_span.transition_out = span.transition_out
                    continue
                merged.append(current_span)
                current_span = OCRSpan(
                    timestamp=span.timestamp,
                    frame_number=span.frame_number,
                    span_end=span.timestamp,
                    text=span.text,
                    source=span.source,
                    confidence=span.confidence,
                    position=span.position,
                    bbox=span.bbox,
                    extracted_style=span.extracted_style,
                    transition_in=span.transition_in,
                    transition_out=span.transition_out,
                )
                current_text = normalized
            if current_span is not None:
                merged.append(current_span)
        return merged

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

                h, w = frame.shape[:2]
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
                                if not raw_text:
                                    continue
                                paddle_text.append(raw_text)

                                # PaddleOCR bbox: line[0] = [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                                raw_bbox = line[0] if line and len(line) > 0 else None
                                bbox_norm: Optional[List[List[float]]] = None
                                position: Optional[str] = None
                                if raw_bbox is not None:
                                    try:
                                        bbox_norm = [[float(pt[0]) / w, float(pt[1]) / h] for pt in raw_bbox]
                                        avg_y = sum(pt[1] for pt in raw_bbox) / 4
                                        if avg_y < h / 3:
                                            position = "Top"
                                        elif avg_y < 2 * h / 3:
                                            position = "Middle"
                                        else:
                                            position = "Bottom"
                                    except Exception:
                                        bbox_norm = None

                                extracted_style = (
                                    extract_text_style(frame, bbox_norm, w, h, text=raw_text)
                                    if bbox_norm else None
                                )

                                ocr_spans.append(
                                    OCRSpan(
                                        timestamp=timestamp,
                                        frame_number=frame_number,
                                        text=raw_text,
                                        source="paddleocr",
                                        confidence=float(line[1][1]) if line and len(line) > 1 else None,
                                        position=position,
                                        bbox=bbox_norm,
                                        extracted_style=extracted_style,
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
                        avg_y = sum(point[1] for point in bbox) / 4
                        if avg_y < h / 3:
                            position = "Top"
                        elif avg_y < 2 * h / 3:
                            position = "Middle"
                        else:
                            position = "Bottom"
                        cleaned = self._clean_text(text)
                        if not cleaned:
                            continue
                        easy_details.append(cleaned)

                        # Normalize bbox to [0, 1] fractions
                        bbox_norm = [[float(x) / w, float(y) / h] for x, y in bbox]
                        extracted_style = extract_text_style(frame, bbox_norm, w, h, text=cleaned)

                        ocr_spans.append(
                            OCRSpan(
                                timestamp=timestamp,
                                frame_number=frame_number,
                                text=cleaned,
                                source="easyocr",
                                confidence=float(conf),
                                position=position,
                                bbox=bbox_norm,
                                extracted_style=extracted_style,
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

            # Merge consecutive identical spans per source
            ocr_spans = self._merge_ocr_spans_by_source(ocr_spans)

            # Second pass: detect transitions for spans that have a bbox
            for span in ocr_spans:
                if span.bbox:
                    transitions = detect_text_transitions(
                        cap=cap,
                        span_start=span.timestamp,
                        span_end=span.span_end if span.span_end is not None else span.timestamp,
                        bbox_norm=span.bbox,
                        src_width=metadata.width,
                        src_height=metadata.height,
                    )
                    span.transition_in = transitions["transition_in"]
                    span.transition_out = transitions["transition_out"]

        finally:
            cap.release()

        return OCRAnalysisOutput(keyframes=keyframes, ocr_spans=ocr_spans)
