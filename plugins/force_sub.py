from plugins.commands import actual_start_handler  # import your main start logic
from bot import app as Client

@Client.on_message(filters.command("start") & filters.private)
async def force_sub_check(client, message):
    user_id = message.from_user.id

    try:
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        if member.status not in ["member", "administrator", "creator"]:
            raise UserNotParticipant
    except UserNotParticipant:
        invite_link = await client.export_chat_invite_link(FORCE_SUB_CHANNEL)
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=invite_link)],
            [InlineKeyboardButton("✅ I've Joined", callback_data="check_sub")]
        ]
        await message.reply("🚫 Please join our channel to use this bot.", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # ✅ User passed the force sub — call the actual start logic
    await actual_start_handler(client, message)
