"""Render the compact SVG artwork for Tk and the Windows icon.

Only the SVG primitives used by tm-device-icon-small.svg are supported. This
keeps the editable vector as the single source of truth for the raster assets.
"""

from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


HERE = Path(__file__).parent
SOURCE = HERE / "tm-device-icon-small.svg"
NAMESPACE = "{http://www.w3.org/2000/svg}"


def render(size: int) -> Image.Image:
    image = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = size * 4 / 256
    root = ET.parse(SOURCE).getroot()
    for element in root:
        if element.tag == NAMESPACE + "rect":
            x = float(element.attrib["x"]) * scale
            y = float(element.attrib["y"]) * scale
            width = float(element.attrib["width"]) * scale
            height = float(element.attrib["height"]) * scale
            radius = float(element.attrib.get("rx", "0")) * scale
            draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=element.attrib["fill"])
        elif element.tag == NAMESPACE + "polygon":
            points = [tuple(float(n) * scale for n in point.split(","))
                      for point in element.attrib["points"].split()]
            draw.polygon(points, fill=element.attrib["fill"])
    return image.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    render(56).save(HERE / "tm-device-icon-header.png")
    render(256).save(HERE / "tm-device-icon-small.png")
