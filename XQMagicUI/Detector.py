import logging
from pathlib import Path

import numpy as np
import cv2

from PyQt5.QtGui import QPixmap, QImage

from cchess import ChessBoard, fen_flip

from cchess_board.detector import labels_to_fen
from cchess_board import ChessboardDetector as _ChessboardDetector


# -----------------------------------------------------#
class ChessboardDetector:
    def __init__(self, model_path: str):
        self._detector = _ChessboardDetector(str(model_path))


    def cv_image_to_fen_with_marked(self, img_bgr):
        """
        Recognize chess board and return marked image.
        Returns: (marked_pixmap, fen, is_fliped)
            - marked_pixmap: QPixmap of the detected board layout
            - fen: FEN string, or None if detection failed
            - is_fliped: True if the board was detected as flipped (red king on top)
        """
        try:
            transformed_image, cell_labels = (
                self._detector.pred_detect_board_and_classifier(img_bgr)
            )
            if not cell_labels:
                return None, None, False
            print(cell_labels)    
            fen, is_fliped = labels_to_fen(cell_labels)

            height, width = transformed_image.shape[:2]
            bytes_per_line = 3 * width
            q_img = QImage(
                transformed_image.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_BGR888,
            )
            pixmap = QPixmap.fromImage(q_img.copy())
            
            return pixmap, fen, is_fliped
        except Exception as e:
            logging.error(f"ChessboardDetector.cv_image_to_fen_with_marked error: {e}")
            raise
