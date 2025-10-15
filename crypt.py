import asyncio
import logging
import json
import os
import time
import re
import html
import sys
import io
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telethon import TelegramClient, events
from pyrogram import Client

# ==================== CONFIGURATION - REPLACE ALL VALUES ====================
BOT_TOKEN = "8402664705:AAFdeu1-W7_NHr23-cfCNMwALbpvcCDOiDg"                    # Replace with Bot A token
API_ID = 20192130                                 # Replace with your API ID
API_HASH = "00344f6d993dfa9cd8ce6ec535a10394"                   # Replace with your API hash
ADMIN_ID = 7566173874                              # Replace with admin user ID

# Channel Configuration (use group IDs)
INCOMING_CHANNEL = -1003143869046                 # Replace with incoming group ID
OUTGOING_CHANNEL = -1003130766459                 # Replace with outgoing group ID
ENCRYPTION_BOT = "@android_protect_bot"           # Replace with Bot B username

# Bot Settings
BATCH_DELAY_SECONDS = 2                           # Delay before processing batch
PROCESSING_DELAY = 5                              # Simulated processing time

# Initialize batch tracker
current_processing_batch = None


# ==================== END CONFIGURATION ====================

class color:
    BOLD = '\033[1m'
    BRIGHT_RED = BOLD + '\033[38;2;255;50;50m'
    DARK_RED = BOLD + '\033[38;2;180;0;0m'
    PURPLE = BOLD + '\033[38;2;180;0;255m'
    MATRIX_GREEN = BOLD + '\033[38;2;0;255;70m'
    WHITE = BOLD + '\033[37m'
    RED = BOLD + '\033[91m'
    GRAY = BOLD + '\033[90m'
    DARK_BG = '\033[48;5;232m'
    DARKER_RED_BG = '\033[48;5;52m'
    YELLOW = BOLD + '\033[93m'
    CYAN = BOLD + '\033[96m'
    BLUE = BOLD + '\033[94m'
    MAGENTA = BOLD + '\033[95m'
    RESET = '\033[0m'

ASCII_ART = f"""
{color.DARK_BG}{color.BRIGHT_RED}
░██████╗████████╗██████╗░░█████╗░███╗░░██╗░██████╗░███████╗
██╔════╝╚══██╔══╝██╔══██╗██╔══██╗████╗░██║██╔════╝░██╔════╝
╚█████╗░░░░██║░░░██████╔╝███████║██╔██╗██║██║░░██╗░█████╗░░
░╚═══██╗░░░██║░░░██╔══██╗██╔══██║██║╚████║██║░░╚██╗██╔══╝░░
██████╔╝░░░██║░░░██║░░██║██║░░██║██║░╚███║╚██████╔╝███████╗
╚═════╝░░░░╚═╝░░░╚═╝░░╚═╝╚═╝░░╚═╝╚═╝░░╚══╝░╚═════╝░╚══════╝

{color.DARKER_RED_BG}{color.WHITE}╚════════════════════Made by @STRANGE_MALWARE2════════════════════╝{color.RESET}
"""

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')




# ====== RESET QUEUE HELPER ======
def reset_processing_state():
    """Clear any leftover batch and reset current processing state."""
    global current_processing_batch
    current_processing_batch = None
    try:
        data = {}
        with open("active_batches.json", "w") as f:
            json.dump(data, f)
        print("🧹 Queue reset successfully.")
    except Exception as e:
        print("❌ Failed to reset queue:", e)
# ================================

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(ASCII_ART)

def cleanup_corrupted_sessions():
    session_files = [
        "user_session.session", "user_session.session-journal", 
        "pyrogram_bot_mode.session", "pyrogram_bot_mode.session-journal"
    ]
    
    for file in session_files:
        try:
            if os.path.exists(file):
                os.remove(file)
                print(f"{color.YELLOW}🗑️ Removed corrupted session: {file}{color.RESET}")
        except Exception as e:
            print(f"{color.RED}❌ Error removing {file}: {e}{color.RESET}")

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'ERROR': color.BRIGHT_RED,
        'PROCESS': color.MATRIX_GREEN,
        'WARNING': color.YELLOW,
        'CRITICAL': color.DARK_RED
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, color.WHITE)
        record.levelname = f"{log_color}{record.levelname}{color.RESET}"
        record.msg = f"{log_color}{record.msg}{color.RESET}"
        return super().format(record)

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)
    
    logging.addLevelName(25, 'PROCESS')
    def process(self, message, *args, **kwargs):
        if self.isEnabledFor(25):
            self._log(25, message, args, **kwargs)
    logging.Logger.process = process
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setLevel(logging.WARNING)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logging.getLogger(__name__)

DATA_DIR = "user_data"
SUBSCRIPTIONS_FILE = "subscriptions.json"
PENDING_APPROVALS_FILE = "pending_approvals.json"
PROCESSING_FILES_FILE = "processing_files.json"
ACTIVE_BATCHES_FILE = "active_batches.json"
QUEUE_FILE = "queue.json"
MESSAGE_LINKS_FILE = "message_links.json"
STORED_QUEUE_FILES = "stored_queue_files.json"
SUBMISSION_COUNTER_FILE = "submission_counter.json"

os.makedirs(DATA_DIR, exist_ok=True)

user_file_batches = {}
admin_states = {}
bot_instance = None
user_client = None
pyrogram_client = None
bot_a_reference_ids = set()
processing_queue = []
current_processing_batch = None
message_links_for_forwarding = {}
stored_queue_files = {}
user_submission_messages = {}

logger = setup_logging()

def load_submission_counter():
    try:
        filepath = os.path.join(DATA_DIR, SUBMISSION_COUNTER_FILE)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                return data.get('counter', 1000)
        return 1000
    except Exception as e:
        logger.error(f"Error loading submission counter: {e}")
        return 1000

def save_submission_counter(counter):
    try:
        filepath = os.path.join(DATA_DIR, SUBMISSION_COUNTER_FILE)
        with open(filepath, 'w') as f:
            json.dump({'counter': counter}, f)
    except Exception as e:
        logger.error(f"Error saving submission counter: {e}")

