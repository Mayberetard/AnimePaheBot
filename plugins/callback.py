#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from plugins.queue import add_to_queue, remove_from_queue
from plugins.kwik import extract_kwik_link
from plugins.direct_link import get_dl_link
from plugins.headers import *
from plugins.file import *
from plugins.commands import user_queries
from helper.database import *
from config import DOWNLOAD_DIR
from bs4 import BeautifulSoup
import os
import re
import requests

episode_data = {}
episode_urls = {}

@Client.on_callback_query(filters.regex(r"^anime_"))
async def anime_details(client, callback_query: CallbackQuery):
    session_id = callback_query.data.split("anime_")[1]
    query = user_queries.get(callback_query.message.chat.id, "")
    search_url = f"https://animepahe.ru/api?m=search&q={query.replace(' ', '+')}"
    response = session.get(search_url).json()

    anime = next(anime for anime in response['data'] if anime['session'] == session_id)
    title = anime['title']
    message_text = (
        f"**Title**: {anime['title']}\n"
        f"**Type**: {anime['type']}\n"
        f"**Episodes**: {anime['episodes']}\n"
        f"**Status**: {anime['status']}\n"
        f"**Season**: {anime['season']}\n"
        f"**Year**: {anime['year']}\n"
        f"**Score**: {anime['score']}\n"
        f"[Anime Link](https://animepahe.ru/anime/{session_id})\n\n"
        f"**Bot Made By**\n"
        f"    **[RAHAT](tg://user?id=1235222889)**"
    )

    episode_data[callback_query.message.chat.id] = {
        "session_id": session_id,
        "poster": anime['poster'],
        "title": title
    }

    await client.send_photo(
        chat_id=callback_query.message.chat.id,
        photo=anime['poster'],
        caption=message_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Episodes", callback_data="episodes")]])
    )


@Client.on_callback_query(filters.regex(r"^episodes$"))
async def episode_list(client, callback_query: CallbackQuery, page=1):
    session_data = episode_data.get(callback_query.message.chat.id)
    if not session_data:
        await callback_query.message.reply_text("Session ID not found.")
        return

    session_id = session_data['session_id']
    response = session.get(f"https://animepahe.ru/api?m=release&id={session_id}&sort=episode_asc&page={page}").json()
    episodes = response['data']
    last_page = int(response["last_page"])

    episode_data[callback_query.message.chat.id].update({
        "current_page": page,
        "last_page": last_page,
        "episodes": {ep['episode']: ep['session'] for ep in episodes}
    })

    episode_buttons = [[InlineKeyboardButton(f"Episode {ep['episode']}", callback_data=f"ep_{ep['episode']}")] for ep in episodes]
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("<", callback_data=f"page_{page - 1}"))
    if page < last_page:
        nav_buttons.append(InlineKeyboardButton(">", callback_data=f"page_{page + 1}"))
    if nav_buttons:
        episode_buttons.append(nav_buttons)

    markup = InlineKeyboardMarkup(episode_buttons)
    if callback_query.message.reply_markup is None:
        await callback_query.message.reply_text(f"Page {page}/{last_page}: Select an episode:", reply_markup=markup)
    else:
        await callback_query.message.edit_reply_markup(markup)


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
    soup = BeautifulSoup(session.get(f"https://animepahe.ru/play/{session_id}/{episode_session}").content, "html.parser")
    download_links = soup.select("#pickDownload a.dropdown-item")

    if not download_links:
        await callback_query.message.reply_text("No download links found.")
        return

    buttons = [[InlineKeyboardButton(link.get_text(strip=True), callback_data=f"dl_{link['href']}")] for link in download_links]
    await callback_query.message.reply_text("Select a download link:", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"set_method_"))
async def change_upload_method(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    method = callback_query.data.split("_")[2]
    save_upload_method(user_id, method)
    await callback_query.answer(f"Upload method set to {method.capitalize()}")

    doc_status = "✅" if method == "document" else "❌"
    vid_status = "✅" if method == "video" else "❌"

    buttons = [[
        InlineKeyboardButton(f"Document ({doc_status})", callback_data="set_method_document"),
        InlineKeyboardButton(f"Video ({vid_status})", callback_data="set_method_video")
    ]]
    await callback_query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^dl_"))
async def download_and_upload_file(client, callback_query: CallbackQuery):
    from asyncio import to_thread

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

    episode_number = episode_data.get(user_id, {}).get('current_episode', 'Unknown')
    title = episode_data.get(user_id, {}).get('title', 'Unknown Title')
    download_button_title = next(
        (b.text for row in callback_query.message.reply_markup.inline_keyboard
         for b in row if b.callback_data == f"dl_{download_url}"),
        "Unknown Source"
    )

    resolution = re.search(r"\b\d{3,4}p\b", download_button_title)
    resolution = resolution.group() if resolution else download_button_title
    type = "Dub" if 'eng' in download_button_title else "Sub"
    short_title = create_short_name(title)
    filename = sanitize_filename(f"[{type}] [{short_title}] [EP {episode_number}] [{resolution}].mp4")
    random_str = random_string(5)

    user_download_dir = os.path.join(DOWNLOAD_DIR, str(user_id), random_str)
    os.makedirs(user_download_dir, exist_ok=True)
    download_path = os.path.join(user_download_dir, filename)

    dl_msg = await callback_query.message.reply_text(
        f"<b>Added to queue:</b>\n <pre>{filename}</pre>\n<b>Downloading now...</b>"
    )

    try:
        await to_thread(download_file, direct_link, download_path)
        await dl_msg.edit("<b>Episode downloaded, uploading...</b>")

        user_thumbnail = get_thumbnail(user_id)
        poster_url = episode_data.get(user_id, {}).get("poster", None)

        if user_thumbnail:
            thumb_path = await client.download_media(user_thumbnail)
        elif poster_url:
            response = requests.get(poster_url, stream=True)
            thumb_path = os.path.join(user_download_dir, "thumb.jpg")
            with open(thumb_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        else:
            thumb_path = None

        user_caption = get_caption(user_id)
        caption_to_use = user_caption if user_caption else filename

        await to_thread(send_and_delete_file, client, callback_query.message.chat.id, download_path, thumb_path, caption_to_use, user_id)
        remove_from_queue(user_id, direct_link)

        await dl_msg.edit("<b><pre>Episode Uploaded 🎉</pre></b>")

        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        if os.path.exists(user_download_dir):
            remove_directory(user_download_dir)

    except Exception as e:
        await callback_query.message.reply_text(f"Error: {str(e)}")


@Client.on_callback_query()
async def callback_query_handler(client, callback_query: CallbackQuery):
    if callback_query.data == "help":
        await callback_query.message.edit_text(
            text="Here is how to use the bot:\n\n"
                 "1. /anime <anime_name> - Search for an anime.\n"
                 "2. /set_thumb - Set a custom thumbnail.\n"
                 "3. /options - Set upload options (Document or Video).\n"
                 "4. /queue - View active downloads.\n"
                 "5. /set_caption - Set custom caption.\n"
                 "6. /see_caption - See current custom caption.\n"
                 "7. /del_caption - Delete current custom caption",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Close", callback_data="close")]]
            )
        )
    elif callback_query.data == "close":
        await callback_query.message.delete()
