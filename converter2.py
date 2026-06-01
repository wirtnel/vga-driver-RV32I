"""
Copyright (C) 2026 wirtnel

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import cv2
import numpy as np
import sys

def convert_video(input_file, output_file, max_frames=2000):
    cap = cv2.VideoCapture(input_file)
    if not cap.isOpened():
        print("Error opening video.")
        sys.exit(1)

    print(f"Processing video... (Max {max_frames} frames)")

    with open(output_file, 'wb') as f:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret or frame_count >= max_frames:
                break

            # Resize to VRAM resolution
            resized = cv2.resize(frame, (40, 30), interpolation=cv2.INTER_AREA)

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

            # Quantize directly to RGB332 format using Numpy bitwise operations
            # Shift colors to their respective bit positions in an 8-bit byte
            r = (rgb_frame[:, :, 0] >> 5) << 5
            g = (rgb_frame[:, :, 1] >> 5) << 2
            b = (rgb_frame[:, :, 2] >> 6)

            rgb332 = r | g | b

            # Write the 1D byte array
            f.write(rgb332.astype(np.uint8).tobytes())

            frame_count += 1
            if frame_count % 100 == 0:
                print(f"Frames procesados: {frame_count}")

    cap.release()
    print(f"Filed: {output_file} saved wtih: ({frame_count * 1200} bytes).")

if __name__ == "__main__":
    video = input("Insert video file name: ")
    convert_video(video, "video.bin")
