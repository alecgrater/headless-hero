"""Reusable chroma-key cutout helpers for generated visual layers."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image


def save_keyed_trimmed_cutout(
    image: Image.Image,
    output_path: Path,
    *,
    padding: int = 24,
    tolerance: int = 70,
) -> list[int]:
    keyed = key_out_background(image.convert("RGBA"), tolerance=tolerance)
    bbox = keyed.getbbox()
    if bbox is None:
        keyed.save(output_path)
        return [0, 0, keyed.width, keyed.height]

    left, top, right, bottom = bbox
    padded = [
        max(0, left - padding),
        max(0, top - padding),
        min(keyed.width, right + padding),
        min(keyed.height, bottom + padding),
    ]
    keyed.crop(tuple(padded)).save(output_path)
    return padded


def key_out_background(image: Image.Image, *, tolerance: int = 70) -> Image.Image:
    image = image.convert("RGBA")
    chroma_bg = detect_chroma_background_rgb(image)
    background_keys = [(chroma_bg, tolerance)] if chroma_bg else []
    if chroma_bg:
        margin_bg = detect_neutral_margin_rgb(image)
        if margin_bg:
            background_keys.append((margin_bg, min(tolerance, 35)))
        dark_margin_bg = detect_dark_margin_rgb(image)
        if dark_margin_bg:
            background_keys.append((dark_margin_bg, min(tolerance, 35)))
    else:
        corner_bg = sample_background_rgb(image)
        background_keys.append((corner_bg, tolerance))
    data = bytearray(image.tobytes())
    background_pixels = find_edge_connected_background_pixels(image, background_keys)
    for pixel_index in background_pixels:
        data[pixel_index * 4 + 3] = 0
    keyed = Image.frombytes("RGBA", image.size, bytes(data))
    return remove_small_edge_alpha_artifacts(keyed)


def remove_small_edge_alpha_artifacts(
    image: Image.Image,
    *,
    max_area_ratio: float = 0.02,
    max_area_pixels: int = 512,
    edge_margin: int = 2,
) -> Image.Image:
    image = image.convert("RGBA")
    width, height = image.size
    data = bytearray(image.tobytes())
    visited: set[int] = set()
    max_area = max(24, min(round(width * height * max_area_ratio), max_area_pixels))

    for pixel_index in range(width * height):
        if pixel_index in visited or data[pixel_index * 4 + 3] == 0:
            continue

        queue: deque[int] = deque([pixel_index])
        visited.add(pixel_index)
        component: list[int] = []
        touches_edge = False
        min_x = width
        min_y = height
        max_x = 0
        max_y = 0

        while queue:
            current = queue.popleft()
            component.append(current)
            x = current % width
            y = current // width
            touches_edge = (
                touches_edge
                or x <= edge_margin
                or y <= edge_margin
                or x >= width - 1 - edge_margin
                or y >= height - 1 - edge_margin
            )
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

            neighbors = []
            if x > 0:
                neighbors.append(current - 1)
            if x < width - 1:
                neighbors.append(current + 1)
            if y > 0:
                neighbors.append(current - width)
            if y < height - 1:
                neighbors.append(current + width)
            for neighbor in neighbors:
                if neighbor in visited or data[neighbor * 4 + 3] == 0:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)

        if touches_edge and len(component) <= max_area:
            for component_pixel in component:
                data[component_pixel * 4 + 3] = 0

    return Image.frombytes("RGBA", image.size, bytes(data))


def find_edge_connected_background_pixels(
    image: Image.Image,
    background_keys: list[tuple[tuple[int, int, int], int]],
) -> set[int]:
    width, height = image.size
    data = image.convert("RGBA").tobytes()
    queue: deque[int] = deque()
    visited: set[int] = set()
    background_pixels: set[int] = set()

    def enqueue(pixel_index: int) -> None:
        if pixel_index not in visited:
            visited.add(pixel_index)
            queue.append(pixel_index)

    for x in range(width):
        enqueue(x)
        enqueue((height - 1) * width + x)
    for y in range(height):
        enqueue(y * width)
        enqueue(y * width + width - 1)

    while queue:
        pixel_index = queue.popleft()
        offset = pixel_index * 4
        red, green, blue, alpha = data[offset:offset + 4]
        if alpha == 0:
            background_pixels.add(pixel_index)
        elif any(
            ((red - bg[0]) ** 2 + (green - bg[1]) ** 2 + (blue - bg[2]) ** 2) ** 0.5 <= key_tolerance
            for bg, key_tolerance in background_keys
        ):
            background_pixels.add(pixel_index)
        else:
            continue

        x = pixel_index % width
        y = pixel_index // width
        if x > 0:
            enqueue(pixel_index - 1)
        if x < width - 1:
            enqueue(pixel_index + 1)
        if y > 0:
            enqueue(pixel_index - width)
        if y < height - 1:
            enqueue(pixel_index + width)

    return background_pixels


def detect_neutral_margin_rgb(image: Image.Image) -> tuple[int, int, int] | None:
    image = image.convert("RGBA")
    data = image.tobytes()
    count = 0
    total = [0, 0, 0]
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index:index + 4]
        if alpha == 0:
            continue
        if max(red, green, blue) - min(red, green, blue) > 35:
            continue
        if (red + green + blue) / 3 < 150:
            continue
        count += 1
        total[0] += red
        total[1] += green
        total[2] += blue

    min_pixels = max(24, round(image.width * image.height * 0.001))
    if count < min_pixels:
        return None
    return (round(total[0] / count), round(total[1] / count), round(total[2] / count))


def detect_dark_margin_rgb(image: Image.Image) -> tuple[int, int, int] | None:
    image = image.convert("RGBA")
    data = image.tobytes()
    edge_samples = {
        "top": [],
        "bottom": [],
        "left": [],
        "right": [],
    }

    def maybe_add(edge: str, x: int, y: int) -> None:
        offset = (y * image.width + x) * 4
        red, green, blue, alpha = data[offset:offset + 4]
        if alpha == 0:
            return
        if max(red, green, blue) > 35:
            return
        edge_samples[edge].append((red, green, blue))

    for x in range(image.width):
        maybe_add("top", x, 0)
        maybe_add("bottom", x, image.height - 1)
    for y in range(image.height):
        maybe_add("left", 0, y)
        maybe_add("right", image.width - 1, y)

    qualifying_samples = []
    min_edge_coverage = 0.6
    for edge, samples in edge_samples.items():
        edge_length = image.width if edge in {"top", "bottom"} else image.height
        if len(samples) / max(edge_length, 1) >= min_edge_coverage:
            qualifying_samples.extend(samples)

    if not qualifying_samples:
        return None
    return (
        round(sum(pixel[0] for pixel in qualifying_samples) / len(qualifying_samples)),
        round(sum(pixel[1] for pixel in qualifying_samples) / len(qualifying_samples)),
        round(sum(pixel[2] for pixel in qualifying_samples) / len(qualifying_samples)),
    )


def detect_chroma_background_rgb(image: Image.Image) -> tuple[int, int, int] | None:
    image = image.convert("RGBA")
    data = image.tobytes()
    counts = {
        "green": 0,
        "magenta": 0,
    }
    totals = {
        "green": [0, 0, 0],
        "magenta": [0, 0, 0],
    }
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index:index + 4]
        if alpha == 0:
            continue
        if green >= 150 and green - red >= 35 and green - blue >= 35:
            counts["green"] += 1
            totals["green"][0] += red
            totals["green"][1] += green
            totals["green"][2] += blue
        elif red >= 170 and blue >= 120 and red - green >= 80 and blue - green >= 60:
            counts["magenta"] += 1
            totals["magenta"][0] += red
            totals["magenta"][1] += green
            totals["magenta"][2] += blue

    min_pixels = max(24, round(image.width * image.height * 0.05))
    key = max(counts, key=lambda name: counts[name])
    if counts[key] < min_pixels:
        return None
    total = totals[key]
    count = counts[key]
    return (round(total[0] / count), round(total[1] / count), round(total[2] / count))


def sample_background_rgb(image: Image.Image) -> tuple[int, int, int]:
    corner_size = min(24, max(1, image.width // 2), max(1, image.height // 2))
    corners = [
        image.crop((0, 0, corner_size, corner_size)),
        image.crop((image.width - corner_size, 0, image.width, corner_size)),
        image.crop((0, image.height - corner_size, corner_size, image.height)),
        image.crop((image.width - corner_size, image.height - corner_size, image.width, image.height)),
    ]
    samples = []
    for corner in corners:
        data = corner.convert("RGB").tobytes()
        samples.extend((data[index], data[index + 1], data[index + 2]) for index in range(0, len(data), 3))
    red = round(sum(pixel[0] for pixel in samples) / len(samples))
    green = round(sum(pixel[1] for pixel in samples) / len(samples))
    blue = round(sum(pixel[2] for pixel in samples) / len(samples))
    return red, green, blue
