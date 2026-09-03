from contextlib import closing
from io import BytesIO
import sqlite3
from pathlib import Path

import requests
from PIL import Image


def crop_image(image_data: bytes) -> bytes:
    img = Image.open(BytesIO(image_data))
    bbox = img.getbbox()
    if bbox == (0, 0, *img.size):
        return image_data
    with BytesIO() as f:
        img.crop(bbox).save(f, format="PNG")
        return f.getvalue()


def download_images() -> dict[str, bytes]:
    URLS = (
        ("neutral", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgh1PA4Bjg2mGnrFcuufNP1WP2kPRqXMRJQSz-fHxBxRYSGjwZQmbkMEe495vP_23LwafvGR2her8vQhM836BMYvJvKCJVkH9NvHTJ5gdoyAz5bFuQIW7SUDX7gTDJC7qIsqyE9vhuU9Wg/s400/figure_standing.png"),
        ("square-off", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEh5w726e-ADC9DDJdytCRtdPAHogCk3CLTNF-2N3RglZbTgf_Ad1-2N4rQngxYE8IeDlz0E-fhIJOsOGoisP-O1J66KVTFFs9DJ6b7Vd4YyXGkPWNFpmNn0Kl7IkiPhZcnomsfrnDYur4k/s400/figure_fighting_pose.png"),
        ("attack", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiuUsvvOwAK4_FlBL5itKyfcgQhzpOhsLZCUFHWbgZZVUl6-Km5hwFIiF8fKCJ2zSdQD5sJpqsBIWEOqThdmc6RUb1FHCtxV7AwyRFX4keVgnm0AN6I-6iDI_yrbWYHLsi2qUUTFLMVySI/s400/figure_fighting_punch.png"),
        ("deliver", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgsErzqpQO9Z87VBwkeb-G_3UrQVHBBAqFR5ONIvwD6DKnjVvCJFFdyqPECypqzKoN1BOqd7e1T9D-L_1-9zYpYIydZZdsq3Cs3bu3p4_7WZUmE9hsP5FQ0gvgQ-wzbG7SoZmmXxMnNtWw/s400/figure_box_carrying.png"),
        ("gift", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEh0evgMM9Ax4RyinjeIOCA_6vVsgFmQwyEfuEnm95a3uv6gWN5QSVb3SS9wqYOHB3sAeno92N_vdS_C160UL8ILjIxe4naoHSsey4dbxtAkLcyeGz7c-e3dDY91nB-9JXbSGyGehDgJuRQq/s400/present_box.png"),
        ("clap", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiYu-t8WjYxwde_VFWPsxSSg6ux32QZtPmP6BFlqrlcZmjiP0bCMO_uwcLwliT9YKSY-Pdk7YLWn-d1tEAeJbvfXAchJ-5vl0tYeWa5cFDSbQIGZ0t0dpH8DQPZ000CbHgJkdzxwYKpnf7K/s450/figure_hakusyu.png"),
        ("orz", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgVV4gxY5N__pAU4EYXRD2fNav5FvKlgfZmhBwYHLdBqnj_2rio9GKWvBstAW94lT-Ts63tCOI0ySdm_lfGlxwfCYBjw-J1Pq9V1LjUFUSfnOb4lAMUu6BN07q4Iv-yIZWGVrLw81IAXyE/s400/figure_zasetsu.png"),
        ("robot", r"https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhsQ2aihomoPrWm1WsTN1cbl2e4mOBuUNCsZmjq_KWTHdYjf19Wkw3b8PEWpxC4owjzMypxSP-dNP5kkLQPt9MjrRiKHuFu94o_4kZpi7uDcvCOkT3IbqiiPCDAzzNv2XilT5BjDMxJTWc/s400/omocha_robot.png"),
    )
    with requests.Session() as s:
        s.headers["Referer"] = "https://www.irasutoya.com/"
        return {name: s.get(url).content for name, url in URLS}


def download_sounds() -> dict[str, bytes]:
    URLS = (
        ("hit", r"https://maou.audio/sound/se/maou_se_battle07.wav"),
        ("hurt", r"https://maou.audio/sound/se/maou_se_battle18.wav"),
        ("gift", r"https://maou.audio/sound/se/maou_se_system46.wav"),
    )
    with requests.Session() as s:
        s.headers["Referer"] = "https://maou.audio/"
        return {name: s.get(url).content for name, url in URLS}


def download_assets(save_path: str):
    with sqlite3.connect(save_path) as conn, closing(conn.cursor()) as cur:
        cur.executescript("""
            CREATE TABLE Images(
                name TEXT NOT NULL UNIQUE,
                image_data BLOB NOT NULL,
                PRIMARY KEY (name)
            ) STRICT;
            CREATE TABLE Sounds(
                name TEXT NOT NULL UNIQUE,
                sound_data BLOB NOT NULL,
                PRIMARY KEY (name)
            ) STRICT;
        """)
        images = download_images()
        cur.executemany(
            "INSERT INTO Images(name, image_data) VALUES(?, ?)",
            ((name, crop_image(image_data)) for name, image_data in images.items()),
        )
        sounds = download_sounds()
        cur.executemany(
            "INSERT INTO Sounds(name, sound_data) VALUES(?, ?)",
            sounds.items(),
        )


def main():
    save_path = Path(__file__).parent.joinpath("whack_a_homole", "assets.sqlite3")
    if save_path.exists():
        print(r"'assets.sqlite3' already exists.")
        return
    print("Downloading assets...")
    download_assets(str(save_path))
    print("Done!")


if __name__ == "__main__":
    main()
