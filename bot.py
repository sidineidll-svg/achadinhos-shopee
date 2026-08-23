import os
import base64
import requests

GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"

# Exemplo de produto capturado
novo_produto = {
    "titulo": "Mini Processador de Alho Elétrico Recarregável",
    "preco": "R$ 19,90",
    "imagem": "https://down-br.img.susercontent.com/file/sg-11134201-22100-1b77z6m5m5bv28",
    "link_afiliado": "https://s.shopee.com.br/SEU_LINK_AQUI",
    "categoria": "Cozinha Prática"
}

def atualizar_site():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Erro ao ler o index.html:", response.json())
        return
        
    data = response.json()
    sha = data["sha"]
    conteudo_atual = base64.b64decode(data["content"]).decode('utf-8')
    
    card_html = f"""
            <!-- CARD AUTOMÁTICO -->
            <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition">
                <img src="{novo_produto['imagem']}" alt="{novo_produto['titulo']}" class="w-full h-48 object-cover">
                <div class="p-4">
                    <span class="text-xs font-semibold bg-orange-100 text-orange-600 px-2 py-1 rounded-full">{novo_produto['categoria']}</span>
                    <h2 class="text-lg font-bold mt-2 text-gray-900">{novo_produto['titulo']}</h2>
                    <div class="mt-4 flex items-center justify-between">
                        <span class="text-xl font-bold text-orange-600">{novo_produto['preco']}</span>
                        <a href="{novo_produto['link_afiliado']}" target="_blank" class="bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded text-sm transition">
                            Ver na Shopee
                        </a>
                    </div>
                </div>
            </div>
    """
    
    ponto_insercao = '<div id="produtos-container" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">'
    if card_html not in conteudo_atual:
        novo_conteudo = conteudo_atual.replace(ponto_insercao, ponto_insercao + "\n" + card_html)
        conteudo_encoded = base64.b64encode(novo_conteudo.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": "Bot: Postando novo produto",
            "content": conteudo_encoded,
            "sha": sha
        }
        
        res = requests.put(url, json=payload, headers=headers)
        if res.status_code == 200:
            print("✅ Produto postado no site com sucesso!")
        else:
            print("❌ Erro ao salvar produto:", res.json())

if __name__ == "__main__":
    atualizar_site()
