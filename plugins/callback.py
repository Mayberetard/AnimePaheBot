#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from plugins.queue import add_to_queue, remove_from_queue
from plugins.kwik import extract_kwik_link
from plugins.direct_link import get_dl_link
from plugins.headers import session
from plugins.file import create_short_name, sanitize_filename, download_file, send_and_delete_file, remove_directory
from plugins.commands import user_queries
from helper.database import save_upload_method, get_upload_method, get_thumbnail, get_caption
from config import DOWNLOAD_DIR
from bs4 import BeautifulSoup
import os, random, re, asyncio

episode_data = {}


@Client.on_callback_query(filters.regex(r"^anime_"))
async def anime_details(client, callback_query: CallbackQuery):
    session_id = callback_query.data.split("anime_")[1]
    query = user_queries.get(callback_query.message.chat.id, "")
    search_url = f"https://animepahe.ru/api?m=search&q={query.replace(' ', '+')}"
    response = session.get(search_url).json()

    anime = next(anime for anime in response['data'] if anime['session'] == session_id)
    title = anime['title']
    anime_type = anime['type']
    episodes = anime['episodes']
    status = anime['status']
    season = anime['season']
    year = anime['year']
    score = anime['score']
    poster_url = anime['poster']
    anime_link = f"https://animepahe.ru/anime/{session_id}"

    message_text = (
        f"**Title**: {title}\n"
        f"**Type**: {anime_type}\n"
        f"**Episodes**: {episodes}\n"
        f"**Status**: {status}\n"
        f"**Season**: {season}\n"
        f"**Year**: {year}\n"
        f"**Score**: {score}\n"
        f"[Anime Link]({anime_link})\n\n"
        f"**Bot Made By**\n"
        f"    **[RAHAT](tg://user?id=1235222889)**"
    )

    episode_data[callback_query.message.chat.id] = {
        "session_id": session_id,
        "poster": poster_url,
        "title": title
    }

    episode_button = InlineKeyboardMarkup([[InlineKeyboardButton("Episodes", callback_data="episodes")]])
    await client.send_photo(
        chat_id=callback_query.message.chat.id,
        photo=poster_url,
        caption=message_text,
        reply_markup=episode_button
    )


@Client.on_callback_query(filters.regex(r"^episodes$"))
async def episode_list(client, callback_query: CallbackQuery, page=1):
    session_data = episode_data.get(callback_query.message.chat.id)
    if not session_data:
        await callback_query.message.reply_text("Session ID not found.")
        return

    session_id = session_data['session_id']
    episodes_url = f"https://animepahe.ru/api?m=release&id={session_id}&sort=episode_asc&page={page}"
    response = session.get(episodes_url).json()

    last_page = int(response["last_page"])
    episodes = response['data']
    episode_data[callback_query.message.chat.id].update({
        'current_page': page,
        'last_page': last_page,
        'episodes': {ep['episode']: ep['session'] for ep in episodes}
    })

    episode_buttons = [[InlineKeyboardButton(f"Episode {ep['episode']}", callback_data=f"ep_{ep['episode']}")] for ep in episodes]
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("<", callback_data=f"page_{page - 1}"))
    if page < last_page:
        nav_buttons.append(InlineKeyboardButton(">", callback_data=f"page_{page + 1}"))
    if nav_buttons:
        episode_buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(episode_buttons)
    await callback_query.message.edit_reply_markup(reply_markup)


@Client.on_callback_query(filters.regex(r"^page_"))
async def navigate_pages(client, callback_query: CallbackQuery):
    new_page = int(callback_query.data.split("_")[1])
    session_data = episode_data.get(callback_query.message.chat.id)

    if not session_data:
        await callback_query.message.reply_text("Session ID not found.")
        return

    current_page = session_data.get('current_page', 1)
    last_page = session_data.get('last_page', 1)

    if new_page < 1:
        await callback_query.answer("You're already on the first page.", show_alert=True)
    elif new_page > last_page:
        await callback_query.answer("You're already on the last page.", show_alert=True)
    else:
        await episode_list(client, callback_query, page=new_page)


