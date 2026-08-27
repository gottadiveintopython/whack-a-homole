__all__ = ("OutlinedButton", "ask_yes_no_question", )

from collections.abc import Awaitable
from typing import Literal
import itertools
from functools import partial

from kivy.properties import ColorProperty, NumericProperty
from kivy.graphics import Scale
from kivy.lang import Builder
from kivy.factory import Factory as F
from kivy.clock import Clock
from kivy.uix.label import Label

import asynckivy as ak
from asynckivy import modal


Builder.load_string("""
<OutlinedButton>:
    canvas.before:
        Color:
            group: "outline_color"
        Line:
            width: self.outline_width
            joint: 'miter'
            rounded_rectangle:
                (
                w := self.outline_width,
                w2x := w * 2,
                ) and (self.x + w, self.y + w, self.width - w2x, self.height - w2x, dp(20))

<YesNoDialog@BoxLayout>:
    padding: "20dp"
    spacing: "20dp"
    orientation: "vertical"
    size_hint: .5, .5
    size_hint_min: self.minimum_size
    pos_hint: {"center_x": .5, "center_y": .5}
    canvas.before:
        Color:
        Line:
            width: dp(2)
            rectangle: (*self.pos, *self.size, )
    Label:
        id: question
        size_hint_min: self.texture_size
    BoxLayout:
        spacing: "10dp"
        size_hint_min: self.minimum_size
        OutlinedButton:
            id: no_button
            size_hint_min: self.texture_size
        OutlinedButton:
            id: yes_button
            size_hint_min: self.texture_size
""")

def is_pos_colliding_and_not_wheel(w, t) -> bool:
    return w.collide_point(*t.pos) and (not t.is_mouse_scrolling)


class OutlinedButton(Label):
    __events__ = ("on_release", )
    outline_color1 = ColorProperty("#666666")
    outline_color2 = ColorProperty("#AAAA33")
    outline_width = NumericProperty("3dp")
    outline_blinking_interval = NumericProperty(.1)
    _props_that_trigger_reset = (
        "disabled", "parent", "outline_color1", "outline_color2", "outline_blinking_interval",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._main_task = ak.dummy_task
        f = self.fbind
        t = Clock.schedule_once(self._reset, -1)
        for prop in self._props_that_trigger_reset:
            f(prop, t)

    def _reset(self, dt):
        self._main_task.cancel()
        self._main_task = ak.managed_start(self._main())

    @staticmethod
    def _change_outline_color(color_inst, get_next_color, dt):
        color_inst.rgba = get_next_color()

    async def _main(self):
        import asynckivy as ak

        color_inst = self.canvas.before.get_group("outline_color")[0]

        if self.parent is None or self.disabled:
            color_inst.rgba = self.disabled_color
            return

        outline_color1 = self.outline_color1
        outline_color2 = self.outline_color2
        color_inst.rgba = outline_color1
        start_blinking = Clock.create_trigger(
            partial(self._change_outline_color, color_inst, itertools.cycle((outline_color1, outline_color2, )).__next__),
            self.outline_blinking_interval, interval=True,
        )
        stop_blinking = start_blinking.cancel
        self_collide_point = self.collide_point
        try:
            while True:
                __, touch = await ak.event(
                    self, "on_touch_down", filter=is_pos_colliding_and_not_wheel, stop_dispatching=True)
                color_inst.rgba = outline_color2
                start_blinking()
                async with ak.rest_of_touch_events(self, touch, stop_dispatching=True) as on_touch_move:
                    while True:
                        await on_touch_move()
                        if self_collide_point(*touch.pos):
                            start_blinking()
                        else:
                            stop_blinking()
                            color_inst.rgba = outline_color1
                if self_collide_point(*touch.pos):
                    with ak.transform(self, canvas_layer="outer") as ig:
                        ig.add(s := Scale(origin=self.center))
                        await ak.anim_attrs(s, xyz=(0.9, 0.9, 1.0), duration=.05)
                        await ak.anim_attrs(s, xyz=(1.0, 1.0, 1.0), duration=.05)
                    self.dispatch("on_release")
                stop_blinking()
                color_inst.rgba = outline_color1
        finally:
            stop_blinking()
            # outline_color1 の変化によりtaskが中断される状況を考えるとここではlocal変数のoutline_color1は使わない方が良いだろう。
            color_inst.rgba = self.outline_color1

    def on_release(self):
        pass


async def ask_yes_no_question(
    question: str, *, window=None, yes_text="Yes", no_text="No",
    transition=modal.SlideTransition(), auto_dismiss=True, _cache=[],
) -> Awaitable[Literal["yes", "no", None]]:
    '''
    Asks the user a yes/no question via a modal dialog.

    .. code-block::

        answer = await ask_yes_no_question("Do you like Kivy?")

    :return: None if the dialog is auto-dismissed.
    '''
    if window is None:
        from kivy.core.window import Window
        window = Window
    dialog = _cache.pop() if _cache else F.YesNoDialog()
    try:
        ids = dialog.ids
        ids.question.text = question
        ids.yes_button.text = yes_text
        ids.no_button.text = no_text
        async with modal.open(
            dialog, window=window, auto_dismiss=auto_dismiss, transition=transition
        ) as auto_dismissed:
            tasks = await ak.wait_any(
                ak.event(ids.yes_button, "on_release"),
                ak.event(ids.no_button, "on_release"),
            )
        if auto_dismissed:
            return None
        return "yes" if tasks[0].finished else "no"
    finally:
        _cache.append(dialog)
