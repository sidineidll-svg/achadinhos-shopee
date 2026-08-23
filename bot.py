import os
import base64
import requests
import google.generativeai as genai

GITHUB_TOKEN = os.getenv("GH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
IMGBB_KEY = os.getenv("IMGBB_API_KEY")

REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

def gerar_texto_ia(nome_produto, preco):
    if not GEMINI_KEY:
        return "Confira esta oferta incrível com desconto na Shopee!"
    try:
        model = genai.GenerativeAI(model_name="gemini-1.5-flash")
        prompt = f"Escreva uma frase super curta (máximo 12 palavras) e chamativa com emojis para vender o produto '{nome_produto}' por {preco}."
        resposta = model.generate_content(prompt)
        return resposta.text.strip()
    except Exception as e:
        print("Erro Gemini:", e)
        return "Aproveite esta oferta imperdível na Shopee!"

def hospedar_imagem_imgbb(url_shopee):
    """Baixa a imagem da Shopee e faz upload para o ImgBB para ter um link 100% público"""
    if not IMGBB_KEY:
        print("Aviso: IMGBB_API_KEY não configurada. Usando imagem original.")
        return url_shopee
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://shopee.com.br/"
        }
        res_img = requests.get(url_shopee, headers=headers)
        if res_img.status_code == 200:
            img_b64 = base64.b64encode(res_img.content).decode('utf-8')
            
            url_api = f"https://api.imgbb.com/1/upload?key={IMGBB_KEY}"
            payload = {"image": img_b64}
            
            res_upload = requests.post(url_api, data=payload)
            if res_upload.status_code == 200:
                link_direto = res_upload.json()['data']['url']
                print(f"✅ Imagem hospedada no ImgBB com sucesso: {link_direto}")
                return link_direto
    except Exception as e:
        print("Erro no upload do ImgBB:", e)
        
    return url_shopee

# PRODUTOS OFICIAIS
produtos_para_postar = [
    {
        "titulo": "Shorts Feminino Mauricinho Linho Confortável",
        "preco": "R$ 29,90",
        "imagem_original": "https://down-br.img.susercontent.com/file/sg-11134201-7rd5y-lvj20a1q9r2q66",
        "link_afiliado": "https://s.shopee.com.br/3LQGcAGDFV",
        "categoria": "Moda Feminina"
    }
]

def atualizar_site():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Erro ao acessar index.html:", response.json())
        return
        
    data = response.json()
    sha = data["sha"]
    conteudo_atual = base64.b64decode(data["content"]).decode('utf-8')
    
    cards_html = ""
    for prod in produtos_para_postar:
        descricao_ia = gerar_texto_ia(prod['titulo'], prod['preco'])
        
        # Gera o link público hospedado sem bloqueios
        img_publica = hospedar_imagem_imgbb(prod['imagem_original'])
        
        cards_html += f"""
            <!-- CARD PRODUTO -->
            <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition">
                <img src="{img_publica}" alt="{prod['titulo']}" class="w-full h-48 object-cover">
                <div class="p-4">
                    <span class="text-xs font-semibold bg-orange-100 text-orange-600 px-2 py-1 rounded-full">{prod['categoria']}</span>
                    <h2 class="text-lg font-bold mt-2 text-gray-900">{prod['titulo']}</h2>
                    <p class="text-xs text-gray-500 mt-1">{descricao_ia}</p>
                    <div class="mt-4 flex items-center justify-between">
                        <span class="text-xl font-bold text-orange-600">{prod['preco']}</span>
                        <a href="{prod['link_afiliado']}" target="_blank" class="bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded text-sm transition">
                            Ver na Shopee
                        </a>
                    </div>
                </div>
            </div>
        """

    inicio_container = '<div id="produtos-container" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">'
    fim_container = '</div>'
    
    if inicio_container in conteudo_atual:
        partes = conteudo_atual.split(inicio_container)
        resto = partes[1].split(fim_container, 1)
        novo_conteudo = partes[0] + inicio_container + "\n" + cards_html + "\n        " + fim_container + resto[1]
    else:
        print("Erro: container id='produtos-container' não encontrado no index.html")
        return

    conteudo_encoded = base64.b64encode(novo_conteudo.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": "Bot: Imagens integradas via ImgBB",
        "content": conteudo_encoded,
        "sha": sha
    }
    
    res = requests.put(url, json=payload, headers=headers)
    if res.status_code == 200:
        print("✅ Site atualizado com imagens livres de bloqueio!")
    else:
        print("❌ Erro ao salvar no GitHub:", res.json())

if __name__ == "__main__":
    atualizar_site()
