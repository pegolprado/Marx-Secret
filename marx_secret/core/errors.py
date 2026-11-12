"""Hierarquia de exceções do MARX SECRET.

Todas as mensagens são em português e seguras para exibição ao usuário:
nunca contêm senhas nem conteúdos secretos.
"""


class MarxSecretError(Exception):
    """Erro base de todas as operações do MARX SECRET."""

    user_message = "Ocorreu um erro inesperado."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.user_message)


class InvalidImageError(MarxSecretError):
    user_message = "A imagem informada é inválida, corrompida ou não suportada."


class InvalidInputError(MarxSecretError):
    user_message = "Os dados de entrada são inválidos."


class CapacityError(MarxSecretError):
    user_message = "A imagem não possui capacidade suficiente para o conteúdo."


class PayloadTooLargeError(MarxSecretError):
    user_message = "O conteúdo excede o limite de tamanho permitido."


class NoHiddenDataError(MarxSecretError):
    user_message = "Nenhum conteúdo MARX SECRET foi encontrado nesta imagem."


class PasswordRequiredError(MarxSecretError):
    user_message = "Este conteúdo está protegido. Informe a senha."


class AuthenticationError(MarxSecretError):
    user_message = (
        "Senha incorreta ou conteúdo adulterado. A autenticação AES-256-GCM falhou."
    )


class IntegrityError(MarxSecretError):
    user_message = "Falha na verificação de integridade SHA-256: o conteúdo foi corrompido."


class CorruptedDataError(MarxSecretError):
    user_message = "Os dados ocultos estão corrompidos ou em formato desconhecido."
