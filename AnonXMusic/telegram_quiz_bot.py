from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Poll, PollAnswer, InputMediaPoll, TextWithEntities
from telethon.tl import types, functions
import re
import time
import random
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Replace with your values
api_id = '12380656'
api_hash = 'd927c13beaaf5110f25c505b7c071273'
session_string = '1BZWaqwUAUMXpkprM7vw9g1l_fLkn3q0PIZuyeo1X9b47TUOD5EbDYT2z_FPZtLyG3WvBXWRT129EXnL7aXaoSt3pQ7twadTTUMadeNV7j9jo-dUuBZcgkabzsuLhmbOKBdl1_OGUCcKH6BAH7amHNmNUvSZIe_dRG99yY1VnYacWnUDKGsrhXLbymBIRsFzowHzJ1ny_TJfq-xZ4Jccwwvx5P1j86g0E-2fadRS3U8yaNPj-_arTbskghhek7NHRsNfNGvl6ZWwCtmV_aYha6r8JA36IY8AbJS0H4qBRruyTIqc-1AO-h1oKclXQp28IbqhlJlRifrG1vbeY7ElNUlytsc4MId4='

client = TelegramClient(StringSession(session_string), api_id, api_hash)

target_chat = None  # Global to store target chat for simplicity

# Emoji removal pattern
emoji_pattern = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002500-\U00002BEF"  # chinese char
    "\U00002702-\U000027B0"
    "\U00002712-\U00002716"
    "\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937"
    "\U00010000-\U0010ffff"
    "\u2640-\u2642"
    "\u2600-\u2B55"
    "\u200d"
    "\u23cf"
    "\u23e9"
    "\u231a"
    "\ufe0f"  # dingbats
    "\u3030"
    "]+",
    flags=re.UNICODE
)

def remove_emojis_preserve_entities(twe: types.TextWithEntities) -> types.TextWithEntities:
    original_text = twe.text
    entities = twe.entities or []
    emoji_matches = list(emoji_pattern.finditer(original_text))
    new_text = ''
    pos = 0
    for match in emoji_matches:
        new_text += original_text[pos:match.start()]
        pos = match.end()
    new_text += original_text[pos:]

    new_entities = []
    for entity in entities:
        old_start = entity.offset
        old_end = old_start + entity.length
        removed_length_before = sum(m.end() - m.start() for m in emoji_matches if m.end() <= old_start)
        removed_length_within = sum(m.end() - m.start() for m in emoji_matches if old_start < m.end() <= old_end)
        new_start = old_start - removed_length_before
        new_length = entity.length - removed_length_within
        if new_length > 0:
            new_entity = type(entity)(
                offset=new_start,
                length=new_length,
                **{k: v for k, v in entity.__dict__.items() if k not in ['offset', 'length']}
            )
            new_entities.append(new_entity)

    return types.TextWithEntities(text=new_text, entities=new_entities)

@client.on(events.NewMessage(pattern='/pn'))
async def pn_handler(event):
    global target_chat
    reply = await event.get_reply_message()
    if not reply:
        await event.reply('Reply to a quiz share message.')
        return

    text = reply.text if reply.text else ''
    quiz_id = None
    if 't.me/QuizBot?start=' in text:
        quiz_id = re.search(r'start=([\w-]+)', text).group(1)
    elif '@QuizBot quiz:' in text:
        quiz_id = 'quiz:' + re.search(r'quiz:([\w-]+)', text).group(1)
    
    if not quiz_id and reply.buttons:
        for row in reply.buttons:
            for btn in row:
                if hasattr(btn, 'url') and btn.url and 't.me/QuizBot?start=' in btn.url:
                    match = re.search(r'start=([\w-]+)', btn.url)
                    if match:
                        quiz_id = match.group(1)
                        break
            if quiz_id:
                break

    if not quiz_id:
        await event.reply('Invalid quiz share format.')
        return

    target_chat = event.chat_id
    logging.info(f"Starting quiz with ID: {quiz_id}")
    await client.send_message('QuizBot', '/stop')
    await asyncio.sleep(1)
    await client.send_message('QuizBot', f'/start {quiz_id}')

@client.on(events.NewMessage(pattern='/again'))
async def again_handler(event):
    global target_chat
    if target_chat is None or event.chat_id != target_chat:
        await event.reply('No active quiz session. Use /pn to start a quiz.')
        return

    # Fetch recent messages from QuizBot to find the "Try again" button
    messages = await client.get_messages('QuizBot', limit=10)
    for msg in messages:
        if msg.buttons:
            for i, row in enumerate(msg.buttons):
                for j, btn in enumerate(row):
                    if btn.text and 'try again' in btn.text.lower():
                        await msg.click(i, j)
                        logging.info("Clicked 'Try again' button via /again command")
                        return
    await event.reply("No 'Try again' button found in recent QuizBot messages.")

@client.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    global target_chat
    if target_chat is None or event.chat_id != target_chat:
        return
    await client.send_message('QuizBot', '/stop')
    target_chat = None
    await event.reply('Stopped sending polls.')

