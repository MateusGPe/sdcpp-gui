from __future__ import annotations

import gc
import tkinter as tk
from functools import lru_cache
from typing import Any, Dict, List, NamedTuple, Optional, TypedDict

from PIL import Image, ImageDraw, ImageFilter, ImageTk

FIRST_RESAMPLING = Image.Resampling.NEAREST
LAST_RESAMPLING = Image.Resampling.BICUBIC
GLOBAL_SCALE = 2


class ColorPalette(TypedDict):
    bg: str
    bg_base: str
    bg_hover: str
    border: str
    shadow: str
    parent: str


class StyleKey(NamedTuple):
    """Unique hashable key defining the visual style of a widget."""

    bg: str
    border_color: str
    shadow_color: str
    parent_bg: str
    radius: int
    border_width: int
    elevation: int


class TextureAtlas:
    """
    The Global Texture Atlas.
    Manages shared PhotoImages.
    Uses LRU Caching for ImageTk objects to prevent ID exhaustion while
     maintaining performance.
    """

    @staticmethod
    def clear_cache() -> None:
        """
        Forces a cleanup of all internal caches.
        Call this before changing themes to free VRAM/Tcl IDs.

        Logic: Clears all LRU caches and calls gc.collect()."""
        _AssetFactory.generate_source_assets.cache_clear()
        TextureAtlas._get_corners_pil.cache_clear()
        TextureAtlas._get_horizontal_edges_pil.cache_clear()
        TextureAtlas._get_vertical_edges_pil.cache_clear()
        TextureAtlas.get_corners.cache_clear()
        TextureAtlas.get_horizontal_edges.cache_clear()
        TextureAtlas.get_vertical_edges.cache_clear()
        gc.collect()

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_corners_pil(key: StyleKey) -> Dict[str, Image.Image]:
        """Logic: Generates PIL images for corners from source assets."""
        src = _AssetFactory.generate_source_assets(key)
        cut = src["cut_size"] // GLOBAL_SCALE
        corners = {}
        for k in ["tl", "tr", "bl", "br"]:
            img = src[k].resize((cut, cut), LAST_RESAMPLING)
            corners[k] = img
        return corners

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_horizontal_edges_pil(
        key: StyleKey, width_px: int
    ) -> Dict[str, Image.Image]:
        """Logic: Generates resized PIL images for horizontal edges."""
        if width_px <= 0:
            return {}
        src = _AssetFactory.generate_source_assets(key)
        cut_raw = src["cut_size"]
        cut_view = cut_raw // GLOBAL_SCALE
        target_w_src = int(width_px * GLOBAL_SCALE)
        edges = {}
        t_img = src["top"].resize((target_w_src, cut_raw), FIRST_RESAMPLING)
        edges["t"] = t_img.resize((width_px, cut_view), LAST_RESAMPLING)
        b_img = src["bottom"].resize((target_w_src, cut_raw), FIRST_RESAMPLING)
        edges["b"] = b_img.resize((width_px, cut_view), LAST_RESAMPLING)
        return edges

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_vertical_edges_pil(
        key: StyleKey, height_px: int
    ) -> Dict[str, Image.Image]:
        """Logic: Generates resized PIL images for vertical edges."""
        if height_px <= 0:
            return {}
        src = _AssetFactory.generate_source_assets(key)
        cut_raw = src["cut_size"]
        cut_view = cut_raw // GLOBAL_SCALE
        target_h_src = int(height_px * GLOBAL_SCALE)
        edges = {}
        l_img = src["left"].resize((cut_raw, target_h_src), FIRST_RESAMPLING)
        edges["l"] = l_img.resize((cut_view, height_px), LAST_RESAMPLING)
        r_img = src["right"].resize((cut_raw, target_h_src), FIRST_RESAMPLING)
        edges["r"] = r_img.resize((cut_view, height_px), LAST_RESAMPLING)
        return edges

    @staticmethod
    @lru_cache(maxsize=32)
    def get_corners(key: StyleKey) -> Dict[str, ImageTk.PhotoImage]:
        """Logic: Converts PIL corner images to ImageTk.PhotoImage."""
        pil_corners = TextureAtlas._get_corners_pil(key)
        return {k: ImageTk.PhotoImage(img) for k, img in pil_corners.items()}

    @staticmethod
    @lru_cache(maxsize=128)
    def get_horizontal_edges(
        key: StyleKey, width_px: int
    ) -> Dict[str, ImageTk.PhotoImage]:
        """Logic: Converts PIL horizontal edge images to ImageTk.PhotoImage."""
        pil_edges = TextureAtlas._get_horizontal_edges_pil(key, width_px)
        return {k: ImageTk.PhotoImage(img) for k, img in pil_edges.items()}

    @staticmethod
    @lru_cache(maxsize=64)
    def get_vertical_edges(
        key: StyleKey, height_px: int
    ) -> Dict[str, ImageTk.PhotoImage]:
        """Logic: Converts PIL vertical edge images to ImageTk.PhotoImage."""
        pil_edges = TextureAtlas._get_vertical_edges_pil(key, height_px)
        return {k: ImageTk.PhotoImage(img) for k, img in pil_edges.items()}


