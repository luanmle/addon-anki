# Anki Concursos Add-on

Este repositório contém o código-fonte do add-on **Anki Concursos** para sincronização offline-first e incremental de flashcards publicados.

## Requisitos de Desenvolvimento

- Python 3.9+
- pytest (para testes locais)

## Instalação em Modo Desenvolvedor

Para carregar o add-on no seu Anki para testes, crie um link simbólico apontando a pasta `anki_concursos` para a pasta de complementos (addons) do Anki:

### Windows (PowerShell Administrador)
```powershell
mklink /D "%APPDATA%\Anki2\addons21\anki_concursos" "C:\caminho\para\addon-anki\anki_concursos"
```

### macOS / Linux
```bash
ln -s "/caminho/para/addon-anki/anki_concursos" "~/Library/Application Support/Anki2/addons21/anki_concursos"
```

---

## Executando Testes Unitários

O add-on possui testes unitários mockados para rodar de forma isolada do runtime do Anki. Para executá-los:

```bash
python -m pytest
```

---

## Como Empacotar o Add-on (`.ankiaddon`)

Para gerar o arquivo de distribuição `.ankiaddon` pronto para produção e staging, execute o script de build na raiz do repositório:

```bash
python build_addon.py
```

O script criará o arquivo `anki_concursos.ankiaddon` na raiz do projeto, incluindo automaticamente apenas o código de produção, manifestos e configurações, excluindo caches (`__pycache__`), logs, bancos locais SQLite de teste (`anki_concursos.db`), arquivos de credenciais (`auth.json`), e pastas de testes ou documentação de desenvolvimento.