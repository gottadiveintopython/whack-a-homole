__all__ = (
    "is_colliding_and_not_wheel",
    "show_fading_image",
    "render_text_to_texture",
)

from contextlib import ExitStack

from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import get_markup_label_class
from kivy.graphics import InstructionGroup, Rectangle, Color
from kivy.graphics.texture import Texture
import asynckivy as ak


def render_text_to_texture(text, *, markup=False, provider=None, **other_options) -> Texture:
    if markup:
        core_cls = get_markup_label_class(provider)
    elif provider is None:
        core_cls = CoreLabel
    else:
        core_cls = CoreLabel.get_provider_class(provider)
    label = core_cls(text=text, **other_options)
    label.refresh()
    return label.texture


def is_colliding_and_not_wheel(widget, touch):
    return widget.collide_point(*touch.pos) and not touch.is_mouse_scrolling


async def show_fading_image(texture, *, draw_target: InstructionGroup, pos, size=None, duration=1.0):
    with ExitStack() as stack:
        defer = stack.callback

        draw_target.add(color := Color())
        defer(draw_target.remove, color)
        draw_target.add(rect := Rectangle(
            texture=texture, pos=pos, size=texture.size if size is None else size))
        defer(draw_target.remove, rect)
        await ak.anim_attrs(color, a=0., duration=duration, transition="in_quad")
