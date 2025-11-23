"""
Image generator for CryptoHack solve announcements.
Creates images similar to Root-Me bot style.
"""

import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Optional

# Paths
BASE_DIR = Path(__file__).parent
ANON_IMAGE_PATH = BASE_DIR / "anon.png"
FIRSTBLOOD_IMAGE_PATH = BASE_DIR / "firstblood.png"
LOGO_IMAGE_PATH = BASE_DIR / "cryptohack.png"
JEFITH_FONT_PATH = BASE_DIR / "JefithPersonalUse-ALqw2.otf"
OSWALD_MEDIUM_PATH = BASE_DIR / "OswaldMedium.ttf"
OSWALD_LIGHT_PATH = BASE_DIR / "OswaldLight.ttf"
CATEGORY_ICONS_DIR = BASE_DIR / "category_icons"

# Category name to icon file mapping
CATEGORY_ICON_MAP = {
    "introduction": "introduction.png",
    "general": "general.png",
    "symmetric ciphers": "aes.png",
    "aes": "aes.png",
    "mathematics": "maths.png",
    "maths": "maths.png",
    "rsa": "rsa.png",
    "diffie-hellman": "diffie-hellman.png",
    "elliptic curves": "ecc.png",
    "ecc": "ecc.png",
    "hash functions": "hashes.png",
    "hashes": "hashes.png",
    "crypto on the web": "web.png",
    "web": "web.png",
    "misc": "misc.png",
    "miscellaneous": "misc.png",
}

# Colors
BG_COLOR = (24, 24, 24)
TITLE_COLOR = (150, 230, 150)
USERNAME_COLOR = (255, 255, 255)
SCORE_COLOR = (180, 180, 180)
CHALLENGE_COLOR = (255, 255, 200)
POINTS_COLOR = (180, 180, 180)
CATEGORY_COLOR = (170, 170, 170)
SUBTITLE_COLOR = (200, 200, 200)
LOGO_TEXT_COLOR = (100, 100, 100)

# Image dimensions
IMAGE_WIDTH = 700
IMAGE_HEIGHT = 300


def get_jefith_font(size: int) -> ImageFont.FreeTypeFont:
    """Get Jefith font for titles."""
    if JEFITH_FONT_PATH.exists():
        try:
            return ImageFont.truetype(str(JEFITH_FONT_PATH), size)
        except Exception:
            pass
    return get_oswald_medium_font(size)


def get_oswald_medium_font(size: int) -> ImageFont.FreeTypeFont:
    """Get Oswald Medium font for username and challenge name."""
    if OSWALD_MEDIUM_PATH.exists():
        try:
            return ImageFont.truetype(str(OSWALD_MEDIUM_PATH), size)
        except Exception:
            pass
    return _get_fallback_font(size)


def get_oswald_light_font(size: int) -> ImageFont.FreeTypeFont:
    """Get Oswald Light font for other content."""
    if OSWALD_LIGHT_PATH.exists():
        try:
            return ImageFont.truetype(str(OSWALD_LIGHT_PATH), size)
        except Exception:
            pass
    return _get_fallback_font(size)


def _get_fallback_font(size: int) -> ImageFont.FreeTypeFont:
    """Fallback font."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for font_path in font_paths:
        try:
            if Path(font_path).exists():
                return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def get_category_icon(category: str) -> Optional[Image.Image]:
    """Get the icon for a category."""
    category_lower = category.lower()
    for key, filename in CATEGORY_ICON_MAP.items():
        if key in category_lower:
            icon_path = CATEGORY_ICONS_DIR / filename
            if icon_path.exists():
                try:
                    return Image.open(icon_path).convert("RGBA")
                except Exception:
                    pass
    default_path = CATEGORY_ICONS_DIR / "general.png"
    if default_path.exists():
        try:
            return Image.open(default_path).convert("RGBA")
        except Exception:
            pass
    return None


async def fetch_avatar(avatar_url: str, session: aiohttp.ClientSession) -> Optional[Image.Image]:
    """Fetch and return a user's avatar image."""
    try:
        async with session.get(avatar_url) as response:
            if response.status == 200:
                data = await response.read()
                return Image.open(io.BytesIO(data))
    except Exception:
        pass
    return None


