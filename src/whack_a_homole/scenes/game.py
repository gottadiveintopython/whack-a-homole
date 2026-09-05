from collections.abc import Mapping
from contextlib import ExitStack
from functools import partial
import itertools

from kivy.properties import (
    NumericProperty, BoundedNumericProperty, ObjectProperty, ColorProperty
)
from kivy.lang import Builder
from kivy.graphics import Rectangle, Color
from kivy.graphics.texture import Texture
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
            size: (s := self.scale, ) and (self.width * s, self.height * s)
            pos: (s := (1. - self.scale) / 2., ) and (self.x + self.width * s, self.y + self.height * s)

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

<CircularTimer>:
    canvas:
        Color:
            rgba: self.color if self.remaining_time else (0, 0, 0, 0)
        Ellipse:
            size: self.size
            pos: self.pos
            angle_start: 360. * (1. - self.remaining_time / self.total_time)
            angle_end: 360.

<GameScreen>:
    pos_hint: {"x": 0, "y": 0, }
    orientation: "vertical"
    padding: "10dp"
    BoxLayout:
        spacing: "10dp"
        size_hint_y: None
        height: self.minimum_height
        Label:
            id: score_label
            size_hint_min: self.texture_size
            pos_hint: {"center_y": .5, }
            font_size: "30sp"
            color: rgba("#8470ff")
        CircularTimer:
            id: timer
            size_hint: None, None
            size: dp(100), dp(100)
            pos_hint: {"center_y": .5, }
    AspectRatio:
        child_aspect_ratio: 4 / 3
        halign: "center"
        valign: "bottom"
        AspectRatio:
            id: grid_container
            child_aspect_ratio: 8 / 3
            halign: "center"
            valign: "bottom"
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


class CircularTimer(Widget):
    total_time = NumericProperty(1.0)
    remaining_time = NumericProperty()
    color = ColorProperty("#FFFFFFFF")


class GameScreen(BoxLayout):
    pass


class SessionState(EventDispatcher):
    score = NumericProperty()

    def __init__(self, *, available_holes, displays_hit_boxes=False, **kwargs):
        super().__init__(**kwargs)
        self.speed = 1.0
        self.displays_hit_boxes = displays_hit_boxes
        self.available_holes = available_holes


async def spawn_enemy_from(
    hole: Hole,
    *,
    root: GameScreen,
    state: SessionState,
    enemy_relative_width=0.7,
    images: Mapping[str, Texture],
    image_relative_widths: Mapping[str, float],
    sounds: Mapping[str, Sound],
    _image_cache: list[PartiallyRevealableImage]=[],
):
    """
    :param hole: The hole where an enemy spawns.

    :enemy_relative_width:
        The base width of the enemy image relative to the width of the hole.
    """
    dcoeff = 1. / state.speed  # duration coefficient
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
                ak.event(actor, "on_touch_down", filter=is_colliding_and_not_wheel, stop_dispatching=True)
            ) as hit_tracker:
                await ak.sleep(dcoeff)
                actor.texture = images["square-off"]
                actor.size_hint_x = enemy_relative_width * image_relative_widths["square-off"]
                await ak.sleep(dcoeff)
            if hit_tracker.finished:
                sounds["hit"].play()
                state.score += 1
                defer(ak.start(show_score_delta_on_actor(images["+1"], actor)).cancel)
                await anim_attrs(actor, opacity=0., d=.5)
            else:
                actor.texture = images["attack"]
                actor.size_hint_x = enemy_relative_width * image_relative_widths["attack"]
                await ak.sleep(0)
                sounds["hurt"].play()
                state.score -= 1
                defer(ak.start(show_score_delta_on_actor(images["-1"], actor)).cancel)
                defer(ak.start(play_hurt_effect_on(root)).cancel)
                await ak.sleep(dcoeff)
                await anim_attrs(actor, reveal_ratio=0., d=.5 * dcoeff)

            await anim_attrs(hole, scale=0., d=.5 * dcoeff)
    finally:
        hole.scale = 0.
        state.available_holes.append(hole)


