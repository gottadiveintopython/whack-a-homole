from collections.abc import Mapping
from contextlib import ExitStack
from functools import partial, cache
import itertools

from kivy.properties import (
    NumericProperty, BoundedNumericProperty, ObjectProperty, ColorProperty,
)
from kivy.lang import Builder
from kivy.graphics.texture import Texture
from kivy.graphics import InstructionGroup
from kivy._event import EventDispatcher
from kivy.core.audio_output import Sound
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
import asynckivy as ak
from asynckivy import transition, anim_attrs_abbr as anim_attrs


from whack_a_homole import SharedObjects, uix
from whack_a_homole.utils import is_colliding_and_not_wheel, show_fading_image


Builder.load_string("""
<Hole>:
    canvas.before:
        Color:
            # The Ellipse instruction has a bug where setting its size to (0, 0) can sometimes leave a visible artifact.
            # As a workaround, I set its color to fully transparent when the scale is 0.
            rgba: self.color if self.scale else (0, 0, 0, 0)
        Ellipse:
            size:
                (
                s := self.scale,
                ) and (self.width * s, self.height * s)
            pos:
                (
                s := (1. - self.scale) / 2.,
                ) and (self.x + self.width * s, self.y + self.height * s)

<PartiallyRevealableImage>:
    texture_aspect_ratio: (t := self.texture, ) and (0. if t is None else t.height / t.width)
    size_hint_y: None
    height: self.width * self.texture_aspect_ratio * self.reveal_ratio
    pos_hint: {"center_x": .5, "y": .5, }
    canvas:
        Color:
        Rectangle:
            size: self.size
            pos: self.pos
            texture: self.texture
            tex_coords: (r := self.reveal_ratio, ) and (0., r, 1., r, 1., 0., 0., 0.)
""")


class Hole(FloatLayout):
    color = ColorProperty("#333333FF")
    scale = NumericProperty(0.)


class PartiallyRevealableImage(Widget):
    texture = ObjectProperty(None, allownone=True)

    texture_aspect_ratio = NumericProperty(0.)
    '''
    (read-only)
    Texture height / width ratio. 0.0 if the texture is None.
    '''

    reveal_ratio = BoundedNumericProperty(1.0, min=0.0, max=1.0)
    '''
    The ratio of the revealed area of the texture.

    * 0.0 ... None of the texture is visible.
    * 0.5 ... Only the upper half of the texture is visible.
    * 1.0 ... The whole texture is visible.
    '''


class GameState(EventDispatcher):
    available_holes: list[Hole] = ObjectProperty()
    score: int = NumericProperty()


