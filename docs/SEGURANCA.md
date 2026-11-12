# MARX SECRET – Modelo de segurança

## Objetivos

1. **Confidencialidade**: sem a senha, o conteúdo oculto não pode ser lido.
2. **Autenticidade e integridade**: qualquer alteração (senha errada, bit trocado, cabeçalho
   manipulado) é detectada e o conteúdo não é entregue.
3. **Discrição**: a alteração da imagem é imperceptível (PSNR típico > 50 dB) e, no modo disperso,
   espalhada pela imagem inteira.
4. **Privacidade operacional**: nada sai do computador; nada secreto é persistido.

## Primitivas

| Função | Algoritmo | Parâmetros |
|---|---|---|
| Cifra | AES-256-GCM (`cryptography`) | chave 256 bits, nonce aleatório 96 bits, tag 128 bits |
| Derivação de chave | Argon2id (`argon2-cffi`) | sal aleatório 128 bits; Rápido 19 MiB/t=2/p=1, Padrão 64 MiB/t=3/p=4, Alto 256 MiB/t=4/p=4 |
| Integridade | SHA-256 | sobre o conteúdo original, verificado após descriptografia e descompressão |
| Dispersão | SHA-256(“MARX-SECRET/scatter/v1” ‖ semente 64 bits ‖ senha) → PCG64 → amostragem sem reposição | semente aleatória por operação |
| Aleatoriedade | `os.urandom` / `secrets` | CSPRNG do sistema operacional |

## Formato do contêiner

```
versão(1) | flags(1) | [kdf t(1) m(4) p(1) | sal(16) | nonce(12)] | corpo
corpo = AES-256-GCM(chave, nonce, interno, AAD = cabeçalho completo)   (se criptografado)
interno = tipo(1) | len_nome(2) | nome | tamanho(8) | SHA-256(32) | dados[zlib]
```

Na imagem, um cabeçalho de 17 bytes (assinatura `MXS§`, layout, tamanho, semente) é gravado a
1 bit/canal nos primeiros 136 valores RGB; o corpo é gravado a partir daí, sequencial ou disperso.

## Capacidade estendida

Quando o conteúdo não cabe nos pixels (ou por escolha do usuário), o mesmo contêiner criptografado
é gravado em blocos PNG auxiliares privados `mxSc` (até 16 MiB cada, com índice e total) antes do
`IEND`. Os pixels não são alterados e o PNG permanece válido. A confidencialidade e a integridade
são idênticas às do modo LSB (AES-256-GCM + SHA-256, além do CRC de cada bloco). A discrição é
menor: o tamanho do arquivo cresce e a presença dos blocos é detectável por inspeção da estrutura
do arquivo (o módulo de análise a reporta).

## Validações e limites

- Imagem: extensão suportada, arquivo não vazio, ≤ 300 MB, ≤ 100 megapixels (proteção contra
  *decompression bomb*), mínimo de 64 pixels, verificação estrutural pelo Pillow.
- Saída: somente formatos sem perdas (PNG/BMP/TIFF); gravação atômica (arquivo temporário +
  `os.replace`); verificação pós-gravação relendo o arquivo.
- Conteúdo: ≤ 256 MB (configurável); descompressão limitada ao tamanho
  declarado (proteção contra *zip bomb*).
- Parâmetros Argon2id lidos do arquivo são limitados (t ≤ 20, m ≤ 1 GiB, p ≤ 16).
- Nomes recuperados são saneados (sem caminhos, caracteres proibidos ou nomes reservados do
  Windows) e nunca sobrescrevem arquivos existentes.
- CSV exportado neutraliza fórmulas (`=`, `+`, `-`, `@`).

## Privacidade

- Senhas não são gravadas em disco, log, histórico ou relatório; os buffers de chave são zerados
  após o uso (melhor esforço em Python).
- O histórico grava apenas metadados técnicos; nomes de arquivos ocultos e mensagens não são
  registrados. O SQLite opera com `PRAGMA secure_delete=ON`; limpar o histórico executa `VACUUM`.
- A área de transferência é limpa automaticamente (padrão 30 s) após copiar uma mensagem.
- Temporários são criados em diretórios privados e apagados com sobrescrita; restos de execuções
  interrompidas são limpos na inicialização.
- Não há telemetria nem acesso à rede (verificado no CI com o executável bloqueado no firewall).

## Limitações conhecidas

- A esteganografia LSB não resiste a recompressão, redimensionamento ou edição da imagem.
- O modo sequencial é detectável por análise estatística (o próprio módulo de análise o mostra);
  use o modo disperso com 1 bit/canal para máxima discrição.
- A exclusão segura não garante eliminação física em SSDs, sistemas com journaling, cópias de
  sombra ou pastas sincronizadas na nuvem.
- Python não permite garantir a remoção de todas as cópias de uma senha da memória.
