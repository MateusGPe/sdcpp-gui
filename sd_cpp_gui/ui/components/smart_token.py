from __future__ import annotations

from sd_cpp_gui.constants import SYSTEM_FONT
from sd_cpp_gui.ui.components.token_chip import TokenChip


class SmartTokenChip(TokenChip):
    """
    Extended TokenChip with variant-based coloring.
    """

    def __init__(
        self,
        parent,
        text,
        on_remove,
        color_manager,
        focus_callback,
        renderer,
        variant="default",
        font=(
            SYSTEM_FONT,
            8,
        ),
    ):
        self._variant = variant
        self._cm = color_manager
        super().__init__(
            parent,
            text,
            on_remove,
            color_manager,
            focus_callback,
            renderer,
            variant=variant,
            font=font,
        )

    def update_colors(self) -> None:
        """
        Refreshes chip visual state.
        """
        # Calculate the base variant color first
        target_bg = None

        if self._variant != "default":
            if self._variant == "number":
                target_bg = self._cm._resolve_color("success")
            elif self._variant == "bracket":
                target_bg = self._cm._resolve_color("warning")
            elif self._variant == "special":
                target_bg = self._cm._resolve_color("info")
            elif self._variant == "separator":
                target_bg = self._cm._resolve_color("danger")

        # Pass this "preferred" color to the base class.
        # The base class will then mix it with hover/selection states.
        super().update_color_palette(override_bg=target_bg)
        self._draw()

    def update_properties(self, text: str, variant: str) -> None:
        """
        Updates the chip text and variant without recreating it.
        """
        self._variant = variant
        # Use the public setter which handles redraw and width calculation
        self.set_text(text)
        self.update_colors()
