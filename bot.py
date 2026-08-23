import os
import re
import json
import base64
import requests
from google import genai

GITHUB_TOKEN = os.getenv("GH_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
IMGBB_KEY = os.getenv("IMGBB_API_KEY")

REPO_OWNER = "sidineidll-svg"
REPO_NAME = "achadinhos-shopee"
FILE_PATH = "index.html"
POSTADOS_PATH = "postados.json"

client_gemini = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# Mapeia o domínio do link para o nome/classe da loja usados no site
LOJAS = {
    "shopee": {"nome": "Shopee", "slug": "shopee"},
    "mercadolivre": {"nome": "Mercado Livre", "slug": "mercado-livre"},
    "amazon": {"nome": "Amazon", "slug": "amazon"},
    "magazineluiza": {"nome": "Magalu", "slug": "magalu"},
    "magalu": {"nome": "Magalu", "slug": "magalu"},
}


def identificar_loja(link):
    dominio = link.lower()
    for chave, info in LOJAS.items():
        if chave in dominio:
            return info["nome"], info["slug"]
    return "Loja Parceira", "outras"


def extrair_codigo(link):
    """Pega um identificador curto do link pra usar como chave em postados.json"""
    match = re.search(r'/([A-Za-z0-9]{6,})/?$', link.rstrip('/'))
    return match.group(1) if match else link


def gerar_texto_ia(nome_produto, preco):
    if not client_gemini:
        return "Aproveite esta oferta imperdível!"
    try:
        prompt = (
            f"Escreva uma frase super curta (máximo 12 palavras) e chamativa "
            f"com emojis para vender o produto '{nome_produto}' por {preco}."
        )
        resposta = client_gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return resposta.text.strip()
    except Exception as e:
        print("Erro Gemini:", e)
        return "Aproveite esta oferta imperdível!"


def hospedar_imagem_imgbb(url_origem):
    """Baixa a imagem original e faz upload para o ImgBB para ter um link público estável"""
    if not IMGBB_KEY:
        print("Aviso: IMGBB_API_KEY não configurada. Usando imagem original.")
        return url_origem

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://shopee.com.br/"
        }
        res_img = requests.get(url_origem, headers=headers, timeout=20)
        if res_img.status_code == 200:
            img_b64 = base64.b64encode(res_img.content).decode('utf-8')
            url_api = f"https://api.imgbb.com/1/upload?key={IMGBB_KEY}"
            res_upload = requests.post(url_api, data={"image": img_b64}, timeout=30)
            if res_upload.status_code == 200:
                link_direto = res_upload.json()['data']['url']
                print(f"✅ Imagem hospedada no ImgBB: {link_direto}")
                return link_direto
    except Exception as e:
        print("Erro no upload do ImgBB:", e)

    return url_origem


# PRODUTOS OFICIAIS A POSTAR NESTE CICLO
produtos_para_postar = [
    {
        "titulo": "Shorts Feminino Mauricinho Linho Confortável",
        "preco": "R$ 29,90",
        "preco_antigo": "",
        "desconto": "",
        "imagem_original": "https://down-br.img.susercontent.com/file/sg-11134201-7rd5y-lvj20a1q9r2q66",
        "link_afiliado": "https://s.shopee.com.br/3LQGcAGDFV",
        "categoria": "Moda Feminina"
    }
]


def montar_card(prod, loja_nome, loja_slug, legenda):
    off_html = f'<span class="off-badge">{prod["desconto"]}</span>' if prod.get("desconto") else ""
    old_price_html = (
        f'<span class="old-price">{prod["preco_antigo"]}</span>'
        if prod.get("preco_antigo") else ""
    )
    return f"""
      <!-- CARD AUTOMÁTICO -->
      <div class="deal-card" data-loja="{loja_slug}">
        <div class="thumb">
          <span class="store-badge">{loja_nome}</span>
          {off_html}
          <img src="{prod['imagem_publica']}" alt="{prod['titulo']}" loading="lazy"
               onerror="this.src='https://placehold.co/400x300/EFE3C4/1C1A15?text=Sem+imagem'">
        </div>
        <div class="body">
          <div class="name">{prod['titulo']}</div>
          <p style="font-size:0.8rem;color:var(--ink-soft);margin:0;">{legenda}</p>
          <div class="price-row">
            {old_price_html}
            <span class="new-price">{prod['preco']}</span>
          </div>
          <a href="{prod['link_afiliado']}" target="_blank" rel="nofollow noopener" class="cta">Ver oferta →</a>
        </div>
      </div>
    """


def carregar_postados(github_headers):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{POSTADOS_PATH}"
    res = requests.get(url, headers=github_headers)
    if res.status_code != 200:
        return [], None
    data = res.json()
    try:
        lista = json.loads(base64.b64decode(data["content"]).decode('utf-8'))
    except Exception:
        lista = []
    return lista, data["sha"]


def salvar_postados(github_headers, lista, sha):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{POSTADOS_PATH}"
    conteudo = json.dumps(lista, ensure_ascii=False, indent=2)
    payload = {
        "message": "Bot: atualiza lista de produtos já postados",
        "content": base64.b64encode(conteudo.encode('utf-8')).decode('utf-8'),
    }
    if sha:
        payload["sha"] = sha
    res = requests.put(url, json=payload, headers=github_headers)
    if res.status_code not in (200, 201):
        print("❌ Erro ao salvar postados.json:", res.json())


def atualizar_site():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Erro ao acessar index.html:", response.json())
        return

    data = response.json()
    sha = data["sha"]
    conteudo_atual = base64.b64decode(data["content"]).decode('utf-8')

    postados, postados_sha = carregar_postados(headers)

    cards_html = ""
    novos_postados = list(postados)

    for prod in produtos_para_postar:
        codigo = extrair_codigo(prod["link_afiliado"])
        if codigo in postados:
            print(f"↷ Já postado, pulando: {prod['titulo']}")
            continue

        loja_nome, loja_slug = identificar_loja(prod["link_afiliado"])
        legenda = gerar_texto_ia(prod["titulo"], prod["preco"])
        prod["imagem_publica"] = hospedar_imagem_imgbb(prod["imagem_original"])

        cards_html += montar_card(prod, loja_nome, loja_slug, legenda)
        novos_postados.append(codigo)

    if not cards_html:
        print("Nada novo para postar neste ciclo.")
        return

    marcador = "<!-- FIM-CARDS -->"
    if marcador not in conteudo_atual:
        print("Erro: marcador '<!-- FIM-CARDS -->' não encontrado no index.html")
        return

    novo_conteudo = conteudo_atual.replace(marcador, cards_html + "\n    " + marcador)

    payload = {
        "message": "Bot: novos produtos publicados",
        "content": base64.b64encode(novo_conteudo.encode('utf-8')).decode('utf-8'),
        "sha": sha
    }

    res = requests.put(url, json=payload, headers=headers)
    if res.status_code == 200:
        print("✅ Site atualizado com sucesso!")
        salvar_postados(headers, novos_postados, postados_sha)
    else:
        print("❌ Erro ao salvar no GitHub:", res.json())


if __name__ == "__main__":
    atualizar_site()