@client.on(events.NewMessage(from_users='QuizBot'))
async def quiz_handler(event):
    global target_chat
    if not target_chat:
        return

    local_target = target_chat  # Capture the current target_chat to avoid race conditions

    msg = event.message

    if msg.buttons:
        for i, row in enumerate(msg.buttons):
            for j, btn in enumerate(row):
                button_text = btn.text.lower()
                if 'i am ready' in button_text:
                    await msg.click(i, j)
                    logging.info("Clicked 'I am ready' button")
                    return

    if msg.poll and msg.poll.poll.quiz:
        options_bytes = [ans.option for ans in msg.poll.poll.answers]
        vote_option = random.choice(options_bytes)
        await client(functions.messages.SendVoteRequest(
            peer='QuizBot',
            msg_id=msg.id,
            options=[vote_option]
        ))

        await asyncio.sleep(2)  # Wait for the message to update

        updated_msg = await client.get_messages('QuizBot', ids=msg.id)
        attempts = 0
        while not updated_msg.poll.results.results and attempts < 10:
            await asyncio.sleep(1)
            updated_msg = await client.get_messages('QuizBot', ids=msg.id)
            attempts += 1

        if not updated_msg.poll.results.results:
            logging.warning("No poll results received after retries")
            if local_target:
                await client.send_message(local_target, "Error: No poll results received")
            return

        correct_option = None
        for res in updated_msg.poll.results.results:
            if res.correct:
                correct_option = res.option
                break

        if correct_option is None:
            logging.error("No correct option found in poll results")
            if local_target:
                await client.send_message(local_target, "No correct option found in poll results")
            return

        original_poll = updated_msg.poll.poll
        question_text = original_poll.question.text
        logging.info(f"Original question: {question_text}")

        original_entities = original_poll.question.entities or []
        twe_original = types.TextWithEntities(text=question_text, entities=original_entities)

        # First, remove emojis preserving entities
        twe_no_emoji = remove_emojis_preserve_entities(twe_original)

        # Remove all numbering patterns like [11/70], [2/70], 11/70, Question 8 of 89, etc.
        number_pattern = re.compile(
            r'^(?:\[?\s*\d+\s*(?:of|\/)\s*\d+\s*\]?\s*[.:]?\s*|Question\s+\d+\s*(?:of|\/)\s*\d+\s*[.:]?\s*|\(\s*\d+\s*/\s*\d+\s*\)\s*|Q\s*\d+\s*[.:]?\s*)',
            re.IGNORECASE
        )
        total_prefix_len = 0
        current_text = twe_no_emoji.text
        while True:
            match = number_pattern.match(current_text)
            if not match:
                break
            prefix_len = match.end()
            total_prefix_len += prefix_len
            current_text = current_text[prefix_len:]

        # Adjust entities after removing all prefixes
        adjusted_entities = []
        for entity in twe_no_emoji.entities:
            old_start = entity.offset
            old_end = old_start + entity.length
            if old_start >= total_prefix_len:
                new_start = old_start - total_prefix_len
                new_length = entity.length
                new_entity = type(entity)(
                    offset=new_start,
                    length=new_length,
                    **{k: v for k, v in entity.__dict__.items() if k not in ['offset', 'length']}
                )
                adjusted_entities.append(new_entity)
            elif old_end > total_prefix_len:
                # Clip if overlapping prefix
                overlap = total_prefix_len - old_start
                new_start = 0
                new_length = entity.length - overlap
                if new_length > 0:
                    new_entity = type(entity)(
                        offset=new_start,
                        length=new_length,
                        **{k: v for k, v in entity.__dict__.items() if k not in ['offset', 'length']}
                    )
                    adjusted_entities.append(new_entity)

        question = types.TextWithEntities(
            text=current_text,
            entities=adjusted_entities
        )
        logging.info(f"Cleaned question: {question.text}")

        # Clean answers: remove emojis, preserve entities
        answers = []
        for ans in original_poll.answers:
            if ans.text is not None:
                clean_twe = remove_emojis_preserve_entities(ans.text)
                answers.append(types.PollAnswer(text=clean_twe, option=ans.option))
            else:
                logging.warning("Poll answer text is None")
                continue

        # Create a quiz poll
        poll = types.Poll(
            id=int(time.time()),
            question=question,
            answers=answers,
            public_voters=False,  # Ensures anonymous poll
            multiple_choice=False,
            quiz=True
        )

        # Create InputMediaPoll with quiz fields
        media_kwargs = {
            'poll': poll,
            'correct_answers': [correct_option]
        }
        media = types.InputMediaPoll(**media_kwargs)

        try:
            logging.info(f"Sending quiz poll to chat {local_target}")
            sent_msg = await client.send_message(local_target, file=media)
            logging.info("Quiz poll sent successfully")

            await asyncio.sleep(1)  # Brief wait for poll to process

            # Create closed poll
            closed_poll = types.Poll(
                id=poll.id,
                question=question,
                answers=answers,
                public_voters=False,
                multiple_choice=False,
                quiz=True,
                closed=True
            )

            closed_media_kwargs = {
                'poll': closed_poll,
                'correct_answers': [correct_option]
            }
            closed_media = types.InputMediaPoll(**closed_media_kwargs)

            # Edit the message to close the poll
            await client(functions.messages.EditMessageRequest(
                peer=local_target,
                id=sent_msg.id,
                media=closed_media
            ))
            logging.info("Edited the poll to close it")

        except Exception as e:
            logging.error(f"Failed to send or close poll: {str(e)}")
            if local_target:
                await client.send_message(local_target, f"Error sending poll: {str(e)}")
            return

with client:
    client.run_until_disconnected()