@Client.on_callback_query(filters.regex(r"^ep_"))
async def fetch_download_links(client, callback_query: CallbackQuery):
    episode_number = int(callback_query.data.split("_")[1])
    user_id = callback_query.message.chat.id
    session_data = episode_data.get(user_id)

    if not session_data or 'episodes' not in session_data:
        await callback_query.message.reply_text("Episode not found.")
        return

    session_id = session_data['session_id']
    episodes = session_data['episodes']

    if episode_number not in episodes:
        await callback_query.message.reply_text("Episode not found.")
        return

    episode_data[user_id]['current_episode'] = episode_number
    episode_session = episodes[episode_number]
    episode_url = f"https://animepahe.ru/play/{session_id}/{episode_session}"

    response = session.get(episode_url)
    soup = BeautifulSoup(response.content, "html.parser")
    download_links = soup.select("#pickDownload a.dropdown-item")

    if not download_links:
        await callback_query.message.reply_text("No download links found.")
        return

    download_buttons = [
        [InlineKeyboardButton(link.get_text(strip=True), callback_data=f"dl_{link['href']}")]
        for link in download_links
    ]
    reply_markup = InlineKeyboardMarkup(download_buttons)
    await callback_query.message.reply_text("Select a download link:", reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"set_method_"))
async def change_upload_method(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data.split("_")[2]
    save_upload_method(user_id, data)
    await callback_query.answer(f"Upload method set to {data.capitalize()}")

    document_status = "✅" if data == "document" else "❌"
    video_status = "✅" if data == "video" else "❌"

    buttons = [
        [
            InlineKeyboardButton(f"Document ({document_status})", callback_data="set_method_document"),
            InlineKeyboardButton(f"Video ({video_status})", callback_data="set_method_video")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    try:
        await callback_query.message.edit_reply_markup(reply_markup)
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^dl_"))
async def download_and_upload_file(client, callback_query):
    download_url = callback_query.data.split("dl_")[1]
    kwik_link = extract_kwik_link(download_url)

    try:
        direct_link = get_dl_link(kwik_link)
    except Exception as e:
        await callback_query.message.reply_text(f"Error generating download link: {str(e)}")
        return

    username = callback_query.from_user.username or "Unknown User"
    user_id = callback_query.from_user.id
    add_to_queue(user_id, username, direct_link)

    session_data = episode_data.get(user_id, {})
    ep_num = session_data.get("current_episode", "Unknown")
    title = session_data.get("title", "Unknown Title")
    download_button_title = next(
        (btn.text for row in callback_query.message.reply_markup.inline_keyboard for btn in row if btn.callback_data == f"dl_{download_url}"),
        "Unknown Source"
    )
    res_match = re.search(r"\b\d{3,4}p\b", download_button_title)
    res = res_match.group() if res_match else download_button_title
    typ = "Dub" if "eng" in download_button_title else "Sub"
    short_name = create_short_name(title)
    filename = sanitize_filename(f"[{typ}] [{short_name}] [EP {ep_num}] [{res}].mp4")
    random_str = random_string(5)
    user_dir = os.path.join(DOWNLOAD_DIR, str(user_id), random_str)
    os.makedirs(user_dir, exist_ok=True)
    download_path = os.path.join(user_dir, filename)

    dl_msg = await callback_query.message.reply_text(
        f"Added to queue:\n<code>{filename}</code>\nDownloading now...")

    try:
        download_file(direct_link, download_path)
        await dl_msg.edit("Episode downloaded, uploading...")

        user_thumb = get_thumbnail(user_id)
        poster = session_data.get("poster")

        if user_thumb:
            thumb_path = await client.download_media(user_thumb)
        elif poster:
            resp_thumb = session.get(poster, stream=True)
            thumb_path = os.path.join(user_dir, "thumb.jpg")
            with open(thumb_path, "wb") as f:
                for chunk in resp_thumb.iter_content(1024):
                    f.write(chunk)
        else:
            thumb_path = None

        user_caption = get_caption(user_id)
        caption = user_caption if user_caption else filename

        send_and_delete_file(client, callback_query.message.chat.id, download_path, thumb_path, caption, user_id)
        remove_from_queue(user_id, direct_link)
        await dl_msg.edit("Episode Uploaded 🎉")

        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        if os.path.exists(user_dir):
            remove_directory(user_dir)

    except Exception as e:
        await callback_query.message.reply_text(f"Error: {e}")

@Client.on_callback_query()
async def callback_query_handler(client, callback_query: CallbackQuery):
    if callback_query.data == "help":
        await callback_query.message.edit_text(
            text=(
                "Here is how to use the bot:\n\n"
                "1. /anime <anime_name> - Search for an anime.\n"
                "2. /set_thumb - Set a custom thumbnail.\n"
                "3. /options - Set upload options (Document or Video).\n"
                "4. /queue - View active downloads.\n"
                "5. /set_caption - Set custom caption.\n"
                "6. /see_caption - See current custom caption.\n"
                "7. /del_caption - Delete current custom caption."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif callback_query.data == "close":
        await callback_query.message.delete()
