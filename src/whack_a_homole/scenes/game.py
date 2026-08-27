from collections.abc import Sequence, Mapping, Callable, Iterable
from functools import partial
from contextlib import ExitStack, nullcontext

from kivy.graphics import (
    InstructionGroup, Color, Rectangle, CanvasBase, Ellipse,
    StencilPush, StencilUse, StencilUnUse, StencilPop,
)
from kivy._event import EventDispatcher
from kivy.properties import NumericProperty, ObjectProperty, ReferenceListProperty, BoundedNumericProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.audio_output import Sound
from kivy.uix.widget import Widget
import asynckivy as ak
from asynckivy import anim_attrs_abbr as anim_attrs

KV = r"""
<HomoleSlot>:
    canvas:
        Color:
        Rectangle:
            pos: self.pos
            size: self.size
            texture: self.texture
"""

async def spawn_enemy(
    *,
    draw_target: InstructionGroup,
    hole_pos: Sequence[float],
    hole_size: Sequence[float],
    hole_color=(0.2, 0.2, 0.2, 1),
    speed=1.0,
    displays_hurt_box=False,
    hurt_box_color=(1, 0, 0, 1),
    images: Mapping[str, Texture],
    sounds: Mapping[str, Sound],
    touch_listener: Widget=None,
    on_hit: Callable=None,
    on_get_hit: Callable=None,
):
    """
    :param hole_pos: bottom-left corner
    :param hole_size: width and height

    :param speed:
        A speed coefficient for the enemy's movement.
        A larger value makes the enemy move faster.

    :param touch_listener:
        A widget used to receive touch events.
        If None, the spawned enemy will not respond to touches.

    :param on_hit: Called when the player hits the enemy.
    :param on_get_hit: Called when the enemy hits the player.
    """
    speed = 1.0 / speed
    hole_x, hole_y = hole_pos
    hole_width, hole_height = hole_size
    hole_center_x = hole_x + hole_width / 2
    hole_center_y = hole_y + hole_height / 2
    hole_center = (hole_center_x, hole_center_y)
    calc_pos_and_size = partial(
        _calc_actor_pos_and_size,
        hole_center_x,
        hole_center_y,
        hole_width,
    )
    nullctx = nullcontext()

    draw_target.add(root_canvas := CanvasBase())
    try:
        # open a hole
        with root_canvas:
            Color(*hole_color)
            hole_ellipse = Ellipse(pos=hole_center, size=(0, 0))
        await anim_attrs(hole_ellipse, pos=hole_pos, size=hole_size, d=.5 * speed)

        # ---------------------------------------
        # enemy in action
        # ---------------------------------------
        root_canvas.add(enemy_canvas := CanvasBase())
        with enemy_canvas:
            StencilPush()
            visible_area = Rectangle(pos=(0, hole_center_y), size=(99999, 99999))
            StencilUse()
            enemy_color = Color()
            enemy_rect = Rectangle()
            StencilUnUse()
            enemy_canvas.add(visible_area)
            StencilPop()

        # spawn an enemy
        cur_img = images["neutral"]
        enemy_rect.texture = cur_img
        appearing_pos, enemy_size = calc_pos_and_size(cur_img)
        hiding_pos = (appearing_pos[0], appearing_pos[1] - enemy_size[1])
        enemy_rect.pos = hiding_pos
        enemy_rect.size = enemy_size
        await anim_attrs(enemy_rect, pos=appearing_pos, d=.5 * speed)

        async with ak.move_on_when(
            ak.sleep_forever() if touch_listener is None else
            ak.event(touch_listener, "on_touch_down", lambda w, t: "<enemy>".collide_point(*t.pos))
        ) as hit_tracker:
            await ak.sleep(speed)
            enemy_rect.texture = cur_img = images["square-off"]
            appearing_pos, enemy_size = calc_pos_and_size(cur_img)
            enemy_rect.pos = appearing_pos
            enemy_rect.size = enemy_size
            await ak.sleep(speed)

        if hit_tracker.finished:
            on_hit()  # 効果音, +1点
            await anim_attrs(enemy_color, a=0., d=.5)
        else:
            enemy_rect.texture = cur_img = images["attack"]
            appearing_pos, enemy_size = calc_pos_and_size(cur_img)
            hiding_pos = (appearing_pos[0], appearing_pos[1] - enemy_size[1])
            enemy_rect.pos = appearing_pos
            enemy_rect.size = enemy_size
            on_get_hit()  # 効果音, -1点, 紅の点滅
            await anim_attrs(enemy_rect, pos=hiding_pos, d=.5 * speed)
        root_canvas.remove(enemy_canvas)

        # close the hole
        await anim_attrs(hole_ellipse, pos=hole_center, size=(0, 0), d=.5 * speed)
    finally:
        draw_target.remove(root_canvas)


def _calc_actor_pos_and_size(
    hole_center_x, hole_center_y, hole_width, actor_img, actor_relative_width=0.9,
) -> tuple[tuple[float, float], tuple[float, float]]:
    actor_width = hole_width * actor_relative_width
    pos = (hole_center_x - actor_width / 2, hole_center_y)
    aspect_ratio = actor_img.height / actor_img.width
    size = (actor_width, actor_width * aspect_ratio)
    return pos, size


class HomoleSlot(Widget):
    actor_image: Texture = ObjectProperty(None, allownone=True)

    actor_relative_width = NumericProperty(0.9)
    '''
    The width of the actor image relative to the width of the widget.
    '''

    reveal_ratio = BoundedNumericProperty(1.0, min=0.0, max=1.0)
    '''
    The ratio of the revealed area of the actor image.

    * 0.0 ... None of the image is visible.
    * 0.5 ... Only the upper half of the image is visible.
    * 1.0 ... The whole image is visible.
    '''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color()
            self._rect_inst = Rectangle()

    def _update_revealed_area(self, dt):
        self._revealed_area.pos = (0, self.hole_center_y)

    def collide_point(self, x, y):
        if self.texture is None or self.reveal_ratio <= 0.:
            return False
        rx, ry = self._rect_inst.pos
        rw, rh = self._rect_inst.size
        return rx <= x < rx + rw and ry <= y < ry + rh


class Hole:
    r_x = NumericProperty()
    hole_center_y = NumericProperty()
    hole_center = ReferenceListProperty(hole_center_x, hole_center_y)
    hole_width = NumericProperty()


class RowOfHoles(Widget):
    '''
    A BoxLayout-like widget that lays out Holes horizontally.
    '''

    spacing = NumericProperty()
    child_width = NumericProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.holes: list[Hole] = []
        self._trigger_layout = t = Clock.create_trigger(self._do_layout, -1)
        self.bind(pos=t, size=t, spacing=t, child_width=t)

    def add_hole(self, hole: Hole):
        hole.parent = self
        self.holes.append(hole)
        self.canvas.add(hole.canvas)
        self._trigger_layout()

    def _do_layout(self, *args):
        x, y = self.pos
        hole_size = (self.child_width, self.height)
        stride = self.child_width + self.spacing
        for hole in self.holes:
            hole.pos = (x, y)
            hole.size = hole_size
            x += stride