def generate_submission_id():
    counter = load_submission_counter()
    counter += 1
    save_submission_counter(counter)
    return counter

def load_stored_queue_files():
    global stored_queue_files
    try:
        filepath = os.path.join(DATA_DIR, STORED_QUEUE_FILES)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                stored_queue_files = json.load(f)
    except Exception as e:
        logger.error(f"Error loading stored queue files: {e}")

def save_stored_queue_files():
    try:
        filepath = os.path.join(DATA_DIR, STORED_QUEUE_FILES)
        with open(filepath, 'w') as f:
            json.dump(stored_queue_files, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving stored queue files: {e}")

def store_queue_file(ref_id, message_id, file_number, total_files):
    global stored_queue_files
    
    if ref_id not in stored_queue_files:
        stored_queue_files[ref_id] = {
            'total_files': total_files,
            'files': [],
            'stored_at': time.time()
        }
    
    stored_queue_files[ref_id]['files'].append({
        'message_id': message_id,
        'file_number': file_number
    })
    
    save_stored_queue_files()
    print(f"{color.PURPLE}📦 STORED queue file for REF {ref_id}: Message {message_id} (file {file_number}/{total_files}){color.RESET}")

def load_message_links():
    global message_links_for_forwarding
    try:
        filepath = os.path.join(DATA_DIR, MESSAGE_LINKS_FILE)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                message_links_for_forwarding = json.load(f)
    except Exception as e:
        logger.error(f"Error loading message links: {e}")

def save_message_links():
    try:
        filepath = os.path.join(DATA_DIR, MESSAGE_LINKS_FILE)
        with open(filepath, 'w') as f:
            json.dump(message_links_for_forwarding, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving message links: {e}")

def add_message_link_for_forwarding(ref_id, chat_username, message_id, user_id, total_files, current_file):
    global message_links_for_forwarding
    
    if ref_id not in message_links_for_forwarding:
        message_links_for_forwarding[ref_id] = {
            'user_id': user_id,
            'total_files': total_files,
            'messages': [],
            'created_at': time.time()
        }
    
    message_links_for_forwarding[ref_id]['messages'].append({
        'chat_username': chat_username,
        'message_id': message_id,
        'file_number': current_file
    })
    
    save_message_links()

def load_queue():
    global processing_queue, current_processing_batch
    processing_queue = []
    current_processing_batch = None
    save_queue()

def save_queue():
    try:
        filepath = os.path.join(DATA_DIR, "queue.json")
        queue_data = {
            'queue': processing_queue,
            'current': current_processing_batch
        }
        with open(filepath, 'w') as f:
            json.dump(queue_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving queue: {e}")

def get_queue_position(batch_ref_id):
    global processing_queue, current_processing_batch
    
    if current_processing_batch == batch_ref_id:
        return 0
    
    for i, batch in enumerate(processing_queue):
        if batch['batch_ref_id'] == batch_ref_id:
            return i + 1
    
    return -1

def add_to_queue(batch_ref_id, user_id, file_count, submission_id):
    global processing_queue, current_processing_batch
    
    if current_processing_batch is None:
        current_processing_batch = batch_ref_id
        print(f"{color.MATRIX_GREEN}🚀 QUEUE: Starting immediate processing for {batch_ref_id} (Submission {submission_id}){color.RESET}")
        save_queue()
        return 0
    else:
        processing_queue.append({
            'batch_ref_id': batch_ref_id,
            'user_id': user_id,
            'file_count': file_count,
            'submission_id': submission_id,
            'queued_at': time.time()
        })
        queue_position = len(processing_queue)
        print(f"{color.YELLOW}📋 QUEUE: Added {batch_ref_id} (Submission {submission_id}) to queue (position: {queue_position}){color.RESET}")
        save_queue()
        return queue_position

async def update_queue_positions():
    global processing_queue, user_submission_messages, bot_instance
    
    for i, batch in enumerate(processing_queue):
        batch_ref_id = batch['batch_ref_id']
        user_id = batch['user_id']
        submission_id = batch['submission_id']
        new_position = i + 1
        
        if user_id in user_submission_messages and batch_ref_id in user_submission_messages[user_id]:
            try:
                message_id = user_submission_messages[user_id][batch_ref_id]
                
                if new_position == 1:
                    update_text = f"Submission ID: {submission_id}\nQueue position: {new_position}\nYou are next in queue. Please wait."
                else:
                    update_text = f"Submission ID: {submission_id}\nQueue position: {new_position}\nYou are in the queue. Please wait for your turn."
                
                await bot_instance.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=update_text
                )
            except Exception as e:
                logger.error(f"Error updating queue position for user {user_id}: {e}")

def finish_current_batch():
    global processing_queue, current_processing_batch
    
    finished_batch = current_processing_batch
    current_processing_batch = None
    
    if processing_queue:
        next_batch = processing_queue.pop(0)
        current_processing_batch = next_batch['batch_ref_id']
        print(f"{color.CYAN}🔄 QUEUE: Finished {finished_batch}, starting {current_processing_batch}{color.RESET}")
        save_queue()
        
        asyncio.create_task(start_processing_next_batch(next_batch))
        asyncio.create_task(update_queue_positions())
        
        return next_batch
    else:
        print(f"{color.MATRIX_GREEN}✅ QUEUE: Finished {finished_batch}, queue empty{color.RESET}")
        save_queue()
        return None

async def start_processing_next_batch(next_batch):
    try:
        batch_ref_id = next_batch['batch_ref_id']
        user_id = next_batch['user_id']
        file_count = next_batch['file_count']
        submission_id = next_batch['submission_id']
        
        print(f"{color.CYAN}🔄 QUEUE: Starting to process queued batch {batch_ref_id} (Submission {submission_id}){color.RESET}")
        
        if user_id in user_submission_messages and batch_ref_id in user_submission_messages[user_id]:
            try:
                message_id = user_submission_messages[user_id][batch_ref_id]
                await bot_instance.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=f"Submission ID: {submission_id}\nQueue position: 0\nYour APK is currently being processed."
                )
            except Exception as e:
                logger.error(f"Error updating processing message: {e}")
        
        await process_stored_queue_files(batch_ref_id)
        
    except Exception as e:
        logger.error(f"Error starting next batch processing: {e}")

async def process_stored_queue_files(batch_ref_id):
    try:
        global stored_queue_files, user_client
        
        if batch_ref_id not in stored_queue_files:
            return
        
        stored_data = stored_queue_files[batch_ref_id]
        files = stored_data['files']
        
        print(f"{color.PURPLE}📦 Processing {len(files)} stored queue files for {batch_ref_id}{color.RESET}")
        
        incoming_entity = await user_client.get_entity(INCOMING_CHANNEL)
        encryption_entity = await user_client.get_entity(ENCRYPTION_BOT)
        
        for file_info in files:
            message_id = file_info['message_id']
            try:
                message = await user_client.get_messages(incoming_entity, ids=message_id)
                if message and message.media:
                    print(f"{color.BLUE}📤 FORWARDING stored file to Bot B: {message_id}{color.RESET}")
                    await user_client.send_file(encryption_entity, message.media)
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error processing stored file {message_id}: {e}")
        
        del stored_queue_files[batch_ref_id]
        save_stored_queue_files()
        
    except Exception as e:
        logger.error(f"Error processing stored queue files: {e}")

def generate_batch_reference_id(user_id):
    timestamp = int(time.time())
    batch_ref_id = f"REF_{timestamp}_{user_id}"
    return batch_ref_id

def load_bot_a_reference_ids():
    global bot_a_reference_ids
    try:
        filepath = os.path.join(DATA_DIR, "bot_a_refs.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                ref_list = json.load(f)
                bot_a_reference_ids = set(ref_list)
    except Exception as e:
        logger.error(f"Error loading Bot A reference IDs: {e}")

def save_bot_a_reference_ids():
    try:
        filepath = os.path.join(DATA_DIR, "bot_a_refs.json")
        with open(filepath, 'w') as f:
            json.dump(list(bot_a_reference_ids), f)
    except Exception as e:
        logger.error(f"Error saving Bot A reference IDs: {e}")

def add_bot_a_reference_id(ref_id):
    global bot_a_reference_ids
    bot_a_reference_ids.add(ref_id)
    save_bot_a_reference_ids()

def extract_reference_id_from_caption(caption):
    if not caption:
        return None
    
    match = re.search(r'REF_\d+_\d+', caption)
    if match:
        return match.group()
    return None

def extract_submission_id_from_caption(caption):
    if not caption:
        return None
    
    match = re.search(r'Submission ID: (\d+)', caption)
    if match:
        return match.group(1)
    return None

def is_apk_file(message):
    if message.document:
        file_name = message.document.file_name
        if file_name and file_name.lower().endswith('.apk'):
            return True
    return False

def load_data(filename):
    try:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump({}, f)
            return {}
        with open(filepath, 'r') as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return {}

def save_data(filename, data):
    try:
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

def load_subscriptions():
    return load_data(SUBSCRIPTIONS_FILE)

def save_subscriptions(data):
    save_data(SUBSCRIPTIONS_FILE, data)

def load_pending_approvals():
    return load_data(PENDING_APPROVALS_FILE)

def save_pending_approvals(data):
    save_data(PENDING_APPROVALS_FILE, data)

def load_processing_files():
    return load_data(PROCESSING_FILES_FILE)

def save_processing_files(data):
    save_data(PROCESSING_FILES_FILE, data)

def load_active_batches():
    return load_data(ACTIVE_BATCHES_FILE)

def save_active_batches(data):
    save_data(ACTIVE_BATCHES_FILE, data)

def is_user_subscribed(user_id):
    try:
        subscriptions = load_subscriptions()
        user_id_str = str(user_id)
        if user_id_str not in subscriptions:
            return False
        expiry_date = datetime.fromisoformat(subscriptions[user_id_str]['expiry_date'])
        return datetime.now() < expiry_date
    except Exception as e:
        logger.error(f"Error checking subscription for {user_id}: {e}")
        return False

def get_user_days_left(user_id):
    try:
        subscriptions = load_subscriptions()
        user_id_str = str(user_id)
        if user_id_str not in subscriptions:
            return 0
        expiry_date = datetime.fromisoformat(subscriptions[user_id_str]['expiry_date'])
        days_left = (expiry_date - datetime.now()).days
        return max(0, days_left)
    except Exception as e:
        logger.error(f"Error getting days left for {user_id}: {e}")
        return 0

async def setup_telethon_client():
    global user_client
    
    user_client = TelegramClient('user_session', API_ID, API_HASH)
    
    try:
        await user_client.start()
        user_me = await user_client.get_me()
        print(f"{color.MATRIX_GREEN}✅ Telethon user client: @{user_me.username}{color.RESET}")
        
        load_bot_a_reference_ids()
        load_queue()
        load_message_links()
        load_stored_queue_files()
        
        return user_client
    except Exception as e:
        logger.error(f"Telethon setup failed: {e}")
        print(f"{color.YELLOW}⚠️ Cleaning corrupted Telethon sessions...{color.RESET}")
        cleanup_corrupted_sessions()
        raise

async def setup_pyrogram_client():
    global pyrogram_client
    
    try:
        pyrogram_client = Client(
            "pyrogram_bot_mode",
            bot_token=BOT_TOKEN
        )
        
        await pyrogram_client.start()
        bot_me = await pyrogram_client.get_me()
        print(f"{color.MATRIX_GREEN}✅ Pyrogram BOT MODE: @{bot_me.username}{color.RESET}")
        
        return pyrogram_client
    except Exception as e:
        logger.error(f"Pyrogram bot mode setup failed: {e}")
        pyrogram_client = None
        print(f"{color.YELLOW}⚠️ Pyrogram failed, will use Bot API fallback{color.RESET}")
        return None

async def setup_telethon_handlers():
    """
    NOTE: changed to register handlers using user_client.add_event_handler(...) instead of
    decorator @user_client.on(...). This avoids the AttributeError when `user_client`
    is None or not available at decoration time.
    """
    global user_client, bot_instance, current_processing_batch
    
    try:
        incoming_entity = await user_client.get_entity(INCOMING_CHANNEL)
        encryption_entity = await user_client.get_entity(ENCRYPTION_BOT)
        outgoing_entity = await user_client.get_entity(OUTGOING_CHANNEL)
        print(f"{color.MATRIX_GREEN}✅ Got channel entities{color.RESET}")
    except Exception as e:
        logger.error(f"Error getting channel entities: {e}")
        return

    # Helper: error keywords to detect Protect Bot errors (case-insensitive)
    ERROR_KEYWORDS = [
        "already encrypted",
        "could not be processed",
        "error",
        "failed",
        "invalid",
        "not allowed",
        "cannot",
        "couldn't",
        "can't",
        "already protected"
    ]


    async def handle_incoming_channel(event):
        """Minimal test: prove Telethon can forward an APK."""
        try:
            # Only process if message has a document
            if not event.media:
                print("No media in message.")
                return
            doc = getattr(event.message, "document", None)
            if not doc:
                print("No document attribute.")
                return

            caption = "Test forward to Protect Bot"
            print("📦 Trying to send to Protect Bot...")

            try:
                result = await user_client.send_file(ENCRYPTION_BOT, doc, caption=caption)
                print("✅ Sent successfully:", result)
            except Exception as e:
                import traceback
                print("❌ send_file failed:", e)
                traceback.print_exc()

        except Exception as e:
            import traceback
            print("❌ handle_incoming_channel error:", e)
            traceback.print_exc()

       
   
   
   
   
   
   
   
   # ============================================================
# 🧩 Handle messages from Outgoing Channel → stop feedback loop
# ============================================================
    async def handle_outgoing_channel(event):

        """
        Prevent the Outgoing Channel from forwarding text or error messages
        back to the Protect Bot.  Only forward APK files.
        """
        try:
            # Ignore any message that has no media (text-only)
            if not event.media:
                print("🚫 Outgoing text ignored – not forwarding to Protect Bot.")
                return

        # Only allow APK documents
            doc = getattr(event.message, "document", None)
            if not doc or not getattr(doc, "mime_type", "").startswith("application/vnd.android.package-archive"):
                print("🚫 Outgoing non-APK media ignored.")
                return

            # Forward valid APKs (if you really need this direction)
            await user_client.send_file(encryption_entity, doc, caption=event.message.message or "")
            print("📤 Outgoing APK forwarded to Protect Bot.")

        except Exception as e:
            logger.error(f"handle_outgoing_channel error: {e}")

   
   
    async def handle_encryption_bot(event):
        try:
            """
            This handler now handles both:
             - media (signed APK) forwarded from Protect Bot -> forward to outgoing channel, and add message link
             - text error messages from Protect Bot -> forward the exact text to OUTGOING_CHANNEL and to the user
            """
            global current_processing_batch, bot_instance

            # Normalize message text if present
            text = None
            if event.message and getattr(event.message, 'message', None):
                text = str(event.message.message).strip()

            # If the Protect Bot sent a text error message (no media)
            if not event.media and text:
                # detect error by searching for error keywords (case-insensitive)
                t_lower = text.lower()
                is_error = any(kw in t_lower for kw in ERROR_KEYWORDS)
                
                # If it looks like an error - forward the exact text to outgoing channel and to the original user
                if is_error:
                    print(f"{color.RED}🚨 Protect Bot error detected: {text}{color.RESET}")
                    
                    # Forward to outgoing channel as a text message
                    try:
                        await user_client.send_message(outgoing_entity, text)
                        print(f"{color.YELLOW}📤 Forwarded Protect Bot error to OUTGOING channel{color.RESET}")
                    except Exception as e:
                        logger.error(f"Error forwarding Protect Bot error to outgoing channel: {e}")
                    
                    # Also send the exact text to the original user (if we can resolve the current batch)
                    try:
                        ref_id = current_processing_batch
                        if ref_id:
                            active_batches = load_active_batches()
                            batch_info = active_batches.get(ref_id, {})
                            user_id = batch_info.get('user_id')
                            submission_id = batch_info.get('submission_id', 'Unknown')
                            if user_id:
                                # send as normal bot message (use Bot A)
                                if bot_instance:
                                    try:
                                        await bot_instance.send_message(user_id, text)
                                        





                                        
                                        print(f"{color.YELLOW}📤 Forwarded Protect Bot error to user {user_id}{color.RESET}")
                                    except Exception as e:
                                        logger.error(f"Error sending error message to user {user_id}: {e}")
                                else:
                                    print(f"{color.GRAY}Bot instance not available to send direct user message{color.RESET}")
                        else:
                            print(f"{color.GRAY}No current_processing_batch to map error to user{color.RESET}")
                    except Exception as e:
                        logger.error(f"Error mapping Protect Bot error to user: {e}")

                    # ✅ CLEANUP after error text
                    # ✅ Reset after successful encryption
                  


                    
                    # Nothing else to do for text-only error
                    return

            # If message contains media (e.g., a signed APK) - process as before
            if event.media:
                print(f"{color.CYAN}📦 RECEIVED file from Bot B → forwarding to outgoing{color.RESET}")
                
                if not current_processing_batch:
                    # We cannot map to a ref id - still forward the media to outgoing channel
                    try:
                        await user_client.send_file(outgoing_entity, event.media)
                            # ✅ CLEANUP: remove finished batch so next user starts at position 1 again
                        if ref_id in active_batches:
                            del active_batches[ref_id]
                            save_active_batches(active_batches)
                            print(f"{color.YELLOW}🧹 Cleaned up finished batch {ref_id}{color.RESET}")

                    except Exception as e:
                        logger.error(f"Error forwarding media to outgoing when no current batch: {e}")
                    return
                
                ref_id = current_processing_batch
                
                active_batches = load_active_batches()
                batch_info = active_batches.get(ref_id, {})
                
                if batch_info:
                    files_received = batch_info.get('files_received', 0) + 1
                    total_files = batch_info.get('total_files', 1)
                    user_id = batch_info.get('user_id')
                    submission_id = batch_info.get('submission_id', 'Unknown')
                    
                    batch_info['files_received'] = files_received
                    active_batches[ref_id] = batch_info
                    save_active_batches(active_batches)
                    
                    print(f"{color.YELLOW}📊 REF {ref_id} (Submission {submission_id}) - File {files_received}/{total_files}{color.RESET}")
                    
                    caption = f"⚡ File {files_received}/{total_files} - Submission ID: {submission_id}"
                else:
                    files_received = 1
                    total_files = 1
                    user_id = None
                    submission_id = 'Unknown'
                    caption = f"⚡ File 1/1 - Submission ID: {submission_id}"
                
                print(f"{color.MAGENTA}📤 FORWARDING to outgoing channel: REF {ref_id}{color.RESET}")
                sent_message = await user_client.send_file(
                    outgoing_entity, 
                    event.media, 
                    caption=caption
                )
                
                # If we know the user and this ref is one of Bot A refs, add link for final forwarding
                if user_id and ref_id in bot_a_reference_ids:
                    add_message_link_for_forwarding(
                        ref_id=ref_id,
                        chat_username="private_channel",
                        message_id=sent_message.id,
                        user_id=user_id,
                        total_files=total_files,
                        current_file=files_received
                    )
                        # ✅ CLEANUP: remove finished batch so next user starts at position 0
                    if ref_id in active_batches:
                        del active_batches[ref_id]
                        save_active_batches(active_batches)
                        print(f"{color.YELLOW}🧹 Cleaned up finished batch {ref_id}{color.RESET}")

                
        except Exception as e:
            logger.error(f"ACCOUNT encryption error: {e}")

    # Register handlers using add_event_handler to avoid decoration-time problems
    print("Sending error to user...")
    print("Resetting queue now")
    reset_processing_state()
    print("Resetting done!")

        # --- Resolve chat entities once ---
    incoming_entity = await user_client.get_entity(INCOMING_CHANNEL)
    outgoing_entity = await user_client.get_entity(OUTGOING_CHANNEL)
    encryption_entity = await user_client.get_entity(ENCRYPTION_BOT)

    try:
        user_client.add_event_handler(handle_incoming_channel, events.NewMessage(chats=incoming_entity))
        user_client.add_event_handler(handle_encryption_bot, events.NewMessage(chats=encryption_entity))

        # 🆕 Detect Protect Bot messages that are edited (error re-edits)
        async def handle_encryption_bot_edit(event):
            try:
                if not event or not event.message:
                    return

                text = str(event.message.message or "").strip()
                if not text:
                    return

                # Same error keyword list as before
                ERROR_KEYWORDS = [
                    "error",
                    "could not be processed",
                    "already encrypted",
                    "can't process",
                    "disable obfuscation",
                    "invalid",
                    "failed"
                ]
                if any(kw in text.lower() for kw in ERROR_KEYWORDS):
                    print(f"{color.RED}⚠️ Protect Bot EDIT error detected: {text}{color.RESET}")

                    # Forward edited error message to outgoing channel
                    await user_client.send_message(OUTGOING_CHANNEL, text)
                            # ✅ Reset after error
                   


                    # Also forward to user (if batch active)
                    ref_id = current_processing_batch
                    if ref_id:
                        active_batches = load_active_batches()
                        batch_info = active_batches.get(ref_id, {})
                        user_id = batch_info.get("user_id")
                        if user_id and bot_instance:
                            await bot_instance.send_message(user_id, text)
                            print(f"{color.YELLOW}📤 Forwarded edited error to user {user_id}{color.RESET}")
                    # ✅ CLEANUP after error
                    # active_batches = load_active_batches()
                    # if ref_id in active_batches:
                    #     del active_batches[ref_id]
                    #     save_active_batches(active_batches)
                    #     print(f"{color.YELLOW}🧹 Cleaned up errored batch {ref_id}{color.RESET}")
                    # ✅ Reset after error
               



            except Exception as e:
                logger.error(f"Error in handle_encryption_bot_edit: {e}")
          

        # Register event handler for edits from Protect Bot
        user_client.add_event_handler(handle_encryption_bot_edit, events.MessageEdited(chats=encryption_entity))
        user_client.add_event_handler(handle_outgoing_channel, events.NewMessage(chats=outgoing_entity))
        reset_processing_state()

        print(f"{color.MATRIX_GREEN}✅ Telethon handlers registered via add_event_handler{color.RESET}")
    except Exception as e:
        logger.error(f"Error registering telethon handlers: {e}")



    
async def setup_bot_a_message_link_forwarding():
    global bot_instance, message_links_for_forwarding, pyrogram_client
    
    while True:
        try:
            await asyncio.sleep(2)
            
            completed_batches = []
            for ref_id, batch_data in message_links_for_forwarding.items():
                if len(batch_data['messages']) >= batch_data['total_files']:
                    completed_batches.append(ref_id)
            
            for ref_id in completed_batches:
                batch_data = message_links_for_forwarding[ref_id]
                user_id = batch_data['user_id']
                messages = batch_data['messages']
                total_files = batch_data['total_files']
                
                active_batches = load_active_batches()
                submission_id = active_batches.get(ref_id, {}).get('submission_id', 'Unknown')
                
                print(f"{color.BRIGHT_RED}🤖 BOT A: Forwarding batch {ref_id} (Submission {submission_id}) to user {user_id}{color.RESET}")
                
                messages.sort(key=lambda x: x['file_number'])
                
                for i, msg_info in enumerate(messages):
                    try:
                        message_id = msg_info['message_id']
                        
                        print(f"{color.BRIGHT_RED}📤 BOT A: Copying file {i+1}/{total_files} (NO FORWARD TAG){color.RESET}")
                        
                        success = False
                        if pyrogram_client:
                            try:
                                await pyrogram_client.copy_message(
                                    chat_id=user_id,
                                    from_chat_id=OUTGOING_CHANNEL,
                                    message_id=message_id
                                )
                                success = True
                            except Exception as pyrogram_error:
                                print(f"{color.YELLOW}⚠️ Pyrogram failed, using Bot API fallback{color.RESET}")
                        
                        if not success:
                            await bot_instance.copy_message(
                                chat_id=user_id,
                                from_chat_id=OUTGOING_CHANNEL,
                                message_id=message_id
                            )
                        
                        if i < total_files - 1:
                            await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"BOT A: Error forwarding file {i+1}: {e}")
                
                print(f"{color.MATRIX_GREEN}🎉 APK Crypt COMPLETE for Submission {submission_id}!{color.RESET}")
                
                try:
                    completion_message = (
                        f"🎊 <b>APK Crypt Complete!</b> 🎊\n\n"
                        f"<b>Submission ID:</b> {submission_id}\n"
                        f"<b>Total Files:</b> {total_files}\n"
                        f"<b>Completed:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"<b>Thank you for using our service!</b>"
                    )
                    await bot_instance.send_message(
                        user_id,
                        completion_message,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"BOT A: Error sending completion message: {e}")
                
                if user_id in user_submission_messages and ref_id in user_submission_messages[user_id]:
                    del user_submission_messages[user_id][ref_id]
                    if not user_submission_messages[user_id]:
                        del user_submission_messages[user_id]
                
                subscriptions = load_subscriptions()
                if str(user_id) in subscriptions:
                    subscriptions[str(user_id)]['files_converted'] += total_files
                    save_subscriptions(subscriptions)
                
                bot_a_reference_ids.discard(ref_id)
                save_bot_a_reference_ids()
                
                del message_links_for_forwarding[ref_id]
                save_message_links()
                
                active_batches = load_active_batches()
                if ref_id in active_batches:
                    del active_batches[ref_id]
                    save_active_batches(active_batches)
                
                finish_current_batch()
            
        except Exception as e:
            logger.error(f"BOT A: Forwarding error: {e}")
            await asyncio.sleep(5)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("🔔 Pending Approvals", callback_data="admin_pending")],
                [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
                [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔧 <b>Admin Panel</b> 🔧\n\n"
                "Choose an option:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        else:
            if is_user_subscribed(user_id):
                days_left = get_user_days_left(user_id)
                
                await update.message.reply_text(
                    f"🎉 <b>Welcome back!</b> 🎉\n\n"
                    f"⏰ <b>{days_left} days remaining</b>\n"
                    f"📱 <b>Send APK files for Crypt</b>\n\n"
                    f"🔥 <b>Send your APK files for processing!</b> 🔥",
                    parse_mode=ParseMode.HTML
                )
            else:
                keyboard = [
                    [InlineKeyboardButton("🔑 Request Approval", callback_data="request_approval")],
                    [InlineKeyboardButton("💬 Contact Support", url="https://t.me/Let_mee_knew")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🔐 <b>APK Crypt Bot</b> 🔐\n\n"
                    "🛡️ <b>Convert your APK files securely</b>\n\n"
                    "📱 Send APK files for Crypt\n"
                    "🔒 Your privacy is our priority\n"
                    "⚡ Fast and reliable service\n\n"
                    "🔥 <b>Request approval to get started!</b> 🔥",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        
    except Exception as e:
        logger.error(f"Error in start_command: {e}")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "request_approval":
            await handle_request_approval(update, context)
        elif data.startswith("accept_"):
            await handle_accept_user(update, context)
        elif data.startswith("decline_"):
            await handle_decline_user(update, context)
        elif data == "admin_pending":
            await handle_admin_pending(update, context)
        elif data.startswith("view_pending_"):
            await handle_view_pending_user(update, context)
        elif data == "admin_broadcast":
            await handle_admin_broadcast(update, context)
        elif data == "admin_stats":
            await handle_admin_stats(update, context)
        elif data == "admin_back":
            await handle_admin_back(update, context)
        else:
            await query.edit_message_text("❌ Unknown action.")
            
    except Exception as e:
        logger.error(f"Error in callback_query_handler: {e}")

async def handle_request_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        user = query.from_user
        
        pending = load_pending_approvals()
        if str(user_id) in pending:
            await query.edit_message_text("⏳ <b>Your approval request is already pending!</b>", parse_mode=ParseMode.HTML)
            return
        
        if is_user_subscribed(user_id):
            await query.edit_message_text("🎉 <b>You already have an active subscription!</b>", parse_mode=ParseMode.HTML)
            return
        
        user_data = {
            'user_id': user_id,
            'username': user.username or "No username",
            'first_name': user.first_name or "No name",
            'last_name': user.last_name or "",
            'request_date': datetime.now().isoformat()
        }
        
        pending[str(user_id)] = user_data
        save_pending_approvals(pending)
        
        admin_message = (
            f"🔔 <b>New Approval Request</b> 🔔\n\n"
            f"👤 <b>{html.escape(user.first_name)} {html.escape(user.last_name or '')}</b>\n"
            f"🆔 <b>User ID:</b> {user_id}\n"
            f"📱 <b>Username:</b> @{html.escape(user.username or 'None')}\n"
            f"📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"decline_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(ADMIN_ID, admin_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await query.edit_message_text("✅ <b>Request sent to admin! Please wait for approval.</b>", parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in handle_request_approval: {e}")

async def handle_accept_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        user_id = int(query.data.split("_")[1])
        admin_states[ADMIN_ID] = {'action': 'waiting_days', 'user_id': user_id}
        
        await query.edit_message_text(
            f"<b>Approving User {user_id}</b>\n\nPlease send the number of days for subscription:",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in handle_accept_user: {e}")

async def handle_decline_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        user_id = int(query.data.split("_")[1])
        
        pending = load_pending_approvals()
        if str(user_id) in pending:
            del pending[str(user_id)]
            save_pending_approvals(pending)
        
        await context.bot.send_message(user_id, "❌ <b>Your approval request has been declined.</b>", parse_mode=ParseMode.HTML)
        await query.edit_message_text(f"❌ <b>Declined User {user_id}</b>", parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in handle_decline_user: {e}")

async def handle_admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        pending = load_pending_approvals()
        
        if not pending:
            await query.edit_message_text("📝 <b>No pending approval requests.</b>", parse_mode=ParseMode.HTML)
            return
        
        buttons = []
        for user_id, user_data in pending.items():
            button_text = f"{user_data['first_name']} ({user_id})"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"view_pending_{user_id}")])
        
        buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")])
        reply_markup = InlineKeyboardMarkup(buttons)
        
        await query.edit_message_text(
            f"🔔 <b>Pending Requests ({len(pending)})</b> 🔔\n\nClick on a user to approve/decline:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in handle_admin_pending: {e}")

async def handle_view_pending_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        user_id = query.data.split("_")[-1]
        pending = load_pending_approvals()
        
        if user_id not in pending:
            await query.edit_message_text("❌ <b>User not found!</b>", parse_mode=ParseMode.HTML)
            return
        
        user_data = pending[user_id]
        message_text = (
            f"👤 <b>User Details</b>\n\n"
            f"• <b>Name:</b> {html.escape(user_data['first_name'])} {html.escape(user_data.get('last_name', ''))}\n"
            f"• <b>Username:</b> @{html.escape(user_data['username'])}\n"
            f"• <b>User ID:</b> {user_data['user_id']}\n"
            f"• <b>Request Date:</b> {user_data['request_date'][:19]}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{user_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"decline_{user_id}")
            ],
            [InlineKeyboardButton("🔙 Back to Pending", callback_data="admin_pending")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in handle_view_pending_user: {e}")

async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        admin_states[ADMIN_ID] = {'action': 'waiting_broadcast'}
        await query.edit_message_text(
            "📢 <b>Broadcast Message</b>\n\nSend the message you want to broadcast to all users:",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in handle_admin_broadcast: {e}")

async def handle_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        subscriptions = load_subscriptions()
        pending = load_pending_approvals()
        active_batches = load_active_batches()
        
        total_users = len(subscriptions)
        pending_count = len(pending)
        active_batch_count = len(active_batches)
        message_link_count = len(message_links_for_forwarding)
        stored_queue_count = len(stored_queue_files)
        active_users = sum(1 for user_data in subscriptions.values() 
                          if datetime.now() < datetime.fromisoformat(user_data['expiry_date']))
        
        total_files = sum(user_data['files_converted'] for user_data in subscriptions.values())
        
        stats_text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 <b>Total Users:</b> {total_users}\n"
            f"✅ <b>Active Subscribers:</b> {active_users}\n"
            f"🔔 <b>Pending Approvals:</b> {pending_count}\n"
            f"⏳ <b>Active Batches:</b> {active_batch_count}\n"
            f"📦 <b>Stored Queue Files:</b> {stored_queue_count}\n"
            f"📎 <b>Message Links Ready:</b> {message_link_count}\n"
            f"📁 <b>Total Files Processed:</b> {total_files}\n"
            f"🆔 <b>Bot A Reference IDs:</b> {len(bot_a_reference_ids)}\n"
            f"📋 <b>QUEUE STATUS:</b>\n"
            f"  Current Processing: {current_processing_batch or 'None'}\n"
            f"  Queue Length: {len(processing_queue)}\n"
            f"⏰ <b>Last Updated:</b> {datetime.now().strftime('%H:%M:%S')}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in handle_admin_stats: {e}")

async def handle_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ <b>Unauthorized!</b>", parse_mode=ParseMode.HTML)
            return
        
        keyboard = [
            [InlineKeyboardButton("🔔 Pending Approvals", callback_data="admin_pending")],
            [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔧 <b>Admin Panel</b> 🔧\n\n"
            "Choose an option:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in handle_admin_back: {e}")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user:
            return
            
        user_id = update.effective_user.id
        
        if user_id == ADMIN_ID and user_id in admin_states:
            state = admin_states[user_id]
            
            if state['action'] == 'waiting_days':
                try:
                    days = int(update.message.text)
                    if days <= 0:
                        await update.message.reply_text("Please enter a positive number of days.")
                        return
                    
                    pending_user_id = state['user_id']
                    subscriptions = load_subscriptions()
                    expiry_date = datetime.now() + timedelta(days=days)
                    
                    pending = load_pending_approvals()
                    user_info = pending.get(str(pending_user_id), {})
                    
                    subscriptions[str(pending_user_id)] = {
                        'user_id': pending_user_id,
                        'username': user_info.get('username', ''),
                        'first_name': user_info.get('first_name', ''),
                        'subscription_date': datetime.now().isoformat(),
                        'expiry_date': expiry_date.isoformat(),
                        'days_granted': days,
                        'files_converted': 0
                    }
                    save_subscriptions(subscriptions)
                    
                    if str(pending_user_id) in pending:
                        del pending[str(pending_user_id)]
                        save_pending_approvals(pending)
                    
                    await context.bot.send_message(
                        pending_user_id,
                        f"🎉 <b>Congratulations!</b>\n\n"
                        f"Your subscription has been approved for {days} days!\n\n"
                        f"🔥 <b>Send APK files for Crypt!</b>\n"
                        f"Type /start to begin.",
                        parse_mode=ParseMode.HTML
                    )
                    
                    await update.message.reply_text(f"✅ <b>User {pending_user_id} approved for {days} days!</b>", parse_mode=ParseMode.HTML)
                    del admin_states[user_id]
                    
                except ValueError:
                    await update.message.reply_text("Please enter a valid number.")
            
            elif state['action'] == 'waiting_broadcast':
                subscriptions = load_subscriptions()
                success = 0
                failed = 0
                
                for user_id_str in subscriptions.keys():
                    try:
                        if update.message.text:
                            await context.bot.send_message(int(user_id_str), update.message.text, parse_mode=ParseMode.HTML)
                        success += 1
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.error(f"Broadcast failed for {user_id_str}: {e}")
                        failed += 1
                
                await update.message.reply_text(
                    f"📢 <b>Broadcast Complete!</b>\n\n"
                    f"✅ <b>Successful:</b> {success}\n"
                    f"❌ <b>Failed:</b> {failed}",
                    parse_mode=ParseMode.HTML
                )
                del admin_states[user_id]
        
    except Exception as e:
        logger.error(f"Error in handle_text_messages: {e}")

async def handle_media_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user or not update.message:
            return
            
        user_id = update.effective_user.id
        username = update.effective_user.username or "NoUsername"
        first_name = update.effective_user.first_name or "NoName"
        
        if hasattr(update.message.chat, 'type') and update.message.chat.type in ['channel', 'supergroup']:
            return
        
        if not is_user_subscribed(user_id):
            await update.message.reply_text(
                "❌ <b>You need an active subscription to use this bot.</b>\n\nUse /start to request approval.",
                parse_mode=ParseMode.HTML
            )
            return
        
        if not is_apk_file(update.message):
            await update.message.reply_text("⚠️ <b>We only support APK files for Crypt.</b>")
            return
        
        print(f"{color.CYAN}📱 RECEIVED APK from user {username} ({user_id}){color.RESET}")
        
        if user_id not in user_file_batches:
            batch_ref_id = generate_batch_reference_id(user_id)
            submission_id = generate_submission_id()
            user_file_batches[user_id] = {
                'files': [],
                'batch_ref_id': batch_ref_id,
                'submission_id': submission_id,
                'timer': None,
                'user_info': f"{username} ({first_name})"
            }
        
        batch = user_file_batches[user_id]
        
        file_info = {
            'message': update.message,
            'file_type': 'apk',
            'timestamp': time.time()
        }
        
        batch['files'].append(file_info)
        file_count = len(batch['files'])
        
        if batch['timer']:
            batch['timer'].cancel()
        
        batch['timer'] = asyncio.create_task(
            process_batch(context, user_id, BATCH_DELAY_SECONDS)
        )
        
    except Exception as e:
        logger.error(f"Error in handle_media_messages: {e}")

async def process_batch(context: ContextTypes.DEFAULT_TYPE, user_id: int, delay_seconds: int):
    try:
        await asyncio.sleep(delay_seconds)
        
        if user_id not in user_file_batches:
            return
        
        batch = user_file_batches[user_id]
        file_count = len(batch['files'])
        batch_ref_id = batch['batch_ref_id']
        submission_id = batch['submission_id']
        
        print(f"{color.MATRIX_GREEN}🔄 Starting batch {batch_ref_id} (Submission {submission_id}) with {file_count} APKs{color.RESET}")
        
        submission_message = await context.bot.send_message(
            user_id,
            f"Submission ID: {submission_id}\n\nProcessing finished. Uploading... please wait."
        )
        
        if user_id not in user_submission_messages:
            user_submission_messages[user_id] = {}
        user_submission_messages[user_id][batch_ref_id] = submission_message.message_id
        
        active_batches = load_active_batches()
        active_batches[batch_ref_id] = {
            'batch_ref_id': batch_ref_id,
            'user_id': user_id,
            'user_info': batch['user_info'],
            'total_files': file_count,
            'files_received': 0,
            'submission_id': submission_id,
            'timestamp': time.time(),
            'status': 'processing'
        }
        save_active_batches(active_batches)
        
        add_bot_a_reference_id(batch_ref_id)
        
        queue_position = add_to_queue(batch_ref_id, user_id, file_count, submission_id)
        
        print(f"{color.BLUE}📤 FORWARDING batch to incoming channel: {batch_ref_id}{color.RESET}")
        await forward_batch_to_incoming(context, batch, batch_ref_id, file_count, submission_id)
        
        if queue_position == 0:
            update_text = f"Submission ID: {submission_id}\nQueue position: 0\nYour APK is currently being processed."
        else:
            update_text = f"Submission ID: {submission_id}\nQueue position: {queue_position}\nYou are in the queue. Please wait for your turn."
        
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=submission_message.message_id,
            text=update_text
        )
        
        del user_file_batches[user_id]
        
    except Exception as e:
        logger.error(f"Error in process_batch: {e}")

async def forward_batch_to_incoming(context: ContextTypes.DEFAULT_TYPE, batch, batch_ref_id, file_count, submission_id):
    try:
        success_count = 0
        
        for i, file_info in enumerate(batch['files'], 1):
            try:
                message = file_info['message']
                
                caption = f"🔄 Batch: {batch_ref_id}\n📁 File: {i}/{file_count}\n👤 User: {batch['user_info']}\n🆔 Submission ID: {submission_id}"
                
                await context.bot.send_document(
                    chat_id=INCOMING_CHANNEL,
                    document=message.document.file_id,
                    caption=caption
                )
                
                success_count += 1
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error forwarding file {i}: {e}")
        
    except Exception as e:
        logger.error(f"Error in forward_batch_to_incoming: {e}")

def main():
    try:
        clear_screen()
        
        print(f"{color.MATRIX_GREEN}🚀 APK Crypt Bot A Started!{color.RESET}")
        print(f"{color.CYAN}🤖 Bot Token: {BOT_TOKEN[:20]}...{color.RESET}")
        print(f"{color.YELLOW}🔥 Starting Telethon + Pyrogram hybrid...{color.RESET}")
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CallbackQueryHandler(callback_query_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
        application.add_handler(MessageHandler(filters.ATTACHMENT, handle_media_messages))
        
        async def async_main():
            load_subscriptions()
            load_pending_approvals()
            load_processing_files()
            load_active_batches()
            
            await setup_telethon_client()
            await setup_telethon_handlers()
            await setup_pyrogram_client()
            
            global bot_instance
            bot_instance = application.bot
            
            asyncio.create_task(setup_bot_a_message_link_forwarding())
            
            print(f"\n{color.MATRIX_GREEN}🎉 APK Crypt System Active... Press Ctrl+C to stop{color.RESET}")
            print(f"{color.CYAN}🔧 Telethon: Main operations{color.RESET}")
            if pyrogram_client:
                print(f"{color.PURPLE}🤖 Pyrogram: Bot A forwarding (no forward tags){color.RESET}\n")
            else:
                print(f"{color.YELLOW}🤖 Bot API: Bot A forwarding (copy_message){color.RESET}\n")
            
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            
            await asyncio.Event().wait()
        
        asyncio.run(async_main())
        
    except KeyboardInterrupt:
        print(f"\n{color.BRIGHT_RED}🛑 Bot stopped by user{color.RESET}")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
