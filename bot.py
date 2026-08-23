import os
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from instagrapi import Client

# Lendo credenciais com segurança das variáveis do Render
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_PASS = os.getenv("INSTAGRAM_PASS")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") # O token que você já usava

# Conecta no Instagram reutilizando a sessão gerada
cl = Client()
if os.path.exists("session.json"):
    cl.load_settings("session.json")
cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)

# Dicionário temporário para guardar os dados da oferta ativa
oferta_atual = {}

async def processar_mensagem_shopee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Garante que só você pode mandar mensagens no bot
    if str(update.message.chat_id) != str(ADMIN_CHAT_ID):
        return

    # --- AQUI FICA A SUA LÓGICA ATUAL DE PEGAR A OFERTA E A IA ---
    # Exemplo do resultado que seu código já gera:
    link_afiliado = "https://shope.ee/exemplo" 
    legenda_ia = "🔥 Confira essa oferta incrível na Shopee!"
    url_imagem = "https://i.ibb.co/exemplo.jpg" # URL do ImgBB ou da Shopee

    # Baixa a imagem temporariamente para o Render conseguir postar no Instagram
    img_data = requests.get(url_imagem).content
    caminho_imagem = "temp_post.jpg"
    with open(caminho_imagem, "wb") as handler:
        handler.write(img_data)

    # Armazena na memória temporária para quando você clicar no botão
    oferta_atual['link'] = link_afiliado
    oferta_atual['legenda'] = legenda_ia
    oferta_atual['imagem'] = caminho_imagem

    # Monta o menu de botões para o seu Telegram
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
        f"**Legenda:** {legenda_ia}\n\n"
        f"Escolha onde deseja publicar no Instagram:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def executar_postagem_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    opcao = query.data
    caminho_img = oferta_atual.get('imagem', 'temp_post.jpg')
    link = oferta_atual.get('link')
    legenda = oferta_atual.get('legenda')

    if opcao == "post_story":
        await query.edit_message_text("⏳ Enviando para o **Story** do Instagram...")
        cl.photo_upload_to_story(caminho_img, caption="Achado Shopee!", link=link)
        await query.message.reply_text("🎉 Postado no Story com sucesso!")

    elif opcao == "post_feed":
        await query.edit_message_text("⏳ Enviando para o **Feed** do Instagram...")
        legenda_completa = f"{legenda}\n\n🛒 Link de compra nos Stories ou na Bio!"
        cl.photo_upload(caminho_img, caption=legenda_completa)
        await query.message.reply_text("🎉 Postado no Feed com sucesso!")

    elif opcao == "post_reels":
        await query.edit_message_text("⏳ Enviando para o **Reels**...")
        legenda_completa = f"{legenda}\n\n🎬 Confira o link deste produto nos Stories!"
        # Certifique-se de usar um arquivo .mp4 caso vá postar Reels
        cl.clip_upload(caminho_img, caption=legenda_completa)
        await query.message.reply_text("🎉 Postado no Reels com sucesso!")

    # Limpa a imagem temporária do servidor
    if os.path.exists(caminho_img):
        os.remove(caminho_img)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, processar_mensagem_shopee))
    app.add_handler(CallbackQueryHandler(executar_postagem_instagram))
    app.run_polling()

if __name__ == '__main__':
    main()