class _AssetFactory:
    """Internal factory to generate the High-Res PIL source material."""

    @staticmethod
    @lru_cache(maxsize=64)
    def generate_source_assets(key: StyleKey) -> dict:
        """
        Logic: Draws rounded rectangle base shapes with shadows/borders
        using PIL Draw."""
        s = GLOBAL_SCALE
        r_px = key.radius * s
        bw_px = int(key.border_width * s)
        elevation_px = key.elevation * s
        shadow_pad = int(elevation_px * 2.5)
        cut = shadow_pad + r_px
        master_size = cut * 2 + 2
        img = Image.new("RGBA", (master_size, master_size), color=key.parent_bg)
        if key.elevation > 0:
            shadow_layer = Image.new(
                "RGBA", (master_size, master_size), (0, 0, 0, 0)
            )
            shadow_draw = ImageDraw.Draw(shadow_layer)
            hex_c = key.shadow_color.lstrip("#")
            try:
                rgb = tuple((int(hex_c[i : i + 2], 16) for i in (0, 2, 4)))
            except ValueError:
                rgb = (0, 0, 0)
            shadow_rgba = (rgb[0], rgb[1], rgb[2], 60)
            offset_y = key.elevation * s // 2
            s_rect = (
                float(shadow_pad),
                float(shadow_pad + offset_y),
                float(master_size - shadow_pad),
                float(master_size - shadow_pad + offset_y),
            )
            shadow_draw.rounded_rectangle(s_rect, radius=r_px, fill=shadow_rgba)
            shadow_layer = shadow_layer.filter(
                ImageFilter.GaussianBlur(radius=elevation_px)
            )
            img.paste(shadow_layer, (0, 0), shadow_layer)
        draw = ImageDraw.Draw(img)
        rect = (
            float(shadow_pad),
            float(shadow_pad),
            float(master_size - shadow_pad),
            float(master_size - shadow_pad),
        )
        draw.rounded_rectangle(rect, radius=r_px, fill=key.bg)
        if bw_px > 0:
            draw.rounded_rectangle(
                rect, radius=r_px, outline=key.border_color, width=bw_px
            )
        w, h = (master_size, master_size)
        mid_x, mid_y = (cut, cut)
        return {
            "tl": img.crop((0, 0, cut, cut)),
            "tr": img.crop((w - cut, 0, w, cut)),
            "bl": img.crop((0, h - cut, cut, h)),
            "br": img.crop((w - cut, h - cut, w, h)),
            "top": img.crop((mid_x, 0, mid_x + 1, cut)),
            "bottom": img.crop((mid_x, h - cut, mid_x + 1, h)),
            "left": img.crop((0, mid_y, cut, mid_y + 1)),
            "right": img.crop((w - cut, mid_y, w, mid_y + 1)),
            "cut_size": cut,
        }


