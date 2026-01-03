"""AES-256-GCM 加密工具"""

import base64
import logging
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

from checkin_bot.config.settings import get_settings

logger = logging.getLogger(__name__)


def _get_key() -> bytes:
    """
    获取加密密钥（32 字节）

    Raises:
        ValueError: 如果密钥无效（不是有效的 32 字节密钥）
    """
    settings = get_settings()
    key_str = settings.encryption_key

    # 如果是 44 字符的 base64 编码，先解码
    if len(key_str) == 44:
        key_bytes = base64.b64decode(key_str)
        if len(key_bytes) == 32:
            return key_bytes
        raise ValueError(f"Base64 解码后的密钥长度为 {len(key_bytes)} 字节，应为 32 字节")

    # 如果是 32 字节的原始密钥，直接使用
    if len(key_str) == 32:
        return key_str.encode()

    # 否则尝试 base64 解码
    try:
        key_bytes = base64.b64decode(key_str)
        if len(key_bytes) == 32:
            return key_bytes
        # 解码成功但长度不对
        raise ValueError(f"Base64 解码后的密钥长度为 {len(key_bytes)} 字节，应为 32 字节")
    except Exception as e:
        # 解码失败或长度不对，抛出明确的错误
        logger.error(f"无效的加密密钥配置: {type(e).__name__}: {e}")
        raise ValueError(
            f"无效的加密密钥配置。密钥应为 32 字节的原始密钥，或 32 字节密钥的 Base64 编码。"
        ) from e


def encrypt_password(password: str) -> str:
    """
    加密密码

    Args:
        password: 明文密码

    Returns:
        Base64 编码的加密数据（nonce + ciphertext）
    """
    key = _get_key()

    # 生成随机 nonce（96 位 = 12 字节）
    nonce = os.urandom(12)

    # 使用 AES-256-GCM 加密
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, password.encode(), None)

    # 将 nonce 前置到密文中（12 字节 nonce + 密文）
    combined = nonce + ciphertext

    # 返回 Base64 编码
    return base64.b64encode(combined).decode()


def decrypt_password(encrypted_data: str) -> str:
    """
    解密密码

    Args:
        encrypted_data: Base64 编码的加密数据（nonce + ciphertext）

    Returns:
        明文密码
    """
    key = _get_key()

    # 解码 Base64
    combined = base64.b64decode(encrypted_data)

    # 提取 nonce（前 12 字节）和密文
    nonce = combined[:12]
    ciphertext = combined[12:]

    # 使用 AES-256-GCM 解密
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext.decode()
