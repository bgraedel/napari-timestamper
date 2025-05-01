from __future__ import annotations

from typing import Literal, Union

import numpy as np
from vispy.color import Color
from vispy.scene.visuals import Compound, Line, Markers, Mesh, Text


class MultiRectVisual(Mesh):
    def __init__(
        self,
        x: list,
        y: list,
        w: list,
        h: list,
        color: Union[list, str] = "white",
        anchor_x="center",
        anchor_y="center",
        **kwargs,
    ):
        # convert color to list if it is a single color
        if isinstance(color, str):
            color = [color]
        # padd shape to match length
        max_len = max(len(x), len(y), len(w), len(h), len(color))
        # raise if any of the lists are too short
        if (
            len(x) < max_len
            or len(y) < max_len
            or len(w) < max_len
            or len(h) < max_len
        ):
            raise ValueError("x, y, w and h must all be the same length")
        color.extend(color[:1] * (max_len - len(color)))
        self._check_valid("anchor_x", anchor_x, ("left", "center", "right"))
        self._check_valid(
            "anchor_y",
            anchor_y,
            ("top", "center", "middle", "baseline", "bottom"),
        )

        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        self.spacer = 10

        self.rect_data = list(zip(x, y, w, h, color))
        vertices, faces, colors = self._generate_vertices_faces_and_colors()
        super().__init__(
            vertices=vertices, faces=faces, vertex_colors=colors, **kwargs
        )

    def _generate_vertices_faces_and_colors(self):
        vertices = []
        faces = []
        colors = []
        face_index = 0

        for rect in self.rect_data:
            x, y, w, h, color_name = rect
            # Adjust x and y based on anchor
            x_offset, y_offset = self._calculate_anchor_offset(w, h)
            rect_vertices = np.array(
                [
                    [x - x_offset, y - y_offset],
                    [x - x_offset + w, y - y_offset],
                    [x - x_offset + w, y - y_offset + h],
                    [x - x_offset, y - y_offset + h],
                ]
            )
            vertices.extend(rect_vertices)

            rect_faces = np.array(
                [
                    [face_index, face_index + 1, face_index + 2],
                    [face_index, face_index + 2, face_index + 3],
                ]
            )
            faces.extend(rect_faces)
            face_index += 4

            color = Color(color_name).rgba
            colors.extend([color] * 4)

        return np.array(vertices), np.array(faces), np.array(colors)

    def _calculate_anchor_offset(self, width, height):
        dx = dy = 0

        # Calculate the horizontal offset
        if self.anchor_x == "right":
            dx = +width - self.spacer
        elif self.anchor_x == "center":
            dx = +width / 2
        elif self.anchor_x == "left":
            dx = self.spacer

        # Calculate the vertical offset
        if self.anchor_y in ("top"):
            dy = +height
        elif self.anchor_y in ("center", "middle"):
            dy = +height / 2
        elif self.anchor_y in ("baseline", "bottom"):
            dy = 0

        return dx, dy

    def _check_valid(self, name, value, valid_values):
        if value not in valid_values:
            raise ValueError(
                f"{name} must be one of {valid_values}, but got {value}"
            )

    def update_rects(
        self, x: list, y: list, w: list, h: list, color: Union[list, str]
    ):
        # convert color to list if it is a single color
        if isinstance(color, str):
            color = [color]
        # padd shape to match length
        max_len = max(len(x), len(y), len(w), len(h), len(color))
        # raise if any of the lists are too short
        if (
            len(x) < max_len
            or len(y) < max_len
            or len(w) < max_len
            or len(h) < max_len
        ):
            raise ValueError("x, y, w and h must all be the same length")
        color.extend(color[:1] * (max_len - len(color)))
        self.rect_data = list(zip(x, y, w, h, color))
        vertices, faces, colors = self._generate_vertices_faces_and_colors()
        self.set_data(vertices=vertices, faces=faces, vertex_colors=colors)

    @property
    def pos(self):
        return [(rect[0], rect[1]) for rect in self.rect_data]

    @pos.setter
    def pos(self, pos: Union[list[tuple], tuple]):
        # bring arguments to correct shape
        if isinstance(pos, tuple):
            pos_x = [pos[0]]
            pos_y = [pos[1]]
        else:
            pos_x = [p[0] for p in pos]
            pos_y = [p[1] for p in pos]
        self.update_rects(pos_x, pos_y, self.w, self.h, self.color)

    @property
    def x(self):
        return [rect[0] for rect in self.rect_data]

    @x.setter
    def x(self, x: list):
        # check if x is a single value
        if isinstance(x, (int, float)):
            x = [x] * len(self.rect_data)
        self.update_rects(x, self.y, self.w, self.h, self.color)

    @property
    def y(self):
        return [rect[1] for rect in self.rect_data]

    @y.setter
    def y(self, y: list):
        # check if y is a single value
        if isinstance(y, (int, float)):
            y = [y] * len(self.rect_data)
        self.update_rects(self.x, y, self.w, self.h, self.color)

    @property
    def w(self):
        return [rect[2] for rect in self.rect_data]

    @w.setter
    def w(self, w: list):
        # check if w is a single value
        if isinstance(w, (int, float)):
            w = [w] * len(self.rect_data)
        self.update_rects(self.x, self.y, w, self.h, self.color)

    @property
    def h(self):
        return [rect[3] for rect in self.rect_data]

    @h.setter
    def h(self, h: list):
        # check if h is a single value
        if isinstance(h, (int, float)):
            h = [h] * len(self.rect_data)
        self.update_rects(self.x, self.y, self.w, h, self.color)

    @property
    def color(self):
        return [rect[4] for rect in self.rect_data]

    @color.setter
    def color(self, color: Union[list, str]):
        self.update_rects(self.x, self.y, self.w, self.h, color)

    @property
    def anchors(self):
        return self.anchor_x, self.anchor_y

    @anchors.setter
    def anchors(self, anchors: tuple):
        self.anchor_x, self.anchor_y = anchors
        self.update_rects(self.x, self.y, self.w, self.h, self.color)


