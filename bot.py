import os
import base64
import requests
import google.generativeai as genai

# Chaves secretas
GITHUB_TOKEN = os.getenv("GH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"

# Configura o Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

def gerar_texto_ia(nome_produto, preco):
    if not GEMINI_KEY:
        return "Oferta imperdível na Shopee com o melhor preço!"
    try:
        model = genai.GenerativeAI(model_name="gemini-1.5-flash")
        prompt = f"Escreva uma frase super curta (máximo 12 palavras) e persuasiva com emojis para vender o produto '{nome_produto}' por {preco}."
        resposta = model.generate_content(prompt)
        return resposta.text.strip()
    except Exception as e:
        print("Erro Gemini:", e)
        return "Aproveite esta oferta especial na Shopee!"

# Produtos cadastrados para publicação
produtos_para_postar = [
    {
        "titulo": "Mini Processador de Alho Elétrico Recarregável",
        "preco": "R$ 19,90",
        "imagem": "https://down-br.img.susercontent.com/file/sg-11134201-22100-1b77z6m5m5bv28",
        "link_afiliado": "https://s.shopee.com.br/3LQGcAGDFV",
        "categoria": "Utilidades Domésticas"
    }
]

def atualizar_site():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Erro ao acessar o index.html:", response.json())
        return
        
    data = response.json()
    sha = data["sha"]
    conteudo_atual = base64.b64decode(data["content"]).decode('utf-8')
    
    cards_novos = ""
    for prod in produtos_para_postar:
        descricao_ia = gerar_texto_ia(prod['titulo'], prod['preco'])
        
        card_html = f"""
            <!-- CARD AUTOMÁTICO COM GEMINI -->
            <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition">
                <img src="{prod['imagem']}" alt="{prod['titulo']}" class="w-full h-48 object-cover">
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
        if card_html not in conteudo_atual:
            cards_novos += "\n" + card_html

    if cards_novos:
        ponto_insercao = '<div id="produtos-container" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">'
        novo_conteudo = conteudo_atual.replace(ponto_insercao, ponto_insercao + cards_novos)
        conteudo_encoded = base64.b64encode(novo_conteudo.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": "Bot: Postando produto com link oficial de afiliado",
            "content": conteudo_encoded,
            "sha": sha
        }
        
        res = requests.put(url, json=payload, headers=headers)
        if res.status_code == 200:
            print("✅ Post publicado com sucesso com legenda gerada pelo Gemini!")
        else:
            print("❌ Erro ao atualizar o site:", res.json())

if __name__ == "__main__":
    atualizar_site()
