__all__ = ("SharedObjects", "run", )

from typing import TypeAlias
from functools import partial
from contextlib import closing
import dataclasses
from io import BytesIO
import pathlib
import sqlite3
from importlib import resources

from kivy.utils import get_color_from_hex
from kivy.metrics import dp as metrics_dp
from kivy.graphics.texture import Texture
from kivy.core.audio_output import SoundLoader, Sound
from kivy.core.image import Image as CoreImage
from kivy.uix.floatlayout import FloatLayout


@dataclasses.dataclass(kw_only=True)
class SharedState:
    displays_hit_boxes: bool = False
    game_duration: float = 30.0
    last_game_score: int = -1


@dataclasses.dataclass(kw_only=True, frozen=True)
class SharedData:
    images: dict[str, Texture]
    image_relative_widths: dict[str, float]
    sounds: dict[str, Sound]

    def asdict(self):
        '''Return a shallow dictionary representation of the dataclass.'''
        return {field.name: getattr(self, field.name) for field in dataclasses.fields(self)}


SharedObjects: TypeAlias = tuple[SharedData, SharedState]
'''
This is passed to each scene as the ``userdata`` argument.
'''


async def run(parent: FloatLayout) -> None:
    from asynckivy import transition
    from . import sceneswitcher

    images, sounds = load_assets()
    images.update(_generate_score_delta_images())

    for s in sounds.values():
        s.volume = 0.5
    await sceneswitcher.run(
        "whack_a_homole.scenes.game.main",
        transition.fade,
        parent=parent,
        userdata=(
            SharedData(
                images=images,
                image_relative_widths=_calc_widths_of_images_relative_to_the_neutral_image(images),
                sounds=sounds,
            ),
            SharedState(),
        ),
    )


def _reload_texture(image_data: bytes, texture):
    # TODO: This function is untested because I don't know how to trigger an OpenGL context loss.
    # https://kivy.org/doc/master/api-kivy.graphics.texture.html#reloading-the-texture
    img = CoreImage(BytesIO(image_data), ext="png")
    texture.blit_data(img._image._data[0])


def _load_images(cur: sqlite3.Cursor) -> dict[str, Texture]:
    return {
        name: (
            tex := CoreImage(BytesIO(image_data), ext="png").texture,
            tex.add_reload_observer(partial(_reload_texture, image_data)),
        ) and tex
        for name, image_data in cur.execute("SELECT name, image_data FROM Images")
    }


def _load_sounds(cur: sqlite3.Cursor) -> dict[str, Sound]:
    import tempfile
    # SoundLoader does not support loading from memory yet, so I need to write to a temporary file,
    # then load it. (https://github.com/kivy/kivy/pull/8799)
    #
    # Also, the GstPlayer provider appears to require the source file used to create a Sound
    # instance to remain available whenever the sound is played, so this function does not work
    # with that provider because it deletes the source files.

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)
        return {
            name: (
                tmp := tmpdir / (name + ".wav"),
                tmp.write_bytes(sound_data),
            ) and SoundLoader.load(str(tmp))
            for name, sound_data in cur.execute("SELECT name, sound_data FROM Sounds")
        }


def load_assets() -> tuple[dict[str, Texture], dict[str, Sound]]:
    # I might try to convert the app to a zipapp in the future,
    # so I use 'importlib.resources' instead of filesystem APIs.
    with sqlite3.connect(":memory:") as conn:
        conn.deserialize(resources.read_binary("whack_a_homole", "assets.sqlite3"))
        with closing(conn.cursor()) as cur:
            return _load_images(cur), _load_sounds(cur)


def _calc_widths_of_images_relative_to_the_neutral_image(images: dict[str, Texture]):
    base_width = images["neutral"].width
    return {
        name: image.width / base_width
        for name, image in images.items()
    }


def _generate_score_delta_images() -> dict[str, Texture]:
    from whack_a_homole.utils import render_text_to_texture

    font_size = metrics_dp(80)
    return {
        text: render_text_to_texture(
            text, font_size=font_size, color=get_color_from_hex(color), bold=True)
        for text, color in (
            ("-1", "#8470ff"),
            ("+1", "#45af23"),
            ("+3", "#84ff23"),
        )
    }
