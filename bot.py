import os
import logging
import threading
import requests
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from instagrapi import Client

# Configuração de Logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SERVIDOR FLASK ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot de Ofertas está rodando no Render!"

def rodar_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

threading.Thread(target=rodar_flask, daemon=True).start()

# --- VARIÁVEIS DE AMBIENTE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_PASS = os.getenv("INSTAGRAM_PASS")

cliente_insta = None

def obter_cliente_instagram():
    """Conecta no Instagram sob demanda."""
    global cliente_insta
    if cliente_insta is not None:
        return cliente_insta

    cl = Client()
    
    if os.path.exists("session.json"):
        try:
            cl.load_settings("session.json")
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            logger.info("Login realizado via session.json")
            cliente_insta = cl
            return cliente_insta
        except Exception as e:
            logger.warning(f"Erro no session.json: {e}")

    try:
        cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
        cl.dump_settings("session.json")
        logger.info("Login realizado via usuário/senha")
        cliente_insta = cl
        return cliente_insta
    except Exception as e:
        logger.error(f"Falha no Instagram: {e}")
        raise e

oferta_temp = {}

async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o link ou foto e gera a resposta no Telegram."""
    # Garante que só você pode mandar comandos
    if str(update.message.chat_id) != str(ADMIN_CHAT_ID):
        logger.warning(f"Acesso negado para o ID: {update.message.chat_id}")
        return

    texto_mensagem = update.message.text or update.message.caption or ""
    caminho_imagem = "temp_post.jpg"

    # Processa a foto recebida ou baixa uma imagem padrão para testes
    if update.message.photo:
        foto = await update.message.photo[-1].get_file()
        await foto.download_to_drive(caminho_imagem)
    else:
        # Imagem placeholder para garantir que o arquivo exista
        url_placeholder = "https://picsum.photos/1080/1080"
        headers = {'User-Agent': 'Mozilla/5.0'}
        img_bytes = requests.get(url_placeholder, headers=headers).content
        with open(caminho_imagem, "wb") as f:
            f.write(img_bytes)

    link_afiliado = texto_mensagem if "http" in texto_mensagem else "https://shope.ee/exemplo"
    legenda_gerada = f"🔥 Achado da Shopee!\n\n{texto_mensagem}"

    oferta_temp['link'] = link_afiliado
    oferta_temp['legenda'] = legenda_gerada
    oferta_temp['imagem'] = caminho_imagem

    teclado = [
        [
            InlineKeyboardButton("📱 Postar no Story", callback_data="post_story"),
            InlineKeyboardButton("🎬 Postar no Reels", callback_data="post_reels")
        ],
        [
            InlineKeyboardButton("🖼️ Postar no Feed", callback_data="post_feed")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(
        f"✅ **Oferta Processada!**\n\n"
        f"**Legenda:**\n{legenda_gerada}\n\n"
        f"Escolha o formato para publicar:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def executar_postagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Realiza o envio para o Instagram."""
    query = update.callback_query
    await query.answer()

    opcao = query.data
    caminho_img = oferta_temp.get("imagem", "temp_post.jpg")
    link = oferta_temp.get("link", "")
    legenda = oferta_temp.get("legenda", "")

    try:
        insta = obter_cliente_instagram()

        if opcao == "post_story":
            await query.edit_message_text("⏳ Publicando no **Story**...")
            insta.photo_upload_to_story(caminho_img, caption="Achado Shopee!", link=link)
            await query.message.reply_text("🎉 Publicado no Story com sucesso!")

        elif opcao == "post_feed":
            await query.edit_message_text("⏳ Publicando no **Feed**...")
            legenda_completa = f"{legenda}\n\n🛒 Link no Story ou na Bio!"
            insta.photo_upload(caminho_img, caption=legenda_completa)
            await query.message.reply_text("🎉 Publicado no Feed com sucesso!")

        elif opcao == "post_reels":
            await query.edit_message_text("⏳ Publicando no **Reels**...")
            legenda_completa = f"{legenda}\n\n🎬 Link nos Stories!"
            insta.clip_upload(caminho_img, caption=legenda_completa)
            await query.message.reply_text("🎉 Publicado no Reels com sucesso!")

    except Exception as e:
        logger.error(f"Erro ao postar no Instagram: {e}")
        await query.message.reply_text(f"❌ Erro ao publicar: {e}")

    finally:
        if os.path.exists(caminho_img):
            os.remove(caminho_img)

async def gerenciar_erro(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Captura exceções globais e envia aviso no log e no chat."""
    logger.error(msg="Exceção capturada no bot:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            f"⚠️ Ocorreu um erro ao processar o comando:\n`{context.error}`",
            parse_mode="Markdown"
        )

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN não configurado no Render.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_mensagem))
    app.add_handler(CallbackQueryHandler(executar_postagem))
    
    # Registra o capturador global de erros
    app.add_error_handler(gerenciar_erro)

    logger.info("Bot rodando e monitorando erros...")
    app.run_polling()

if __name__ == "__main__":
    main()
