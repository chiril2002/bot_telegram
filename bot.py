import logging
import json
import uuid
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
import os

# Configurare logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Stări pentru ConversationHandler
(
    CHOOSE_CATEGORY,
    CHOOSE_PRODUCT,
    PRODUCT_DETAILS,
    ADD_TO_CART,
    CHECKOUT_NAME,
    CHECKOUT_PHONE,
    CHECKOUT_ADDRESS,
    CHECKOUT_EMAIL,
    CONFIRM_ORDER,
) = range(9)

# Simulăm o bază de date sqlite3 cu produse
# Conexiune la baza de date SQLite
def get_db_connection():
    conn = sqlite3.connect("cosmetics.db")
    conn.row_factory = sqlite3.Row
    return conn

# Obține lista de categorii distincte
def get_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories")
    categories = [row["name"] for row in cur.fetchall()]
    conn.close()
    return categories

# Obține toate produsele dintr-o categorie
def get_products_by_category(category_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.* FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE c.name = ?
    """, (category_name,))
    products = [dict(row) for row in cur.fetchall()]
    conn.close()
    return products

# Obține un produs după ID
def get_product_by_id(product_id: int) -> dict:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# Exemplu pentru best-sellers: primele id-uri din fiecare categorie
def get_best_sellers():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT MIN(p.id) as id
        FROM products p
        JOIN categories c ON p.category_id = c.id
        GROUP BY p.category_id
    """)
    best_sellers = [row["id"] for row in cur.fetchall()]
    conn.close()
    return best_sellers

# Simulăm best-sellers
BEST_SELLERS = get_best_sellers()

# Coșul de cumpărături (stocat în context.user_data)
def get_cart(context) -> dict:
    return context.user_data.get("cart", {})

def save_cart(context, cart: dict):
    context.user_data["cart"] = cart


def format_product(product: dict) -> str:
    return f"**{product['name']}**\nPreț: {product['price']} RON\nDescriere: {product['description']}\nStoc: {product['stock']} buc."