async def spawn_enemy_from(
    hole: Hole,
    *,
    game_state: GameState,
    speed=1.0,
    enemy_relative_width=0.7,
    # displays_hurt_box=False,
    # hurt_box_color=(1, 0, 0, 1),
    images: Mapping[str, Texture],
    image_relative_widths: Mapping[str, float],
    sounds: Mapping[str, Sound],
    _image_cache: list[PartiallyRevealableImage]=[],
):
    """
    :param hole: The hole where an enemy spawns.

    :param speed:
        A speed coefficient for the enemy's movement.
        A larger value makes the enemy move faster.

    :enemy_relative_width:
        The base width of the enemy image relative to the width of the hole.

    :param on_hit: Called when the player hits the enemy.
    :param on_hurt: Called when the enemy hits the player.
    """
    dcoeff = 1. / speed  # duration coefficient
    try:
        await anim_attrs(hole, scale=1., d=.5 * dcoeff)

        with ExitStack() as stack:
            defer = stack.callback

            actor = _image_cache.pop() if _image_cache else PartiallyRevealableImage()
            defer(_image_cache.append, actor)
            actor.texture = images["neutral"]
            actor.size_hint_x = enemy_relative_width
            actor.opacity = 1.
            actor.reveal_ratio = 0.
            hole.add_widget(actor)
            defer(hole.remove_widget, actor)

            await anim_attrs(actor, reveal_ratio=1.0, d=.5 * dcoeff)

            async with ak.move_on_when(
                ak.event(actor, "on_touch_down", filter=is_colliding_and_not_wheel)
            ) as hit_tracker:
                await ak.sleep(dcoeff)
                actor.texture = images["square-off"]
                actor.size_hint_x = enemy_relative_width * image_relative_widths["square-off"]
                await ak.sleep(dcoeff)
            if hit_tracker.finished:
                sounds["hit"].play()
                game_state.score += 1
                defer(ak.start(show_score_delta_on_actor(images["+1"], actor)).cancel)
                await anim_attrs(actor, opacity=0., d=.5)
            else:
                actor.texture = images["attack"]
                actor.size_hint_x = enemy_relative_width * image_relative_widths["attack"]
                sounds["hurt"].play()
                game_state.score -= 1
                defer(ak.start(show_score_delta_on_actor(images["-1"], actor)).cancel)
                await ak.sleep(dcoeff)
                await anim_attrs(actor, reveal_ratio=0., d=.5 * dcoeff)

            await anim_attrs(hole, scale=0., d=.5 * dcoeff)
    finally:
        hole.scale = 0.
        game_state.available_holes.append(hole)


def build_a_grid_of_holes(
    *, n_rows=3, n_cols=5, row_spacing="40dp", col_spacing="30dp", relative_row_width=0.9,
    _get_row_pos_hint = itertools.cycle([{"x": 0.}, {"right": 1.}]).__next__,
) -> BoxLayout:
    root = BoxLayout(
        pos_hint={"x": 0, "y": 0, },
        orientation="vertical",
        spacing=row_spacing,
    )
    for i in range(n_rows):
        row = BoxLayout(
            spacing=col_spacing,
            size_hint_x=relative_row_width,
            pos_hint=_get_row_pos_hint().copy(),
        )
        root.add_widget(row)
        for __ in range(n_cols):
            row.add_widget(Hole())
    return root


KV = """
FloatLayout:
    pos_hint: {"x": 0, "y": 0, }
    AspectRatio:
        size_hint: .96, .92
        pos_hint: {"center_x": .5, "center_y": .5, }
        child_aspect_ratio: 4 / 3
        halign: "center"
        valign: "bottom"
        AspectRatio:
            id: grid_container
            child_aspect_ratio: 8 / 3
            halign: "center"
            valign: "bottom"
"""

async def main(parent: FloatLayout, userdata: SharedObjects, *, _cache=[]):
    from random import choice, random

    s_data, s_states = userdata

    with ExitStack() as stack:
        defer = stack.callback

        if _cache:
            root = _cache.pop()
        else:
            root = Builder.load_string(KV)
            root.ids.grid_container.add_widget(build_a_grid_of_holes())
        defer(_cache.append, root)
        parent.add_widget(root)
        defer(parent.remove_widget, root)

        grid = root.ids.grid_container.children[0]
        available_holes = [hole for row in grid.children for hole in row.children]
        game_state = GameState(available_holes=available_holes, score=0)
        spawn_enemy_from_ = partial(spawn_enemy_from, game_state=game_state, **s_data.asdict())

        yield

        async with ak.open_nursery() as nursery:
            while True:
                await ak.sleep(2. * random())
                if not available_holes:
                    continue
                hole = choice(available_holes)
                available_holes.remove(hole)
                nursery.start(spawn_enemy_from_(hole))

        yield "whack_a_homole.scenes.title.main", transition.fade


def show_score_delta_on_actor(score_image: Texture, actor: PartiallyRevealableImage):
    w, h = score_image.size
    return show_fading_image(
        score_image, draw_target=actor.canvas.after,
        pos=(actor.center_x - w * 0.5, actor.top - h),
        # size=score_image.size,
    )
