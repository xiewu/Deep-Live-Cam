from typing import Any, List
import cv2
import insightface
import threading
import os

import modules.globals
import modules.processors.frame.core
from modules.core import update_status
from modules.face_analyser import get_one_face, get_many_faces
from modules.typing import Face, Frame
from modules.utilities import conditional_download, resolve_relative_path, is_image, is_video
import numpy as np

FACE_SWAPPER = None
THREAD_LOCK = threading.Lock()
NAME = 'DLC.FACE-SWAPPER'

def pre_check() -> bool:
    download_directory_path = resolve_relative_path('../models')
    conditional_download(download_directory_path, [
        'https://huggingface.co/hacksider/deep-live-cam/blob/main/inswapper_128.onnx'
    ])
    return True

def pre_start() -> bool:
    if not is_image(modules.globals.source_path):
        update_status('Select an image for source path.', NAME)
        return False
    elif not get_one_face(cv2.imread(modules.globals.source_path)):
        update_status('No face detected in the source path.', NAME)
        return False
    if not is_image(modules.globals.target_path) and not is_video(modules.globals.target_path):
        update_status('Select an image or video for target path.', NAME)
        return False
    return True

def get_face_swapper() -> Any:
    global FACE_SWAPPER

    with THREAD_LOCK:
        if FACE_SWAPPER is None:
            model_path = resolve_relative_path('../models/inswapper_128.onnx')
            FACE_SWAPPER = insightface.model_zoo.get_model(model_path, providers=modules.globals.execution_providers)
    return FACE_SWAPPER

def upscale_image(image: np.ndarray, scaling_factor: int = modules.globals.source_image_scaling_factor) -> np.ndarray:
    """
    Upscales the given image by the specified scaling factor.

    Args:
        image (np.ndarray): The input image to upscale.
        scaling_factor (int): The factor by which to upscale the image.

    Returns:
        np.ndarray: The upscaled image.
    """
    height, width = image.shape[:2]
    new_size = (width * scaling_factor, height * scaling_factor)
    upscaled_image = cv2.resize(image, new_size, interpolation=cv2.INTER_CUBIC)
    return upscaled_image

def swap_face(source_face: Face, target_face: Face, temp_frame: Frame) -> Frame:
    return get_face_swapper().get(temp_frame, target_face, source_face, paste_back=True)

def process_frame(source_face: Face, temp_frame: Frame) -> Frame:
    if modules.globals.many_faces:
        many_faces = get_many_faces(temp_frame)
        if many_faces:
            for target_face in many_faces:
                temp_frame = swap_face(source_face, target_face, temp_frame)
    else:
        target_face = get_one_face(temp_frame)
        if target_face:
            temp_frame = swap_face(source_face, target_face, temp_frame)
    return temp_frame

def process_frames(source_path: str, temp_frame_paths: List[str], progress: Any = None) -> None:
    source_image = cv2.imread(source_path)
    if source_image is None:
        print(f"Failed to load source image from {source_path}")
        return
    # Upscale the source image for better quality
    source_image_upscaled = upscale_image(source_image, scaling_factor=2)
    source_face = get_one_face(source_image_upscaled)

    for temp_frame_path in temp_frame_paths:
        temp_frame = cv2.imread(temp_frame_path)
        try:
            result = process_frame(source_face, temp_frame)
            cv2.imwrite(temp_frame_path, result)
        except Exception as exception:
            print(f"Error processing frame {temp_frame_path}: {exception}")
        if progress:
            progress.update(1)

def process_image(source_path: str, target_path: str, output_path: str) -> None:
    source_face = get_one_face(cv2.imread(source_path))
    target_frame = cv2.imread(target_path)
    result = process_frame(source_face, target_frame)
    cv2.imwrite(output_path, result)

def process_video(source_path: str, temp_frame_paths: List[str]) -> None:
    modules.processors.frame.core.process_video(source_path, temp_frame_paths, process_frames)