# Meniul principal
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍️ Produse", callback_data="products")],
        [InlineKeyboardButton("🔥 Promoții", callback_data="promotions")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")],
        [InlineKeyboardButton("🛒 Coșul meu", callback_data="cart")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.reply_text(
            "Bună! Bine ai venit la magazinul nostru de cosmetice! 💄\nCe dorești să faci astăzi?",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(
            "Bună! Bine ai venit la magazinul nostru de cosmetice! 💄\nCe dorești să faci astăzi?",
            reply_markup=reply_markup,
        )
    return CHOOSE_CATEGORY

# Gestionarea butoanelor din meniu
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "products":
        categories = get_categories()
        keyboard = [
            [InlineKeyboardButton(category.title(), callback_data=f"category_{category}")]
            for category in categories
        ]
        keyboard.append([InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Alege o categorie:", reply_markup=reply_markup)
        return CHOOSE_CATEGORY

    elif query.data == "promotions":
        keyboard = [[InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("🔥 **Promoții speciale**:\nMomentan nu avem promoții active. Verifică mai târziu!", reply_markup=reply_markup)
        return CHOOSE_CATEGORY

    elif query.data == "contact":
        keyboard = [[InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("📞 **Contact**:\nEmail: contact@magazin-cosmetice.ro\nTelefon: 0722 123 456", reply_markup=reply_markup)
        return CHOOSE_CATEGORY

    elif query.data == "cart":
        cart = get_cart(context)
        keyboard = [[InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if not cart:
            await query.message.reply_text("Coșul tău este gol! 🛒", reply_markup=reply_markup)
        else:
            total = 0
            response = "🛒 **Coșul tău**:\n"
            for product_id, quantity in cart.items():
                product = get_product_by_id(product_id)
                if product:
                    subtotal = product["price"] * quantity
                    total += subtotal
                    response += f"{product['name']} x{quantity}: {subtotal} RON\n"
            response += f"\n**Total**: {total} RON"
            keyboard = [
                [InlineKeyboardButton("Finalizează comanda", callback_data="checkout")],
                [InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(response, reply_markup=reply_markup)
        return CHOOSE_CATEGORY

    elif query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY

    return CHOOSE_CATEGORY

# Afișarea produselor dintr-o categorie
async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY
    category = query.data.replace("category_", "")
    categories = get_categories()
    if category in categories:
        context.user_data["current_category"] = category
        products = get_products_by_category(category)
        keyboard = [
            [InlineKeyboardButton(product["name"], callback_data=f"product_{product['id']}")]
            for product in products
        ]
        keyboard.append([InlineKeyboardButton("Înapoi la categorii", callback_data="back_to_products")])
        keyboard.append([InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(f"Produse din categoria **{category.title()}**:", reply_markup=reply_markup)
        return CHOOSE_PRODUCT
    return CHOOSE_CATEGORY

# Detalii despre produs
async def product_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_products":
        category = context.user_data.get("current_category", "")
        products = get_products_by_category(category)
        if products:
            keyboard = [
                [InlineKeyboardButton(product["name"], callback_data=f"product_{product['id']}")]
                for product in products
            ]
            keyboard.append([InlineKeyboardButton("Înapoi la categorii", callback_data="back_to_products")])
            keyboard.append([InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"Produse din categoria **{category.title()}**:", reply_markup=reply_markup)
            return CHOOSE_PRODUCT
        return CHOOSE_CATEGORY
    elif query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY
    product_id = int(query.data.replace("product_", ""))
    product = get_product_by_id(product_id)
    if product:
        await query.message.reply_photo(
            photo=product["image"],
            caption=format_product(product),
            parse_mode="Markdown",
        )
        keyboard = [
            [InlineKeyboardButton("Adaugă în coș", callback_data=f"add_to_cart_{product_id}")],
            [InlineKeyboardButton("Înapoi la categorie", callback_data="back_to_products")],
            [InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Sugestii de produse asemănătoare sau best-sellers
        suggestions = [p for p in BEST_SELLERS if p != product_id][:2]
        if suggestions:
            suggestion_text = "\n\n**Îți recomandăm și:**\n"
            for sug_id in suggestions:
                sug_product = get_product_by_id(sug_id)
                suggestion_text += f"- {sug_product['name']} ({sug_product['price']} RON)\n"
            await query.message.reply_text(suggestion_text, reply_markup=reply_markup)
        else:
            await query.message.reply_text("Ce mai dorești să faci?", reply_markup=reply_markup)
        return PRODUCT_DETAILS
    return CHOOSE_CATEGORY

# Adăugare în coș
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_products":
        category = context.user_data.get("current_category", "")
        products = get_products_by_category(category)  # <-- folosește baza de date
        if products:
            keyboard = [
                [InlineKeyboardButton(product["name"], callback_data=f"product_{product['id']}")]
                for product in products
            ]
            keyboard.append([InlineKeyboardButton("Înapoi la categorii", callback_data="back_to_products")])
            keyboard.append([InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(f"Produse din categoria **{category.title()}**:", reply_markup=reply_markup)
            return CHOOSE_PRODUCT
        return CHOOSE_CATEGORY
    elif query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY
    product_id = int(query.data.replace("add_to_cart_", ""))
    product = get_product_by_id(product_id)
    if product and product["stock"] > 0:
        cart = get_cart(context)  # <-- modificat aici
        cart[product_id] = cart.get(product_id, 0) + 1
        save_cart(context, cart)  # <-- modificat aici
        await query.message.reply_text(f"{product['name']} a fost adăugat în coș! 🛒")
    else:
        await query.message.reply_text("Ne pare rău, acest produs nu este în stoc.")
    keyboard = [
        [InlineKeyboardButton("Vezi coșul", callback_data="cart")],
        [InlineKeyboardButton("Înapoi la categorie", callback_data="back_to_products")],
        [InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Ce mai dorești să faci?", reply_markup=reply_markup)
    return ADD_TO_CART

# Procesul de finalizare a comenzii
async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY
    cart = get_cart(context)
    if not cart:
        keyboard = [[InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Coșul tău este gol! 🛒", reply_markup=reply_markup)
        return CHOOSE_CATEGORY
    await query.message.reply_text("Te rugăm să ne spui numele tău:")
    return CHECKOUT_NAME

async def checkout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"] = {"name": update.message.text}
    await update.message.reply_text("Numărul tău de telefon:")
    return CHECKOUT_PHONE

async def checkout_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["phone"] = update.message.text
    await update.message.reply_text("Adresa de livrare:")
    return CHECKOUT_ADDRESS

async def checkout_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["address"] = update.message.text
    await update.message.reply_text("Emailul tău (opțional, apasă /skip pentru a sări):")
    return CHECKOUT_EMAIL

async def checkout_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data["order"]["email"] = update.message.text
    else:
        context.user_data["order"]["email"] = ""
    cart = get_cart(context)
    order_details = "📦 **Comanda ta**:\n"
    total = 0
    for product_id, quantity in cart.items():
        product = get_product_by_id(product_id)
        subtotal = product["price"] * quantity
        total += subtotal
        order_details += f"{product['name']} x{quantity}: {subtotal} RON\n"
    order_details += f"\n**Total**: {total} RON\n"
    order_details += f"\n**Detalii client**:\nNume: {context.user_data['order']['name']}\nTelefon: {context.user_data['order']['phone']}\nAdresă: {context.user_data['order']['address']}\nEmail: {context.user_data['order']['email'] or 'Nefurnizat'}"
    keyboard = [
        [InlineKeyboardButton("Confirmă comanda", callback_data="confirm_order")],
        [InlineKeyboardButton("Anulează", callback_data="cancel_order")],
        [InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(order_details, reply_markup=reply_markup, parse_mode="Markdown")
    return CONFIRM_ORDER

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY
    
    # Construim mesajul pentru admin
    cart = get_cart(context)
    order_id = str(uuid.uuid4())
    order_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    order_details = f"📦 **Comandă nouă (ID: {order_id})** ({order_time}):\n"
    total = 0
    for product_id, quantity in cart.items():
        product = get_product_by_id(product_id)
        subtotal = product["price"] * quantity
        total += subtotal
        order_details += f"{product['name']} x{quantity}: {subtotal} RON\n"
    order_details += f"\n**Total**: {total} RON\n"
    order_details += f"\n**Detalii client**:\nNume: {context.user_data['order']['name']}\nTelefon: {context.user_data['order']['phone']}\nAdresă: {context.user_data['order']['address']}\nEmail: {context.user_data['order']['email'] or 'Nefurnizat'}"
    
    # Trimitem comanda către chatul adminului
    try:
        chat_id = int(os.getenv("ADMIN_CHAT_ID"))
        await context.bot.send_message(
             chat_id=chat_id,
             text=order_details,
             parse_mode="Markdown"
        ) 
        
        await query.message.reply_text("Comanda ta a fost plasată cu succes! 🎉 Îți mulțumim!")
    except Exception as e:
        logger.error(f"Eroare la trimiterea comenzii către admin: {e}")
        await query.message.reply_text("Am întâmpinat o problemă la procesarea comenzii. Te rugăm să încerci din nou mai târziu.")
        return CHOOSE_CATEGORY

    # Golește coșul și detaliile comenzii
    context.user_data["cart"] = {}
    context.user_data["order"] = {}
    await start(update, context)
    return CHOOSE_CATEGORY

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_menu":
        await start(update, context)
        return CHOOSE_CATEGORY
    await query.message.reply_text("Comanda a fost anulată.")
    await start(update, context)
    return CHOOSE_CATEGORY

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["email"] = ""
    cart = get_cart(context)
    order_details = "📦 **Comanda ta**:\n"
    total = 0
    for product_id, quantity in cart.items():
        product = get_product_by_id(product_id)
        subtotal = product["price"] * quantity
        total += subtotal
        order_details += f"{product['name']} x{quantity}: {subtotal} RON\n"
    order_details += f"\n**Total**: {total} RON\n"
    order_details += (
        f"\n**Detalii client**:\n"
        f"Nume: {context.user_data['order']['name']}\n"
        f"Telefon: {context.user_data['order']['phone']}\n"
        f"Adresă: {context.user_data['order']['address']}\n"
        f"Email: Nefurnizat"
    )
    keyboard = [
        [InlineKeyboardButton("Confirmă comanda", callback_data="confirm_order")],
        [InlineKeyboardButton("Anulează", callback_data="cancel_order")],
        [InlineKeyboardButton("Înapoi la meniu", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(order_details, reply_markup=reply_markup, parse_mode="Markdown")
    return CONFIRM_ORDER
# Gestionarea erorilor
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update.message:
        await update.message.reply_text("A apărut o eroare. Te rugăm să încerci din nou.")
    elif update.callback_query:
        await update.callback_query.message.reply_text("A apărut o eroare. Te rugăm să încerci din nou.")

def main():
    # Încarcă variabilele din fișierul .env
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("Eroare: BOT_TOKEN nu este setat în fișierul .env")
        return
    if not os.getenv("ADMIN_CHAT_ID"):
        logger.error("Eroare: ADMIN_CHAT_ID nu este setat în fișierul .env")
        return

    # Inițializează aplicația cu token-ul din .env
    application = Application.builder().token(bot_token).build()

    # ConversationHandler pentru fluxul de comandă
    conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start), CallbackQueryHandler(button)],
    states={
        CHOOSE_CATEGORY: [
            CallbackQueryHandler(choose_category, pattern="^category_|^back_to_menu$"),
            CallbackQueryHandler(checkout, pattern="^checkout$"),  # <-- Adaugă această linie!
            CallbackQueryHandler(button, pattern="^products$|^promotions$|^contact$|^cart$|^back_to_menu$")
        ],
        CHOOSE_PRODUCT: [
            CallbackQueryHandler(product_details, pattern="^product_|^back_to_products$|^back_to_menu$"),
            CallbackQueryHandler(button, pattern="^products$|^back_to_menu$")
        ],
        PRODUCT_DETAILS: [
            CallbackQueryHandler(add_to_cart, pattern="^add_to_cart_|^back_to_products$|^back_to_menu$"),
            CallbackQueryHandler(product_details, pattern="^back_to_products$|^back_to_menu$")
        ],
        ADD_TO_CART: [
            CallbackQueryHandler(button, pattern="^cart$|^back_to_menu$"),
            CallbackQueryHandler(add_to_cart, pattern="^back_to_products$|^back_to_menu$")
        ],
        CHECKOUT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_name)],
        CHECKOUT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_phone)],
        CHECKOUT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_address)],
        CHECKOUT_EMAIL: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_email),
            CommandHandler("skip", skip),
        ],
        CONFIRM_ORDER: [
            CallbackQueryHandler(confirm_order, pattern="^confirm_order$|^back_to_menu$"),
            CallbackQueryHandler(cancel_order, pattern="^cancel_order$|^back_to_menu$"),
        ],
    },
    fallbacks=[CommandHandler("start", start)],
)

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
