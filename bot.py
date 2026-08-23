import os
import json
import time
import base64
import requests
import google.generativeai as genai

# ===================== CONFIGURAÇÃO =====================
GITHUB_TOKEN = os.getenv("GH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"
PRODUTOS_PATH = "produtos.json"      # lista de produtos a publicar (fica no repo ou local)
POSTADOS_PATH = "postados.json"      # controle de quem já foi publicado (fica no repo)

if not GITHUB_TOKEN:
    raise SystemExit("❌ Variável de ambiente GH_TOKEN não definida.")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}


# ===================== GERAÇÃO DE TEXTO (IA) =====================
def gerar_texto_ia(nome_produto, preco):
    if not GEMINI_KEY:
        return "Oferta imperdível na Shopee com o melhor preço!"
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")  # <-- corrigido
        prompt = (
            f"Escreva uma frase super curta (máximo 12 palavras) e persuasiva "
            f"com emojis para vender o produto '{nome_produto}' por {preco}."
        )
        resposta = model.generate_content(prompt)
        texto = resposta.text.strip()
        return texto if texto else "Aproveite esta oferta especial na Shopee!"
    except Exception as e:
        print("⚠️ Erro Gemini:", e)
        return "Aproveite esta oferta especial na Shopee!"


# ===================== HELPERS GITHUB =====================
def get_arquivo(path):
    """Busca conteúdo + sha de um arquivo no repo. Retorna (conteudo_str, sha) ou (None, None) se não existir."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 404:
        return None, None
    resp.raise_for_status()
    data = resp.json()
    conteudo = base64.b64decode(data["content"]).decode("utf-8")
    return conteudo, data["sha"]


def put_arquivo(path, conteudo_str, sha, mensagem, max_tentativas=3):
    """Atualiza um arquivo no repo, com retry simples em caso de conflito de SHA (409)."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    conteudo_encoded = base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")

    for tentativa in range(1, max_tentativas + 1):
        payload = {"message": mensagem, "content": conteudo_encoded, "sha": sha}
        res = requests.put(url, json=payload, headers=HEADERS)

        if res.status_code == 200:
            return True

        if res.status_code == 409 and tentativa < max_tentativas:
            print(f"⚠️ Conflito de SHA (tentativa {tentativa}), buscando versão atual e tentando de novo...")
            _, sha = get_arquivo(path)
            time.sleep(1)
            continue

        print(f"❌ Erro ao atualizar {path}:", res.status_code, res.json())
        return False

    return False


# ===================== PRODUTOS =====================
def carregar_produtos():
    """Tenta carregar produtos.json do repo; se não existir, usa a lista local de exemplo."""
    conteudo, _ = get_arquivo(PRODUTOS_PATH)
    if conteudo:
        return json.loads(conteudo)

    # fallback local, útil pra testar sem precisar do produtos.json no repo ainda
    return [
        {
            "id": "3LQGcAGDFV",  # use algo estável e único por produto (ex: código do link)
            "titulo": "Mini Processador de Alho Elétrico Recarregável",
            "preco": "R$ 19,90",
            "imagem": "https://down-br.img.susercontent.com/file/sg-11134201-22100-1b77z6m5m5bv28",
            "link_afiliado": "https://s.shopee.com.br/3LQGcAGDFV",
            "categoria": "Utilidades Domésticas",
        }
    ]


def carregar_postados():
    conteudo, sha = get_arquivo(POSTADOS_PATH)
    if conteudo:
        return set(json.loads(conteudo)), sha
    return set(), None


def salvar_postados(postados_set, sha):
    conteudo = json.dumps(sorted(postados_set), ensure_ascii=False, indent=2)
    put_arquivo(POSTADOS_PATH, conteudo, sha, "Bot: atualizando lista de produtos postados")


# ===================== LÓGICA PRINCIPAL =====================
def atualizar_site():
    conteudo_atual, sha_site = get_arquivo(FILE_PATH)
    if conteudo_atual is None:
        print(f"❌ Não foi possível acessar {FILE_PATH}")
        return

    produtos = carregar_produtos()
    postados, sha_postados = carregar_postados()

    cards_novos = ""
    novos_ids = []

    for prod in produtos:
        if prod["id"] in postados:
            continue  # já publicado, pula

        descricao_ia = gerar_texto_ia(prod["titulo"], prod["preco"])

        card_html = f"""
            <!-- PRODUTO:{prod['id']} -->
            <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition">
                <img src="{prod['imagem']}" alt="{prod['titulo']}" class="w-full h-48 object-cover" loading="lazy">
                <div class="p-4">
                    <span class="text-xs font-semibold bg-orange-100 text-orange-600 px-2 py-1 rounded-full">{prod['categoria']}</span>
                    <h2 class="text-lg font-bold mt-2 text-gray-900">{prod['titulo']}</h2>
                    <p class="text-xs text-gray-500 mt-1">{descricao_ia}</p>
                    <div class="mt-4 flex items-center justify-between">
                        <span class="text-xl font-bold text-orange-600">{prod['preco']}</span>
                        <a href="{prod['link_afiliado']}" target="_blank" rel="nofollow sponsored" class="bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded text-sm transition">
                            Ver na Shopee
                        </a>
                    </div>
                </div>
            </div>
        """
        cards_novos += "\n" + card_html
        novos_ids.append(prod["id"])

        # evita bater o rate limit do Gemini se a lista crescer
        time.sleep(1)

    if not cards_novos:
        print("ℹ️ Nenhum produto novo para postar.")
        return

    ponto_insercao = '<div id="produtos-container" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">'
    if ponto_insercao not in conteudo_atual:
        print("❌ Ponto de inserção não encontrado no index.html — verifique o template.")
        return

    novo_conteudo = conteudo_atual.replace(ponto_insercao, ponto_insercao + cards_novos)

    if put_arquivo(FILE_PATH, novo_conteudo, sha_site, "Bot: postando novos produtos com legenda gerada pelo Gemini"):
        print(f"✅ {len(novos_ids)} produto(s) publicado(s) com sucesso!")
        postados.update(novos_ids)
        salvar_postados(postados, sha_postados)
    else:
        print("❌ Falha ao publicar no index.html — postados.json não foi atualizado.")


if __name__ == "__main__":
    atualizar_site()
