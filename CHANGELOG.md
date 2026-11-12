# Histórico de versões

## 1.1.0 — 2026-11-12
- **Capacidade estendida**: conteúdo criptografado em blocos privados do PNG, sem depender da
  resolução da imagem (até 256 MB); modo Automático escolhe LSB ou estendido.
- Limite padrão de conteúdo elevado para 256 MB; compressão mais rápida para arquivos grandes.
- Banner oficial MARX SECRET no dashboard, abertura, Sobre, relatórios e manual.

## 1.0.0 — 2026-11-12
- Primeira versão do **MARX SECRET Professional**.
- Ocultação/extração de mensagens e arquivos (LSB 1–3 bits, sequencial ou disperso).
- AES-256-GCM + Argon2id, verificação SHA-256, verificação pós-gravação.
- Criptografia de arquivos `.mxs`, gerador de senhas, verificação de hashes.
- Análise estatística (qui-quadrado, entropia, plano LSB) e comparação (PSNR, SSIM, MSE).
- Histórico SQLite, relatórios PDF/CSV, gerenciador de arquivos com exclusão segura.
- Interface PySide6 com tema escuro/claro e identidade visual própria.
- Instalador Inno Setup, versão portátil, ZIP do código-fonte e manual em PDF.