class NineSliceRenderer:
    def __init__(self, radius: int, border_width: int, elevation: int) -> None:
        """Logic: Initializes renderer properties."""
        self.radius = radius
        self.border_width = border_width
        self.elevation = elevation
        self._current_key: Optional[StyleKey] = None
        self._last_width: Optional[int] = None
        self._last_height: Optional[int] = None
        self._last_key: Optional[StyleKey] = None
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None
        self._current_images_ref: List[Any] = []

    def generate_slices(self, colors: ColorPalette) -> None:
        """Just updates the style key. No generation happens until draw time.

        Logic: Creates the StyleKey based on current colors."""
        self._current_key = StyleKey(
            bg=colors["bg"],
            border_color=colors["border"],
            shadow_color=colors["shadow"],
            parent_bg=colors["parent"],
            radius=self.radius,
            border_width=self.border_width,
            elevation=self.elevation,
        )

    def draw_on_canvas(
        self,
        canvas: tk.Canvas,
        width: int,
        height: int,
        tag_prefix: str = "ns",
        x: int = 0,
        y: int = 0,
    ) -> None:
        """
        Logic: Draws or updates the 9-slice images (corners, edges,
        center) on the target canvas."""
        if not self._current_key or width <= 1 or height <= 1:
            return
        key = self._current_key
        w_int, h_int = (int(width), int(height))
        tags = {
            k: f"{tag_prefix}_{k}"
            for k in ["c", "tl", "tr", "bl", "br", "t", "b", "l", "r"]
        }
        if (
            self._last_width == w_int
            and self._last_height == h_int
            and (self._last_key == key)
            and (self._last_x == x)
            and (self._last_y == y)
            and all((canvas.find_withtag(tag) for tag in tags.values()))
        ):
            return
        self._last_width = w_int
        self._last_height = h_int
        self._last_key = key
        self._last_x = x
        self._last_y = y
        corners = TextureAtlas.get_corners(key)
        cut_view = corners["tl"].width()
        mid_w = max(0, w_int - 2 * cut_view)
        mid_h = max(0, h_int - 2 * cut_view)
        h_edges = (
            TextureAtlas.get_horizontal_edges(key, mid_w) if mid_w > 0 else {}
        )
        v_edges = (
            TextureAtlas.get_vertical_edges(key, mid_h) if mid_h > 0 else {}
        )
        self._current_images_ref = [corners, h_edges, v_edges]
        if not canvas.find_withtag(tags["c"]):
            canvas.create_rectangle(
                x + cut_view - 1,
                y + cut_view - 1,
                x + w_int - cut_view + 1,
                y + h_int - cut_view + 1,
                fill=key.bg,
                width=0,
                tags=tags["c"],
            )
            canvas.create_image(
                x, y, image=corners["tl"], anchor="nw", tags=tags["tl"]
            )
            canvas.create_image(
                x + w_int, y, image=corners["tr"], anchor="ne", tags=tags["tr"]
            )
            canvas.create_image(
                x, y + h_int, image=corners["bl"], anchor="sw", tags=tags["bl"]
            )
            canvas.create_image(
                x + w_int,
                y + h_int,
                image=corners["br"],
                anchor="se",
                tags=tags["br"],
            )
            if "t" in h_edges:
                canvas.create_image(
                    x + cut_view,
                    y,
                    image=h_edges["t"],
                    anchor="nw",
                    tags=tags["t"],
                )
            if "b" in h_edges:
                canvas.create_image(
                    x + cut_view,
                    y + h_int,
                    image=h_edges["b"],
                    anchor="sw",
                    tags=tags["b"],
                )
            if "l" in v_edges:
                canvas.create_image(
                    x,
                    y + cut_view,
                    image=v_edges["l"],
                    anchor="nw",
                    tags=tags["l"],
                )
            if "r" in v_edges:
                canvas.create_image(
                    x + w_int,
                    y + cut_view,
                    image=v_edges["r"],
                    anchor="ne",
                    tags=tags["r"],
                )
            for t in tags.values():
                canvas.tag_lower(t)
        else:
            canvas.coords(
                tags["c"],
                x + cut_view - 1,
                y + cut_view - 1,
                x + w_int - cut_view + 1,
                y + h_int - cut_view + 1,
            )
            canvas.itemconfigure(tags["c"], fill=key.bg)
            canvas.coords(tags["tl"], x, y)
            canvas.itemconfigure(tags["tl"], image=corners["tl"])
            canvas.coords(tags["tr"], x + w_int, y)
            canvas.itemconfigure(tags["tr"], image=corners["tr"])
            canvas.coords(tags["bl"], x, y + h_int)
            canvas.itemconfigure(tags["bl"], image=corners["bl"])
            canvas.coords(tags["br"], x + w_int, y + h_int)
            canvas.itemconfigure(tags["br"], image=corners["br"])
            self._update_edge(
                canvas, tags["t"], h_edges.get("t"), x + cut_view, y, "nw"
            )
            self._update_edge(
                canvas,
                tags["b"],
                h_edges.get("b"),
                x + cut_view,
                y + h_int,
                "sw",
            )
            self._update_edge(
                canvas, tags["l"], v_edges.get("l"), x, y + cut_view, "nw"
            )
            self._update_edge(
                canvas,
                tags["r"],
                v_edges.get("r"),
                x + w_int,
                y + cut_view,
                "ne",
            )

    def _update_edge(
        self,
        canvas: tk.Canvas,
        tag: str,
        image: Optional[ImageTk.PhotoImage],
        x: int,
        y: int,
        anchor: str,
    ) -> None:
        """Helper to safely update/create/hide edges.

        Logic: Updates canvas image item or creates it if missing."""
        if image:
            if canvas.find_withtag(tag):
                canvas.coords(tag, x, y)
                canvas.itemconfigure(tag, image=image, state="normal")
            else:
                canvas.create_image(x, y, image=image, anchor=anchor, tags=tag)
                canvas.tag_lower(tag)
        elif canvas.find_withtag(tag):
            canvas.delete(tag)