class TextWithBoxVisual(Compound):
    RECTANGLE_SCALER = 2

    def __init__(
        self,
        text: Union[list[str], str],
        color: Union[list[str], str] = "white",
        bgcolor: str = "red",
        outline_color: str = "white",
        outline_width: float = 1.0,
        font_size: int = 12,
        pos: Union[list[tuple], tuple] = (0, 0),
        anchor_x: str = "left",
        anchor_y: str = "bottom",
        bold=False,
        italic=False,
        **kwargs,
    ):
        self._textvisual = Text(
            text=text,
            pos=pos,
            color=color,
            font_size=font_size,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            bold=bold,
            italic=italic,
        )
        # bring arguments to correct shape
        if isinstance(pos, tuple):
            pos_x = [pos[0]]
            pos_y = [pos[1]]
        else:
            pos_x = [p[0] for p in pos]
            pos_y = [p[1] for p in pos]

        self._rectagles_visual = MultiRectVisual(
            x=pos_x,
            y=pos_y,
            w=[font_size * self.RECTANGLE_SCALER] * len(pos_x),
            h=[font_size * self.RECTANGLE_SCALER] * len(pos_y),
            color=bgcolor,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
        )

        self.scale_factor = 1
        self.rectangles_scale_factor = 1

        # Initialize the line visual for outlines
        self._outline_visual = Line(color=outline_color, width=outline_width)
        # Initialize markers to cover gaps
        self._corner_markers = Markers()
        self.update_outline()  # Call this method to initialize the outline

        super().__init__(
            [
                self._rectagles_visual,
                self._textvisual,
                self._outline_visual,
                self._corner_markers,
            ]
        )

    def update_outline(
        self,
        hide_partial_outline: (
            list[Literal["left", "right", "top", "bottom"]]
            | list[list[Literal["left", "right", "top", "bottom"]]]
            | None
        ) = None,
    ):
        z = 0
        vertices = []
        edges = []
        corner_positions = []
        half_outline_thickness = (
            self._outline_visual.width / self.scale_factor / 2
        )
        vertex_count = 0

        n_rects = len(self._rectagles_visual.x)

        if not hide_partial_outline:
            hide_partial_outline = [[] for _ in range(n_rects)]
        elif isinstance(hide_partial_outline[0], str):
            hide_partial_outline = [hide_partial_outline] * n_rects
        elif len(hide_partial_outline) != n_rects:
            raise ValueError(
                "Length of hide_partial_outline must match number of rectangles"
            )

        for i, (x, y, w, h) in enumerate(
            zip(
                self._rectagles_visual.x,
                self._rectagles_visual.y,
                self._rectagles_visual.w,
                self._rectagles_visual.h,
            )
        ):
            (
                x_offset,
                y_offset,
            ) = self._rectagles_visual._calculate_anchor_offset(w, h)

            rect_verts = [
                [
                    x - x_offset + half_outline_thickness,
                    y - y_offset + half_outline_thickness,
                    z,
                ],  # 0: bottom-left
                [
                    x - x_offset + w - half_outline_thickness,
                    y - y_offset + half_outline_thickness,
                    z,
                ],  # 1: bottom-right
                [
                    x - x_offset + w - half_outline_thickness,
                    y - y_offset + h - half_outline_thickness,
                    z,
                ],  # 2: top-right
                [
                    x - x_offset + half_outline_thickness,
                    y - y_offset + h - half_outline_thickness,
                    z,
                ],  # 3: top-left
            ]
            vertices.extend(rect_verts)

            hide_sides = hide_partial_outline[i]
            if hide_sides is None:
                hide_sides = []
            if isinstance(hide_sides, str):
                hide_sides = [hide_sides]
            hide_sides = [side.lower() for side in hide_sides]

            # Define edges if not hidden
            if "bottom" not in hide_sides:
                edges.append([vertex_count + 0, vertex_count + 1])
            if "right" not in hide_sides:
                edges.append([vertex_count + 1, vertex_count + 2])
            if "top" not in hide_sides:
                edges.append([vertex_count + 2, vertex_count + 3])
            if "left" not in hide_sides:
                edges.append([vertex_count + 3, vertex_count + 0])

            # Only show corner markers if either connecting edge is present
            show_corner = [
                "left" not in hide_sides
                or "bottom" not in hide_sides,  # bottom-left
                "bottom" not in hide_sides
                or "right" not in hide_sides,  # bottom-right
                "right" not in hide_sides
                or "top" not in hide_sides,  # top-right
                "top" not in hide_sides
                or "left" not in hide_sides,  # top-left
            ]

            for j in range(4):
                if show_corner[j]:
                    corner_positions.append(rect_verts[j])

            vertex_count += 4

        self._outline_visual.set_data(
            pos=np.array(vertices),
            connect=np.array(edges),
            color=self._outline_visual.color,
            width=self._outline_visual.width,
        )

        self._corner_markers.set_data(
            pos=np.array(corner_positions),
            face_color=self._outline_visual.color,
            edge_color=self._outline_visual.color,
            edge_width=0.75 * self.rectangles_scale_factor,
            size=self._outline_visual.width,
            symbol="square",
        )

    @property
    def color(self):
        return self._textvisual.color

    @color.setter
    def color(self, color: str):
        self._textvisual.color = color

    @property
    def bgcolor(self):
        return self._rectagles_visual.color

    @bgcolor.setter
    def bgcolor(self, color: str):
        self._rectagles_visual.color = color

    @property
    def font_size(self):
        return self._textvisual.font_size

    @font_size.setter
    def font_size(self, size: int):
        self._textvisual.font_size = size * self.scale_factor
        self._rectagles_visual.h = size * self.rectangles_scale_factor

    @property
    def pos(self):
        return self._textvisual.pos, self._rectagles_visual.pos

    @pos.setter
    def pos(self, pos: Union[list[tuple], tuple]):
        self._textvisual.pos = pos
        self._rectagles_visual.pos = pos

    @property
    def text(self):
        return self._textvisual.text

    @text.setter
    def text(self, text: Union[list[str], str]):
        self._textvisual.text = text

    @property
    def anchors(self):
        return self._textvisual.anchors

    @anchors.setter
    def anchors(self, anchors: tuple):
        self._textvisual.anchors = anchors
        self._rectagles_visual.anchors = anchors

    @property
    def bold(self):
        return self._textvisual.bold

    @bold.setter
    def bold(self, bold: bool):
        self._textvisual.bold = bold

    @property
    def italic(self):
        return self._textvisual.italic

    @italic.setter
    def italic(self, italic: bool):
        self._textvisual.italic = italic

    @property
    def layer_widths(self):
        return self._rectagles_visual.w

    @layer_widths.setter
    def layer_widths(self, coords: list):
        w = [coord[0] for coord in coords]
        self._rectagles_visual.w = w
        self.update_outline()

    @property
    def show_background(self):
        return self._rectagles_visual.visible

    @show_background.setter
    def show_background(self, show: bool):
        self._rectagles_visual.visible = show

    @property
    def outline_color(self):
        return self._outline_visual.color

    @outline_color.setter
    def outline_color(self, color: str):
        self._outline_visual.set_data(color=color)

    @property
    def outline_thickness(self):
        return self._outline_visual.width

    @outline_thickness.setter
    def outline_thickness(self, width: float):
        width = width * self.scale_factor
        self._outline_visual.set_data(width=width)
        self.update_outline()

    @property
    def show_outline(self):
        return self._outline_visual.visible

    @show_outline.setter
    def show_outline(self, show: bool):
        self._outline_visual.visible = show
        self._corner_markers.visible = show

    def update_data(
        self,
        text: Union[list[str], str],
        color: Union[list[str], str] = "white",
        bgcolor: str = "red",
        font_size: int = 12,
        pos: Union[list[tuple], tuple] = (0, 0),
        box_width: Union[list[float], float] = 0,
        hide_parial_outline: list[
            Literal["left", "right", "top", "bottom"]
        ] = None,
    ):
        # bring arguments to correct shape
        if isinstance(pos, tuple):
            pos_x = [pos[0]]
            pos_y = [pos[1]]
        else:
            pos_x = [p[0] for p in pos]
            pos_y = [p[1] for p in pos]

        # shift text_pos by 0.5 * font_size * self.scale_factor
        # to center the text in the box
        text_pos = [
            (
                pos_x[i],
                pos_y[i] + 0.35 * font_size * self.rectangles_scale_factor,
            )
            for i in range(len(pos_x))
        ]

        self.text = text
        self.color = color
        self.font_size = font_size
        self._textvisual.pos = text_pos
        height = [
            font_size * self.RECTANGLE_SCALER * self.rectangles_scale_factor
        ] * len(pos_y)

        self._rectagles_visual.update_rects(
            pos_x, pos_y, box_width, height, bgcolor
        )
        self.update_outline(hide_parial_outline)
