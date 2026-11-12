# MARX SECRET – Arquitetura

```
┌──────────────────────────── ui/ (PySide6) ─────────────────────────────┐
│ main_window · pages/* · widgets · theme · icons · splash · worker      │
└───────────────┬────────────────────────────────────────────────────────┘
                │ AppContext (sinais Qt, configurações)
┌───────────────▼──────────── services/operations.py ────────────────────┐
│ ocultar · extrair · .mxs · analisar · comparar · exclusão · integridade │
│ cronometragem + registro no histórico (somente metadados)               │
└──────┬──────────────────────────┬───────────────────────┬──────────────┘
       │                          │                       │
┌──────▼────── core/ ─────┐ ┌─────▼──── data/ ───┐ ┌─────▼─── reports/ ───┐
│ crypto  payload  stego  │ │ database (SQLite)  │ │ pdf_report csv_report│
│ imageio analysis compare│ └────────────────────┘ └──────────────────────┘
│ secure_delete paths     │
└─────────────────────────┘
```

## Princípios

- **Núcleo sem dependência de interface**: `core/`, `data/`, `services/` e `reports/` não
  importam Qt. Isso permite testes rápidos, autodiagnóstico, uma futura CLI e portabilidade.
- **Operações longas fora da thread da interface** (`ui/worker.py`, `QThreadPool`).
- **Erros tipados** (`core/errors.py`) com mensagens em português seguras para exibição.
- **Gravação atômica** de todos os arquivos produzidos.

## Portabilidade (Linux e macOS)

- Caminhos por plataforma centralizados em `core/paths.py` (APPDATA, `~/Library/Application
  Support`, XDG).
- Todas as dependências são multiplataforma; os testes já rodam em Linux no CI.
- Para empacotar: PyInstaller funciona nos três sistemas com o mesmo `.spec`
  (no macOS, adicionar `BUNDLE` para gerar `.app`; no Linux, AppImage ou `.deb`).
- O código específico de Windows (AppUserModelID, mutex do instalador) é condicional.

## Testes

| Arquivo | Escopo |
|---|---|
| `test_crypto.py` | Argon2id, AES-GCM, adulteração, senhas |
| `test_payload.py` | contêiner, senha errada, AAD, SHA-256, limites, nomes |
| `test_stego.py` | LSB 1–3 bits, disperso, capacidade, alfa, formatos, imagens inválidas |
| `test_services.py` | fluxos completos, histórico sem segredos, .mxs, exclusão segura |
| `test_database.py` | CRUD, filtros, estatísticas, configurações |
| `test_analysis_compare.py` | estatísticas, qui-quadrado, assinatura, PSNR/SSIM |
| `test_reports.py` | PDF e CSV, injeção de fórmulas |
| `test_gui.py` | navegação, botões conectados, fluxos de interface, temas |
| `test_paths_app.py` | modo portátil, recursos, CLI, ausência de nomes antigos |

No CI Windows também são testados: autodiagnóstico do executável, instalação silenciosa,
atalhos, execução offline (firewall), versão portátil e desinstalação completa.