class AtlasDebugger:
    """
    Utility to inspect the Texture Atlas cache health.
    """

    @staticmethod
    def print_stats() -> None:
        """Prints Cache Hits, Misses, and Usage.

        Logic: Prints cache statistics for debugging."""
        print("\n=== TEXTURE ATLAS HEALTH REPORT ===")
        src_stats = _AssetFactory.generate_source_assets.cache_info()
        print("[CPU] Source Generation:")
        print(f"  - Hits:   {src_stats.hits} (Reused source)")
        print(f"  - Misses: {src_stats.misses} (Generated from scratch)")
        print(f"  - Size:   {src_stats.currsize}/{src_stats.maxsize}")
        h_stats = TextureAtlas.get_horizontal_edges.cache_info()
        v_stats = TextureAtlas.get_vertical_edges.cache_info()
        c_stats = TextureAtlas.get_corners.cache_info()
        print("[TK] Texture Caches (Active IDs):")
        print(
            f"  - Horiz Edges: {h_stats.currsize}/{h_stats.maxsize}"
            f" (Hits: {h_stats.hits}, Misses: {h_stats.misses})"
        )
        print(
            f"  - Vert Edges:  {v_stats.currsize}/{v_stats.maxsize}"
            f" (Hits: {v_stats.hits}, Misses: {v_stats.misses})"
        )
        print(
            f"  - Corners:     {c_stats.currsize}/{c_stats.maxsize}"
            f" (Hits: {c_stats.hits}, Misses: {c_stats.misses})"
        )
        print("===================================\n")

    @staticmethod
    def benchmark_render(widget_name: str, render_func: Any) -> None:
        """Wrapper to measure how long a render takes.

        Logic: Times a render function execution."""
        import time

        start = time.perf_counter()
        render_func()
        end = time.perf_counter()
        ms = (end - start) * 1000
        if ms > 16:
            print(f"[WARNING] Slow Render on {widget_name}: {ms:.2f}ms")