async def spawn_ally_from(
    hole: Hole,
    *,
    state: SessionState,
    ally_relative_width=0.7,
    images: Mapping[str, Texture],
    image_relative_widths: Mapping[str, float],
    sounds: Mapping[str, Sound],
    _image_cache: list[PartiallyRevealableImage]=[],
):
    """
    :param hole: The hole where an ally spawns.

    :ally_relative_width:
        The base width of the ally image relative to the width of the hole.
    """
    dcoeff = 1. / state.speed  # duration coefficient
    try:
        await anim_attrs(hole, scale=1., d=.5 * dcoeff)

        with ExitStack() as stack:
            defer = stack.callback

            actor = _image_cache.pop() if _image_cache else PartiallyRevealableImage()
            defer(_image_cache.append, actor)
            actor.texture = images["neutral"]
            actor.size_hint_x = ally_relative_width
            actor.opacity = 1.
            actor.reveal_ratio = 0.
            hole.add_widget(actor)
            defer(hole.remove_widget, actor)

            await anim_attrs(actor, reveal_ratio=1.0, d=.5 * dcoeff)

            async with ak.move_on_when(
                ak.event(actor, "on_touch_down", filter=is_colliding_and_not_wheel, stop_dispatching=True)
            ) as hit_tracker:
                await ak.sleep(dcoeff)
                actor.texture = images["deliver"]
                actor.size_hint_x = ally_relative_width * image_relative_widths["deliver"]
                await ak.sleep(dcoeff)
            if hit_tracker.finished:
                sounds["hit"].play()
            else:
                actor.texture = images["gift"]
                actor.size_hint_x = ally_relative_width * image_relative_widths["gift"]
                sounds["gift"].play()
                state.score += 3
                await ak.sleep(0)
                defer(ak.start(show_score_delta_above_actor(images["+3"], actor)).cancel)
                await ak.sleep(dcoeff)
            await anim_attrs(actor, opacity=0., d=.5)
            await anim_attrs(hole, scale=0., d=.5 * dcoeff)
    finally:
        hole.scale = 0.
        state.available_holes.append(hole)


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


async def main(parent: FloatLayout, userdata: SharedObjects, *, _cache=[]):
    from random import choice, random, choices

    s_data, s_states = userdata

    with ExitStack() as stack:
        defer = stack.callback

        if _cache:
            root = _cache.pop()
        else:
            root = GameScreen()
            grid = build_a_grid_of_holes()
            root.ids.grid_container.add_widget(grid)
            root.holes = tuple(hole for row in grid.children for hole in row.children)
        defer(_cache.append, root)
        parent.add_widget(root)
        defer(parent.remove_widget, root)

        available_holes = list(root.holes)
        state = SessionState(
            score=0,
            available_holes=available_holes,
            displays_hit_boxes=s_states.displays_hit_boxes,
        )
        timer = root.ids.timer
        timer.total_time = timer.remaining_time = s_states.game_duration

        spawn_funcs = (
            partial(spawn_enemy_from, state=state, root=root, **s_data.asdict()),
            partial(spawn_ally_from, state=state, **s_data.asdict()),
        )
        r = s_states.enemy_to_ally_ratio
        cum_weights = (r[0], r[0] + r[1])
        del r

        yield

        async with ak.open_nursery() as nursery:
            nursery.start(anim_attrs(timer, remaining_time=0., d=timer.total_time), close_on_finish=True)
            while True:
                await ak.sleep(3. * random() / state.speed)
                if not available_holes:
                    continue
                hole = choice(available_holes)
                available_holes.remove(hole)
                nursery.start(choices(spawn_funcs, cum_weights=cum_weights)[0](hole))

        yield "whack_a_homole.scenes.title.main", transition.fade


def show_score_delta_on_actor(score_image: Texture, actor: PartiallyRevealableImage):
    hole = actor.parent
    scale = hole.width / 160.
    dw = score_image.width * scale  # display width
    dh = score_image.height * scale  # display height
    return show_fading_image(
        score_image, draw_target=actor.canvas,
        pos=(actor.center_x - dw * 0.5, actor.top - dh),
        size=(dw, dh),
    )


def show_score_delta_above_actor(score_image: Texture, actor: PartiallyRevealableImage):
    hole = actor.parent
    scale = hole.width / 160.
    dw = score_image.width * scale  # display width
    dh = score_image.height * scale  # display height
    return show_fading_image(
        score_image, draw_target=actor.canvas,
        pos=(actor.center_x - dw * 0.5, actor.top),
        size=(dw, dh),
    )


async def play_hurt_effect_on(root: GameScreen):
    draw_target = root.canvas.after
    with draw_target:
        color = Color(1, 0, 0, 0.3)
        rect = Rectangle(size=root.size, pos=root.pos)
    try:
        await anim_attrs(color, a=0., d=.5)
    finally:
        draw_target.remove(rect)
        draw_target.remove(color)