def create_circle_mask(size: int) -> Image.Image:
    """Create a circular mask for avatar."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    return mask


async def generate_solve_image(
    username: str,
    score: int,
    challenge_name: str,
    category: str,
    points: int,
    server_rank: int,
    total_solvers: int,
    is_first_blood: bool = False,
    avatar_url: Optional[str] = None,
    session: Optional[aiohttp.ClientSession] = None
) -> io.BytesIO:
    """Generate a solve announcement image."""
    img = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Font sizes
    TITLE_SIZE = 48
    USERNAME_SIZE = 32   # -4
    SCORE_SIZE = 22      # -8
    CHALLENGE_SIZE = 34
    POINTS_SIZE = 28     # -4
    CATEGORY_SIZE = 28
    RANK_SIZE = 26
    LOGO_TEXT_SIZE = 26

    # Margins
    MARGIN_X = 40

    # === TITLE (top left) - JEFITH ===
    title_text = "NOUVEAU CHALLENGE VALIDÉ"
    title_font = get_jefith_font(TITLE_SIZE)
    draw.text((MARGIN_X, 12), title_text, font=title_font, fill=TITLE_COLOR)

    # === FIRST BLOOD ICON ===
    if is_first_blood and FIRSTBLOOD_IMAGE_PATH.exists():
        try:
            fb_icon = Image.open(FIRSTBLOOD_IMAGE_PATH).convert("RGBA")
            fb_icon = fb_icon.resize((45, 45), Image.Resampling.LANCZOS)
            title_width = draw.textlength(title_text, font=title_font)
            img.paste(fb_icon, (int(MARGIN_X + title_width + 12), 8), fb_icon)
        except Exception:
            pass

    # === CRYPTOHACK text (top right) - JEFITH ===
    logo_text = "CRYPTOHACK"
    logo_text_font = get_jefith_font(LOGO_TEXT_SIZE)
    logo_text_width = draw.textlength(logo_text, font=logo_text_font)
    draw.text((IMAGE_WIDTH - logo_text_width - MARGIN_X, 18), logo_text, font=logo_text_font, fill=LOGO_TEXT_COLOR)

    # === CRYPTOHACK LOGO (bottom right) ===
    if LOGO_IMAGE_PATH.exists():
        try:
            logo = Image.open(LOGO_IMAGE_PATH).convert("RGBA")
            logo_size = 50
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            img.paste(logo, (IMAGE_WIDTH - logo_size - MARGIN_X, IMAGE_HEIGHT - logo_size - 10), logo)
        except Exception:
            pass

    # === AVATAR ===
    avatar_size = 90
    avatar_x = MARGIN_X
    avatar_y = 60

    avatar_img = None
    if avatar_url and session:
        avatar_img = await fetch_avatar(avatar_url, session)

    if avatar_img is None and ANON_IMAGE_PATH.exists():
        try:
            avatar_img = Image.open(ANON_IMAGE_PATH).convert("RGBA")
        except Exception:
            pass

    if avatar_img:
        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        mask = create_circle_mask(avatar_size)
        circular_avatar = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
        circular_avatar.paste(avatar_img, (0, 0), mask)
        img.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)
    else:
        draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(60, 60, 60))
        draw.text((avatar_x + avatar_size // 2 - 8, avatar_y + avatar_size // 2 - 12), "?", font=get_oswald_light_font(26), fill=(150, 150, 150))

    # === USERNAME - OSWALD MEDIUM ===
    text_x = avatar_x + avatar_size + 15
    text_y = avatar_y + 12
    username_font = get_oswald_medium_font(USERNAME_SIZE)
    draw.text((text_x, text_y), username.upper(), font=username_font, fill=USERNAME_COLOR)

    # === SCORE - OSWALD LIGHT ===
    score_font = get_oswald_light_font(SCORE_SIZE)
    draw.text((text_x, text_y + 42), f"SCORE: {score}", font=score_font, fill=SCORE_COLOR)

    # === CHALLENGE NAME - OSWALD MEDIUM ===
    challenge_y = 155
    challenge_font = get_oswald_medium_font(CHALLENGE_SIZE)
    challenge_text = challenge_name.upper()
    draw.text((MARGIN_X, challenge_y), challenge_text, font=challenge_font, fill=CHALLENGE_COLOR)

    # === POINTS - OSWALD MEDIUM ===
    points_font = get_oswald_light_font(POINTS_SIZE)
    challenge_width = draw.textlength(challenge_text, font=challenge_font)
    draw.text((MARGIN_X + challenge_width + 15, challenge_y + 4), f"{points} POINTS", font=points_font, fill=POINTS_COLOR)

    # === CATEGORY WITH ICON - OSWALD LIGHT ===
    category_y = challenge_y + 42
    category_icon = get_category_icon(category)
    icon_size = 32
    category_font = get_oswald_light_font(CATEGORY_SIZE)

    if category_icon:
        category_icon = category_icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        # Align icon bottom with text baseline
        img.paste(category_icon, (MARGIN_X, category_y + 7), category_icon)
        draw.text((MARGIN_X + icon_size + 10, category_y + 3), category.upper(), font=category_font, fill=CATEGORY_COLOR)
    else:
        draw.text((MARGIN_X, category_y), category.upper(), font=category_font, fill=CATEGORY_COLOR)

    # === SERVER RANK (lowercase) - OSWALD LIGHT ===
    rank_y = category_y + 36
    rank_font = get_oswald_light_font(RANK_SIZE)

    if is_first_blood:
        rank_text = "1er du serveur"
    elif server_rank == 2:
        rank_text = "2ème du serveur"
    else:
        rank_text = f"{server_rank}ème du serveur"

    draw.text((MARGIN_X, rank_y), rank_text, font=rank_font, fill=SUBTITLE_COLOR)

    # Convert to bytes
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


async def generate_test_image() -> io.BytesIO:
    """Generate a test image."""
    return await generate_solve_image(
        username="CryptoHacker",
        score=2450,
        challenge_name="Encoding Challenge",
        category="General",
        points=10,
        server_rank=6,
        total_solvers=45000,
        is_first_blood=False
    )


async def generate_test_first_blood_image() -> io.BytesIO:
    """Generate a test first blood image."""
    return await generate_solve_image(
        username="L3akCTF",
        score=8750,
        challenge_name="RSA Starter 1",
        category="RSA",
        points=10,
        server_rank=1,
        total_solvers=30000,
        is_first_blood=True
    )


if __name__ == "__main__":
    import asyncio

    async def test():
        img_bytes = await generate_test_image()
        with open("example_solve.png", "wb") as f:
            f.write(img_bytes.read())
        print("Generated example_solve.png")

        img_bytes = await generate_test_first_blood_image()
        with open("example_firstblood.png", "wb") as f:
            f.write(img_bytes.read())
        print("Generated example_firstblood.png")

    asyncio.run(test())
