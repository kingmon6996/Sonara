# Copyright 2026 Pravanjan Roy (kingmon6996)
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from PIL import Image, ImageDraw, ImageFont
import io
import os

FONT_FILE = os.path.join("data", "fonts", "Berlin-Sans.TTF")

def create_card(
    image_bytes: bytes,
    background_path: str,
    heading: str,
    author: str,
    player: str,
    time_text: str,
) -> bytes:

    bg = Image.open(background_path).convert("RGBA")
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    bg.paste(img, (55, 55), img)

    draw = ImageDraw.Draw(bg)

    try:
        title_font = ImageFont.truetype(FONT_FILE, 86)
        meta_font = ImageFont.truetype(FONT_FILE, 46)
        small_font = ImageFont.truetype(FONT_FILE, 42)
    except:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
        small_font = ImageFont.load_default()


    draw.text((570, 70), heading, font=title_font, fill="black")
    draw.text((675, 230), author, font=meta_font, fill="black")
    draw.text((660, 420), player, font=small_font, fill="black")
    draw.text((1300, 420), time_text, font=meta_font, fill="black")


    output = io.BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)

    return output.getvalue()

def resize_and_round(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize((420, 420), Image.Resampling.LANCZOS)

    w, h = img.size

    radius = int(min(w, h) * 0.1)

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [(0, 0), (w, h)],
        radius=radius,
        fill=255
    )


    img.putalpha(mask)


    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)

    return output.getvalue()

def shorten_title(text: str) -> str:
    if len(text) > 26:
        return text[:22] + " ..."
    return text