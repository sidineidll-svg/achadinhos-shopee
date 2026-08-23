import os
import logging
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
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

# Variáveis de Ambiente do Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_PASS = os.getenv("INSTAGRAM_PASS")

# Instância do Instagram em cache
cliente_insta = None

def obter_cliente_instagram():
    """Conecta no Instagram sob demanda para evitar bloqueio 429 na inicialização."""
    global cliente_insta
    if cliente_insta is not None:
        return cliente_insta

    cl = Client()
    
    # 1. Tenta usar o session.json se existir no repositório
    if os.path.exists("session.json"):
        try:
            cl.load_settings("session.json")
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            logger.info("Login realizado via session.json")
            cliente_insta = cl
            return cliente_insta
        except Exception as e:
            logger.warning(f"Erro ao usar session.json, tentando login normal: {e}")

    # 2. Login padrão via usuário e senha
    try:
        cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
        # Salva a sessão localmente para chamadas futuras
        cl.dump_settings("session.json")
        logger.info("Login realizado com sucesso via usuário/senha.")
        cliente_insta = cl
        return cliente_insta
    except Exception as e:
        logger.error(f"Falha ao autenticar no Instagram: {e}")
        raise e

# Dicionário temporário para armazenar a oferta até o clique no botão
oferta_temp = {}

async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe a mensagem/link no Telegram e exibe o menu de postagem."""
    # Garante acesso apenas do administrador
    if str(update.message.chat_id) != str(ADMIN_CHAT_ID):
        return

    texto_mensagem = update.message.text or update.message.caption or ""

    # --- LÓGICA DE PROCESSAMENTO DA SHOPEE / IA ---
    # Substitua pelas suas chamadas de API se necessário:
    link_afiliado = "https://shope.ee/exemplo"  # Seu link gerado
    legenda_gerada = f"🔥 Achado imperdível da Shopee!\n\n{texto_mensagem}"
    
    # Imagem temporária de exemplo (se mandar foto, usa a foto enviada)
    caminho_imagem = "temp_post.jpg"
    if update.message.photo:
        foto = await update.message.photo[-1].get_file()
        await foto.download_to_drive(caminho_imagem)
    else:
        # Imagem padrão para testes caso envie apenas texto/link
        url_placeholder = "https://via.placeholder.com/1080x1080.png"
        img_bytes = requests.get(url_placeholder).content
        with open(caminho_imagem, "wb") as f:
            f.write(img_bytes)

    # Armazena na memória temporária
    oferta_temp['link'] = link_afiliado
    oferta_temp['legenda'] = legenda_gerada
    oferta_temp['imagem'] = caminho_imagem

    # Monta os botões interativos
    teclado = [
        [
            InlineKeyboardButton("📱 Postar no Story (Com Link)", callback_data="post_story"),
            InlineKeyboardButton("🎬 Postar no Reels", callback_data="post_reels")
        ],
        [
            InlineKeyboardButton("🖼️ Postar no Feed", callback_data="post_feed")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    await update.message.reply_text(
        f"✅ **Oferta Processada com Sucesso!**\n\n"
        f"**Legenda:**\n{legenda_gerada}\n\n"
        f"**Link:** {link_afiliado}\n\n"
        f"Escolha o formato para publicar no Instagram:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def executar_postagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback acionado ao clicar em um dos botões do Telegram."""
    query = update.callback_query
    await query.answer()

    opcao = query.data
    caminho_img = oferta_temp.get("imagem", "temp_post.jpg")
    link = oferta_temp.get("link", "")
    legenda = oferta_temp.get("legenda", "")

    try:
        insta = obter_cliente_instagram()

        if opcao == "post_story":
            await query.edit_message_text("⏳ Publicando no **Story** do Instagram...")
            insta.photo_upload_to_story(caminho_img, caption="Achado Shopee!", link=link)
            await query.message.reply_text("🎉 Publicado no Story com sucesso!")

        elif opcao == "post_feed":
            await query.edit_message_text("⏳ Publicando no **Feed** do Instagram...")
            legenda_completa = f"{legenda}\n\n🛒 Link de compra no Story ou na Bio!"
            insta.photo_upload(caminho_img, caption=legenda_completa)
            await query.message.reply_text("🎉 Publicado no Feed com sucesso!")

        elif opcao == "post_reels":
            await query.edit_message_text("⏳ Publicando no **Reels** do Instagram...")
            legenda_completa = f"{legenda}\n\n🎬 Link de compra disponível nos Stories!"
            insta.clip_upload(caminho_img, caption=legenda_completa)
            await query.message.reply_text("🎉 Publicado no Reels com sucesso!")

    except Exception as e:
        logger.error(f"Erro ao publicar no Instagram: {e}")
        await query.message.reply_text(f"❌ Falha ao publicar no Instagram: {e}")

    finally:
        # Limpeza do arquivo temporário
        if os.path.exists(caminho_img):
            os.remove(caminho_img)

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN não configurado nas Variáveis do Render.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers do Telegram
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_mensagem))
    app.add_handler(CallbackQueryHandler(executar_postagem))

    logger.info("Bot iniciado e aguardando mensagens...")
    app.run_polling()

if __name__ == "__main__":
    main()
